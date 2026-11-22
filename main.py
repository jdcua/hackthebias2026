from flask import Flask, jsonify, send_from_directory
import re
import requests
import io
import json
import random
import threading
from queue import Queue
import time
from dotenv import load_dotenv
import os
from pypdf import PdfReader
from GRI_STANDARDS_DATABASE import GRI_STANDARDS, BIAS_FLUFF_WORDS

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover
    Anthropic = None

try:
    from llama_cpp import Llama
except Exception:  # pragma: no cover
    Llama = None

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# LLM backend configuration
# - "anthropic": use Claude (requires ANTHROPIC_API_KEY)
# - "openai":    use any OpenAI-compatible local server (Ollama, llama-server, LM Studio)
# - auto:        anthropic if key present else openai if reachable else None (heuristic fallback)
LLM_BACKEND = os.getenv("LLM_BACKEND", "auto").lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen3:0.6b")
LLM_API_KEY = os.getenv("LLM_API_KEY", "local")  # most local servers ignore this
LLM_MODEL_PATH = os.getenv("LLM_MODEL_PATH", "models/qwen3.5-4b-q4_k_m.gguf")

# Initialize Flask
app = Flask(__name__, static_folder='static')

# Anthropic client (optional)
anthropic_client = None
if ANTHROPIC_API_KEY and Anthropic is not None:
    try:
        anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    except Exception as e:
        print(f"⚠️ Could not init Anthropic client: {e}")

_llama_model = None
_llama_lock = threading.Lock()

def _load_llama_model():
    global _llama_model
    if _llama_model is not None:
        return _llama_model
    if Llama is None:
        return None
    if not os.path.exists(LLM_MODEL_PATH):
        print(f"⚠️ Llama model not found at {LLM_MODEL_PATH}")
        return None
    with _llama_lock:
        if _llama_model is None:
            try:
                print(f"📦 Loading local model {LLM_MODEL_PATH}...")
                _llama_model = Llama(
                    model_path=LLM_MODEL_PATH,
                    n_ctx=int(os.getenv("LLM_N_CTX", "2048")),
                    n_threads=int(os.getenv("LLM_N_THREADS", "4")),
                    verbose=False,
                )
                print("✅ Local model loaded")
            except Exception as e:
                print(f"⚠️ Failed to load local model: {e}")
                _llama_model = None
    return _llama_model

def _backend():
    if LLM_BACKEND == "anthropic":
        return "anthropic" if anthropic_client is not None else None
    if LLM_BACKEND == "openai":
        return "openai"
    if LLM_BACKEND == "llamacpp":
        return "llamacpp"
    # auto
    if anthropic_client is not None:
        return "anthropic"
    if os.path.exists(LLM_MODEL_PATH) and Llama is not None:
        return "llamacpp"
    return "openai"

