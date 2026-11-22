import requests
import io
import re
import random
from pypdf import PdfReader

# Example URLs of sustainability reports
DEFAULT_URLS = [
    "https://www.gstatic.com/gumdrop/sustainability/google-2024-environmental-report.pdf",
    "https://query.prod.cms.rt.microsoft.com/cms/api/am/binary/RW1lMj" 
]

THEME_WORDS = [
    "CARBON", "EMISSIONS", "WATER", "ENERGY", "WASTE", 
    "CLIMATE", "RENEWABLE", "NET-ZERO", "BIODIVERSITY", "CIRCULAR"
]

BIAS_INDICATORS = [
    "proud", "leader", "committed", "vision", "believe", "dedication", 
    "best", "forefront", "innovative", "unique", "excellence"
]

# Common standards topics to check for absence
STANDARD_CHECKLIST = {
    "BIODIVERSITY": ["biodiversity", "species", "habitat", "ecosystem", "nature"],
    "HUMAN RIGHTS": ["human rights", "forced labor", "child labor", "trafficking", "modern slavery"],
    "SCOPE 3": ["scope 3", "indirect emissions", "supply chain emissions", "value chain"],
    "WATER RECYCLING": ["water recycling", "recycled water", "water reuse", "effluent"],
    "GENDER PAY": ["gender pay", "pay gap", "equal pay", "remuneration"]
}

def download_pdf_text(url):
    """Downloads a PDF from a URL and extracts its text."""
    print(f"Downloading report from {url}...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        f = io.BytesIO(response.content)
        reader = PdfReader(f)
        
        text = ""
        # Limit pages for speed
        for page in reader.pages[:40]: 
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return ""

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s) > 20]

def get_sentence_type(sentence):
    has_number = bool(re.search(r'\d+%|\$\d+|\d{4}', sentence))
    has_bias = any(word in sentence.lower() for word in BIAS_INDICATORS)
    
    types = []
    if has_number:
        types.append("FACT")
    if has_bias:
        types.append("BIAS")
    return types

def find_missing_standards(text):
    """Checks which standards are NOT mentioned in the text."""
    missing = []
    text_lower = text.lower()
    
    for topic, keywords in STANDARD_CHECKLIST.items():
        found = False
        for kw in keywords:
            if kw in text_lower:
                found = True
                break
        if not found:
            missing.append(topic)
    return missing

def generate_game_content(urls=DEFAULT_URLS):
    all_text = ""
    report_texts = [] # Store individual texts for "missing" analysis per report if needed, 
                      # but simplest is to treat all as one corpus or check them individually.
                      # Let's check them individually to find *a* report that missed something.
    
    combined_missing_clues = []
    
    print("Fetching and analyzing reports...")
    
    for url in urls:
        raw_text = download_pdf_text(url)
        clean = clean_text(raw_text)
        if not clean: continue
        all_text += clean + " "
        
        # Check for missing standards in this specific report
        missing_topics = find_missing_standards(clean)
        for topic in missing_topics:
            # Create a clue about this omission
            # We don't want to over-generate, just store potential clues
            clue_text = f"One analysed report failed to significantly mention _______ standards."
            combined_missing_clues.append({
                "word": topic,
                "clue": clue_text,
                "types": "MISSING STANDARD",
                "original": "N/A"
            })
            
    if not all_text.strip():
        print("No text extracted.")
        return

    sentences = split_into_sentences(all_text)
    found_clues = {} 
    
    print("Scanning for facts and biases...")
    
    for sentence in sentences:
        sentence_upper = sentence.upper()
        for word in THEME_WORDS:
            if re.search(r'\b' + word + r'\b', sentence_upper):
                stypes = get_sentence_type(sentence)
                if stypes:
                    if word not in found_clues:
                        found_clues[word] = []
                    found_clues[word].append((sentence, stypes))

    # We need 5 words total.
    # Strategy: Pick 1-2 "Missing" clues if available, and the rest Fact/Bias.
    
    final_output = []
    
    # Try to add missed standard clues
    unique_missing = {i['word']: i for i in combined_missing_clues}
    missing_words = list(unique_missing.keys())
    
    # Randomly pick up to 2 missing standards if available
    num_missing_to_pick = min(2, len(missing_words))
    if num_missing_to_pick > 0:
        picked_missing = random.sample(missing_words, num_missing_to_pick)
        for pm in picked_missing:
            final_output.append(unique_missing[pm])
    
    # Fill the rest with normal words
    remaining_slots = 5 - len(final_output)
    available_words = [w for w in found_clues.keys() if len(found_clues[w]) > 0]
    
    if len(available_words) < remaining_slots:
        selected_words = available_words
    else:
        selected_words = random.sample(available_words, remaining_slots)
        
    for word in selected_words:
        options = found_clues[word]
        short_options = [opt for opt in options if len(opt[0]) < 200]
        if not short_options: short_options = options
        
        picked_sentence, picked_types = random.choice(short_options)
        clue = re.sub(r'\b' + word + r'\b', "_______", picked_sentence, flags=re.IGNORECASE)
        
        final_output.append({
            "word": word,
            "clue": clue,
            "types": ", ".join(picked_types),
            "original": picked_sentence
        })

    print("\n=== GENERATED SUSTAINABILITY CLUES ===")
    print("--------------------------------------")
    for item in final_output:
        print(f"THEME WORD: {item['word']}")
        print(f"CATEGORY  : {item['types']}")
        print(f"CLUE      : {item['clue']}")
        print("-" * 40)

if __name__ == "__main__":
    generate_game_content()
