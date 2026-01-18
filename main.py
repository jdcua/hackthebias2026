from flask import Flask, jsonify, send_from_directory
from anthropic import Anthropic
import re
import requests
import io
import json
import random
import threading
from queue import Queue
import time
from pypdf import PdfReader
from GRI_STANDARDS_DATABASE import GRI_STANDARDS, BIAS_FLUFF_WORDS


ANTHROPIC_API_KEY = "test"

# Initialize Flask and Claude
app = Flask(__name__, static_folder='static')
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# PDF List - Sources for sustainability reports
# These URLs are used to fetch real-world data for the game
PDF_URLS = [
    "https://www.deloitte.com/content/dam/assets-shared/docs/about/gir/global-report-full-version.pdf",
    "https://www.ey.com/content/dam/ey-unified-site/ey-com/en-ca/about-us/documents/ey-ca-impact-report-en-2025-v1.pdf",
    "https://www.sheingroup.com/wp-content/uploads/2024/08/FINAL-SHEIN-2023-Sustainability-and-Social-Impact-Report.pdf.pdf"
    
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
    """Extract the company name from PDF content using Claude"""
    max_chars = 8000
    truncated_content = pdf_content[:max_chars]
    
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=100,
        messages=[
            {
                "role": "user", 
                "content": f"""Based on this PDF content, identify the main company name mentioned in the document.

PDF Content:
---
{truncated_content}
---

Respond with ONLY the company name, nothing else. No explanations."""
            }
        ]
    )
    
    company_name = message.content[0].text.strip()
    return company_name

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
    
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[
            {
                "role": "user", 
                "content": f"""I have extracted text from a PDF document about {company_name}. Based on this content and GRI compliance analysis, generate {count} words for a word search game.

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


Format your response EXACTLY like this:
WORD1
Clue for word 1 based on PDF content or GRI findings (without company name)
WORD2
Clue for word 2 based on PDF content or GRI findings (without company name)

No explanations, no numbering, just word then clue, alternating."""
            }
        ]
    )
    
    # Extract words and clues from response
    response_text = message.content[0].text
    lines = [line.strip() for line in response_text.split('\n') if line.strip()]
    
    # Separate words and clues (alternating lines from LLM response)
    words = []
    clues = []
    for i, line in enumerate(lines):
        if i % 2 == 0:
            words.append(line.upper()) # Ensure words are uppercase for the grid
        else:
            clues.append(line)
    
    # Return limited count
    return words[:count], clues[:count]

@app.route('/')
def index():
    """Serve the game HTML"""
    return send_from_directory('.', 'game.html')


def generate_game_data():
    """Generate game data from next random PDF (used by preloader and on-demand)"""
    print("\n" + "="*60)
    print("🎮 Generating Game Data...")
    print("="*60)
    
    # Get next PDF
    pdf_url = get_next_pdf()
    print(f"\n📌 Selected PDF: {pdf_url}")
    
    # Process PDF
    scraper = PDFScraper()
    pdf_content = scraper.download_pdf_text(pdf_url)
    
    if not pdf_content:
        return None
    
    # Clean text
    cleaned_content = scraper.clean_text(pdf_content)
    
    # Analyze GRI compliance
    gri_analysis = scraper.analyze_gri_compliance(cleaned_content)
    
    # Extract company name
    print(f"\n🔍 Identifying company from PDF...")
    company_name = extract_company_name(cleaned_content)
    print(f"✅ Found company: {company_name}")
    
    # Generate words and clues
    print(f"\n🤖 Generating word search...")
    words, clues = generate_words_from_pdf(cleaned_content, company_name, gri_analysis, count=5)
    
    print(f"\n📝 Generated words: {words}")
    print(f"💡 Generated clues: {clues}")
    print(f"\n✅ Game data ready!\n")
    
    return {
        'words': words,
        'clues': clues,
        'companyName': company_name
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
    print("📍 Open your browser to: http://localhost:5000")
    print("🎮 Game will auto-generate on page load")
    print("="*60 + "\n")
    
    # Start background preloader
    preload_thread = threading.Thread(target=preload_game_worker, daemon=True)
    preload_thread.start()
    print("🔄 Background preloader started")
    
    app.run(debug=True, port=5000)