def llm_chat(prompt, max_tokens=500, system=None):
    """Send a chat prompt to the configured LLM. Returns text or None."""
    backend = _backend()
    if backend == "anthropic" and anthropic_client is not None:
        try:
            kwargs = {
                "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            message = anthropic_client.messages.create(**kwargs)
            return message.content[0].text
        except Exception as e:
            print(f"⚠️ Anthropic call failed: {e}")
            return None
    if backend == "llamacpp":
        llm = _load_llama_model()
        if llm is None:
            return None
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            resp = llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            content = resp["choices"][0]["message"].get("content") or ""
            return content
        except Exception as e:
            print(f"⚠️ Local model call failed: {e}")
            return None

    if backend == "openai":
        try:
            url = f"{LLM_BASE_URL}/chat/completions"
            payload = {
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            if system:
                payload["messages"].insert(0, {"role": "system", "content": system})
            headers = {"Content-Type": "application/json"}
            if LLM_API_KEY:
                headers["Authorization"] = f"Bearer {LLM_API_KEY}"
            resp = requests.post(url, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if not content.strip():
                content = msg.get("reasoning_content") or ""
            return content
        except Exception as e:
            print(f"⚠️ Local LLM call failed ({LLM_BASE_URL}): {e}")
            return None
    return None

# PDF List - Sources for sustainability reports
# These URLs are used to fetch real-world data for the game
PDF_URLS = [
    "https://www.deloitte.com/content/dam/assets-shared/docs/about/gir/global-report-full-version.pdf",
    "https://www.ey.com/content/dam/ey-unified-site/ey-com/en-ca/about-us/documents/ey-ca-impact-report-en-2025-v1.pdf",
    "https://www.pwc.com/gx/en/about/assets/2025-pwc-network-sustainability-report.pdf",
    "https://www.nestle.com/sites/default/files/2024-02/creating-shared-value-sustainability-report-2023-en.pdf"
]

GAME_STATE_FILE = 'game_state.json'  # file to persist used PDFs state

# Preloading system to avoid wait times for the user
preloaded_games = Queue(maxsize=2)  # Store up to 2 preloaded games logic
preload_lock = threading.Lock()     # Thread safety for queue access
is_preloading = False               # Flag to prevent multiple preloader threads

class PDFScraper:
    def __init__(self):
        self.pdfs_processed = 0

    def download_pdf_text(self, url):
        """Downloads a PDF from a URL and extracts its text"""
        print(f"📄 Downloading PDF from {url}...")
        try:
            # unique user agent to avoid being blocked by some servers
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            
            text = ""
            # Limit to first 50 pages to prevent processing overload on huge reports
            max_pages = min(50, len(reader.pages))
            for i, page in enumerate(reader.pages[:max_pages]): 
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            self.pdfs_processed += 1
            print(f"✅ Successfully extracted text from PDF ({len(text)} chars, {max_pages} pages)")
            return text
        except Exception as e:
            print(f"❌ Error processing {url}: {e}")
            return ""

    def clean_text(self, text):
        """Removes extra whitespace and normalizes text"""
        return re.sub(r'\s+', ' ', text).strip()

    def analyze_gri_compliance(self, pdf_content):
        """Compare PDF content against GRI standards"""
        print("\n🔍 Analyzing PDF against GRI Standards...")
        
        pdf_lower = pdf_content.lower()
        
        analysis = {
            'missing_standards': [],
            'misleading_content': [],
            'compliant_standards': []
        }
        
        # Check each GRI standard
        for gri_code, standard in GRI_STANDARDS.items():
            keywords_found = []
            metrics_found = []
            
            for keyword in standard['keywords']:
                if keyword.lower() in pdf_lower:
                    keywords_found.append(keyword)
            
            for metric in standard['required_metrics']:
                if metric.lower() in pdf_lower:
                    metrics_found.append(metric)
            
            if not keywords_found and not metrics_found:
                analysis['missing_standards'].append({
                    'code': gri_code,
                    'title': standard['title'],
                    'reason': f"No keywords or metrics found for {standard['title']}"
                })
            elif keywords_found and not metrics_found:
                analysis['misleading_content'].append({
                    'code': gri_code,
                    'title': standard['title'],
                    'reason': f"Mentions {', '.join(keywords_found[:2])} but lacks quantitative metrics",
                    'keywords': keywords_found
                })
            elif keywords_found and metrics_found:
                analysis['compliant_standards'].append({
                    'code': gri_code,
                    'title': standard['title'],
                    'keywords': keywords_found,
                    'metrics': metrics_found
                })
        
        # Check for bias/fluff words
        bias_findings = []
        for bias_word in BIAS_FLUFF_WORDS:
            if bias_word.lower() in pdf_lower:
                pattern = r'(.{0,50}' + re.escape(bias_word) + r'.{0,50})'
                matches = re.findall(pattern, pdf_lower, re.IGNORECASE)
                if matches:
                    bias_findings.append({
                        'word': bias_word,
                        'context': matches[0].strip()
                    })
        
        if bias_findings:
            # Limit to top 5 bias findings to avoid overwhelming the analysis
            for finding in bias_findings[:5]:
                analysis['misleading_content'].append({
                    'code': 'BIAS',
                    'title': 'Marketing Language',
                    'reason': f"Uses subjective term '{finding['word']}' without data",
                    'word': finding['word']
                })
        
        print(f"\n📊 GRI Compliance Analysis:")
        print(f"   ❌ Missing Standards: {len(analysis['missing_standards'])}")
        print(f"   ⚠️  Misleading Content: {len(analysis['misleading_content'])}")
        print(f"   ✅ Compliant Standards: {len(analysis['compliant_standards'])}")
        
        return analysis

def load_game_state():
    """Load game state from JSON file"""
    try:
        with open(GAME_STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {'used_pdfs': [], 'all_pdfs': PDF_URLS}

def save_game_state(state):
    """Save game state to JSON file"""
    with open(GAME_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_next_pdf():
    """Get next random unused PDF"""
    state = load_game_state()
    
    # If all PDFs used, reset to allow replaying
    if len(state['used_pdfs']) >= len(PDF_URLS):
        print("\n🔄 All PDFs used! Resetting...")
        state['used_pdfs'] = []
    
    # Get unused PDFs list
    unused = [pdf for pdf in PDF_URLS if pdf not in state['used_pdfs']]
    
    # Pick random PDF from unused list
    selected = random.choice(unused)
    
    # Mark as used and save state
    state['used_pdfs'].append(selected)
    save_game_state(state)
    
    return selected

def extract_company_name(pdf_content):
    """Extract the company name from PDF content using configured LLM (or heuristic fallback)"""
    max_chars = 8000
    truncated_content = pdf_content[:max_chars]

    prompt = f"""Based on this PDF content, identify the main company name mentioned in the document.

PDF Content:
---
{truncated_content}
---

Respond with ONLY the company name, nothing else. No explanations."""

    text = llm_chat(prompt, max_tokens=100)
    if text:
        return text.strip().splitlines()[0].strip()

    # Heuristic fallback: look for capitalized multi-word company-like phrase in first lines
    for line in pdf_content.splitlines()[:40]:
        line = line.strip()
        if len(line) > 3 and len(line) < 80:
            # crude: line with 1-4 capitalized words
            words = line.split()
            if 1 <= len(words) <= 4 and all(w[:1].isupper() for w in words if w.isalpha()):
                return line
    return "Unknown Company"

def generate_words_from_pdf(pdf_content, company_name, gri_analysis, count=5):
    """Generate words and clues using Claude based on PDF content and GRI analysis"""
    max_chars = 6000
    truncated_content = pdf_content[:max_chars]
    
    # Build GRI context string
    gri_context_parts = []
    
    if gri_analysis['missing_standards']:
        missing = [f"{item['code']} - {item['title']}" for item in gri_analysis['missing_standards'][:3]]
        gri_context_parts.append(f"Missing Standards: {', '.join(missing)}")
    
    if gri_analysis['misleading_content']:
        misleading = []
        for item in gri_analysis['misleading_content'][:3]:
            if item['code'] == 'BIAS':
                misleading.append(f"Bias word '{item['word']}'")
            else:
                misleading.append(f"{item['code']} - {item['reason']}")
        gri_context_parts.append(f"Misleading: {'; '.join(misleading)}")
    
    if gri_analysis['compliant_standards']:
        compliant = [f"{item['code']} - {item['title']}" for item in gri_analysis['compliant_standards'][:3]]
        gri_context_parts.append(f"Compliant: {', '.join(compliant)}")
    
    gri_context = "\n".join(gri_context_parts) if gri_context_parts else "No GRI analysis available"
    
    prompt = f"""I have extracted text from a PDF document about {company_name}. Based on this content and GRI compliance analysis, generate {count} words for a word search game.

PDF Content:
---
{truncated_content}
---

GRI COMPLIANCE FINDINGS:
{gri_context}

For each word:
1. Extract or identify a KEY TERM from the PDF (3-8 letters MAXIMUM. uppercase)
2. Create a clue based on information from the PDF OR GRI findings (missing/misleading metrics)

CRITICAL RULES:
- DO NOT mention "{company_name}" or any variation of the company name in the clues
- Your words chosen should not be longer than the board limit. Ensure that it is 3-8 letters long.
- If your words chosen are longer than the board limit, please change the word.
- The clues should be generic enough that players have to guess which company this is
- The clues should be fun, engaging, simple, and educational
- The clues should be fill-in-the-blank style as well. Example: "A metric this report fails to disclose: _____ consumption"
- You can reference missing metrics (e.g., "A metric this report fails to disclose")
- You can highlight misleading language (e.g., "Vague term used without supporting data")
- You can reference bias words (e.g., "Subjective claim without evidence")
- Focus on metrics, initiatives, practices, or general concepts from the PDF


Format your response EXACTLY like this (one item per line, no extra text):
WORD | clue for that word

Example:
ENERGY | A metric this report fails to disclose: _____ consumption
WATER | Vague term used without supporting data

Rules: word must be 3-8 uppercase letters only. Do not include company name. No numbering, no explanations."""

    response_text = llm_chat(prompt, max_tokens=2000)
    if not response_text:
        # Heuristic fallback: derive words from GRI missing standards / bias words
        fallback_words = []
        fallback_clues = []
        for item in gri_analysis.get('missing_standards', [])[:count]:
            w = item['code'].replace('-', '')[:8].upper()
            if 3 <= len(w) <= 8:
                fallback_words.append(w)
                fallback_clues.append(f"A standard this report fails to disclose: {item['title']}")
        for item in gri_analysis.get('misleading_content', []):
            if len(fallback_words) >= count:
                break
            if item.get('code') == 'BIAS':
                w = item['word'].upper()[:8]
                if 3 <= len(w) <= 8 and w not in fallback_words:
                    fallback_words.append(w)
                    fallback_clues.append("Subjective claim without supporting data")
        # pad
        generic = [("CARBON", "A common emission metric often reported vaguely"),
                   ("WATER", "Resource consumption frequently undisclosed"),
                   ("WASTE", "Byproduct management metric"),
                   ("ENERGY", "Power usage figure often missing"),
                   ("LABOR", "Workforce metric sometimes omitted")]
        i = 0
        while len(fallback_words) < count and i < len(generic):
            w, c = generic[i]
            if w not in fallback_words:
                fallback_words.append(w)
                fallback_clues.append(c)
            i += 1
        return fallback_words[:count], fallback_clues[:count]

    lines = [line.strip() for line in response_text.split('\n') if line.strip()]

    words = []
    clues = []
    for ln in lines:
        # Expected format: WORD | clue
        if '|' in ln:
            left, right = ln.split('|', 1)
            w = re.sub(r'[^A-Za-z]', '', left.strip())
            c = right.strip()
            if 3 <= len(w) <= 8:
                words.append(w.upper())
                clues.append(c if c else "Find this term in the report")
                continue
        # Fallback: single token line treated as word with generic clue
        w = re.sub(r'[^A-Za-z]', '', ln.split()[0] if ln.split() else "")
        if 3 <= len(w) <= 8 and len(ln.split()) == 1:
            words.append(w.upper())
            clues.append("Find this term in the report")

    # pad clues if needed
    while len(clues) < len(words):
        clues.append("Find this term in the report")

    # If parsing failed entirely, use fallback words already returned earlier? Just return what we have.
    if not words:
        return [], []

    # Return limited count
    return words[:count], clues[:count]

@app.route('/')
def index():
    """Serve the game HTML"""
    return send_from_directory('.', 'game.html')


def generate_game_data():
    """Serve the next pre-generated (deterministic) game trace.

    In production, an LLM would intake a sustainability report PDF and
    generate fresh words/clues. For this demo we ship example traces so the
    app runs fully offline and deterministically.
    """
    print("\n" + "="*60)
    print("🎮 Loading next example game trace...")
    print("="*60)

    try:
        with open('traces.json', 'r') as f:
            traces = json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load traces.json: {e}")
        return None

    if not traces:
        return None

    state = load_game_state()
    idx = state.get('trace_index', 0) % len(traces)
    trace = traces[idx]

    state['trace_index'] = idx + 1
    save_game_state(state)

    print(f"📝 Company: {trace['companyName']}")
    print(f"💡 Words: {trace['words']}")
    print("\n✅ Game data ready!\n")

    return {
        'words': list(trace['words']),
        'clues': list(trace['clues']),
        'companyName': trace['companyName'],
    }


def preload_game_worker():
    """Background worker that keeps games preloaded"""
    global is_preloading
    while True:
        # Check if we need more games in the buffer
        if preloaded_games.qsize() < 2 and not is_preloading:
            with preload_lock:
                is_preloading = True
            try:
                print("🔄 Background: Preloading next game...")
                game_data = generate_game_data()
                if game_data:
                    preloaded_games.put(game_data)
                    print(f"✅ Background: Game preloaded (queue size: {preloaded_games.qsize()})")
            except Exception as e:
                print(f"⚠️ Background preload error: {e}")
            finally:
                with preload_lock:
                    is_preloading = False
        time.sleep(2)  # Check every 2 seconds for queue status


@app.route('/new-game')
def new_game():
    """Get a preloaded game or generate on-demand"""
    try:
        # Try to get a preloaded game first (instant!)
        if not preloaded_games.empty():
            print("⚡ Serving preloaded game!")
            return jsonify(preloaded_games.get())
        
        # Fallback: generate on-demand if queue is empty
        print("⏳ No preloaded game available, generating on-demand...")
        game_data = generate_game_data()
        if game_data:
            return jsonify(game_data)
        return jsonify({'error': 'Failed to generate game'}), 500
        
    except Exception as e:
        print(f"❌ Error getting game: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n🚀 Starting SUSearch Server...")
    port = int(os.getenv("PORT", "5001"))
    print(f"📍 Open your browser to: http://localhost:{port}")
    print("🎮 Game will auto-generate on page load")
    print("="*60 + "\n")
    
    # Start background preloader
    preload_thread = threading.Thread(target=preload_game_worker, daemon=True)
    preload_thread.start()
    print("🔄 Background preloader started")
    
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=True, use_reloader=False, port=port)