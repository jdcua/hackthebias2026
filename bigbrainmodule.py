from anthropic import Anthropic
import re
import requests
import io
from pypdf import PdfReader
from GRI_STANDARDS_DATABASE import GRI_STANDARDS, BIAS_FLUFF_WORDS

# WARNING: Regenerate this API key immediately!
ANTHROPIC_API_KEY = "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"

# Initialize Claude API
client = Anthropic(api_key=ANTHROPIC_API_KEY)

class PDFScraper:
    def __init__(self):
        self.pdfs_processed = 0

    def download_pdf_text(self, url):
        """Downloads a PDF from a URL and extracts its text (all pages)."""
        print(f" Downloading PDF from {url}...")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            
            text = ""
            # Extract text from all pages (or limit to first 50 for speed)
            max_pages = min(50, len(reader.pages))
            for i, page in enumerate(reader.pages[:max_pages]): 
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            self.pdfs_processed += 1
            print(f" Successfully extracted text from PDF ({len(text)} chars, {max_pages} pages)")
            return text
        except Exception as e:
            print(f" Error processing {url}: {e}")
            return ""

    def read_local_pdf(self, filepath):
        """Reads a PDF from local file path and extracts its text."""
        print(f" Reading PDF from {filepath}...")
        try:
            reader = PdfReader(filepath)
            
            text = ""
            max_pages = min(50, len(reader.pages))
            for page in reader.pages[:max_pages]:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            self.pdfs_processed += 1
            print(f" Successfully extracted text from PDF ({len(text)} chars)")
            return text
        except Exception as e:
            print(f" Error reading {filepath}: {e}")
            return ""

    def clean_text(self, text):
        """Removes extra whitespace and normalizes text."""
        return re.sub(r'\s+', ' ', text).strip()

    def analyze_gri_compliance(self, pdf_content):
        """Compare PDF content against GRI standards to find missing, misleading, or compliant metrics"""
        
        print("\n Analyzing PDF against GRI Standards...")
        
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
            
            # Check if keywords from this standard appear in PDF
            for keyword in standard['keywords']:
                if keyword.lower() in pdf_lower:
                    keywords_found.append(keyword)
            
            # Check if required metrics appear in PDF
            for metric in standard['required_metrics']:
                if metric.lower() in pdf_lower:
                    metrics_found.append(metric)
            
            # Determine compliance status
            if not keywords_found and not metrics_found:
                # Completely missing
                analysis['missing_standards'].append({
                    'code': gri_code,
                    'title': standard['title'],
                    'reason': f"No keywords or metrics found for {standard['title']}"
                })
            elif keywords_found and not metrics_found:
                # Keywords mentioned but no actual metrics = misleading
                analysis['misleading_content'].append({
                    'code': gri_code,
                    'title': standard['title'],
                    'reason': f"Mentions {', '.join(keywords_found[:2])} but lacks quantitative metrics",
                    'keywords': keywords_found
                })
            elif keywords_found and metrics_found:
                # Both keywords and metrics present = compliant
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
                # Find context around the bias word
                pattern = r'(.{0,50}' + re.escape(bias_word) + r'.{0,50})'
                matches = re.findall(pattern, pdf_lower, re.IGNORECASE)
                if matches:
                    bias_findings.append({
                        'word': bias_word,
                        'context': matches[0].strip()
                    })
        
        # Add bias findings to misleading content
        if bias_findings:
            for finding in bias_findings[:5]:  # Limit to 5 examples
                analysis['misleading_content'].append({
                    'code': 'BIAS',
                    'title': 'Marketing Language',
                    'reason': f"Uses subjective term '{finding['word']}' without data",
                    'word': finding['word']
                })
        
        # Print summary
        print(f"\n GRI Compliance Analysis:")
        print(f"    Missing Standards: {len(analysis['missing_standards'])}")
        print(f"    Misleading Content: {len(analysis['misleading_content'])}")
        print(f"    Compliant Standards: {len(analysis['compliant_standards'])}")
        
        # Print details
        if analysis['missing_standards']:
            print(f"\n   Missing:")
            for item in analysis['missing_standards'][:3]:
                print(f"      • {item['code']}: {item['title']}")
        
        if analysis['misleading_content']:
            print(f"\n   Misleading:")
            for item in analysis['misleading_content'][:3]:
                if item['code'] == 'BIAS':
                    print(f"      • Bias word: '{item['word']}'")
                else:
                    print(f"      • {item['code']}: {item['reason']}")
        
        return analysis

def extract_company_name(pdf_content):
    """Extract the company name from PDF content using Claude"""
    
    # Truncate PDF content if too long
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
    
    # Truncate PDF content if too long (API has token limits)
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
1. Extract or identify a KEY TERM from the PDF (3-8 letters, uppercase)
2. Create a clue based on information from the PDF OR GRI findings (missing/misleading metrics)

CRITICAL RULES:
- DO NOT mention "{company_name}" or any variation of the company name in the clues
- The clues should be generic enough that players have to guess which company this is
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
    
    # Separate words and clues (alternating lines)
    words = []
    clues = []
    for i, line in enumerate(lines):
        if i % 2 == 0:  # Even indices are words
            words.append(line.upper())
        else:  # Odd indices are clues
            clues.append(line)
    
    return words[:count], clues[:count]

def update_html_words(html_file, new_words, new_clues, company_name):
    """Update the word list and clues in the HTML file"""
    
    # Read the HTML file
    with open(html_file, 'r') as f:
        html_content = f.read()
    
    # Update words array
    words_pattern = r'const words = \[.*?\];'
    new_words_str = '["' + '", "'.join(new_words) + '"]'
    words_replacement = f'const words = {new_words_str};'
    updated_html = re.sub(words_pattern, words_replacement, html_content, flags=re.DOTALL)
    
    # Update clues array
    clues_pattern = r'const clues = \[.*?\];'
    new_clues_str = '["' + '", "'.join(new_clues) + '"]'
    clues_replacement = f'const clues = {new_clues_str};'
    updated_html = re.sub(clues_pattern, clues_replacement, updated_html, flags=re.DOTALL)

    # Update companyName to actual company name from PDF
    companyName_pattern = r'const companyName = \[".*?"\];'
    new_companyName_str = '["' + company_name + '"]'
    companyName_replacement = f'const companyName = {new_companyName_str};'
    updated_html = re.sub(companyName_pattern, companyName_replacement, updated_html, flags=re.DOTALL)
    
    # Write back to file
    with open(html_file, 'w') as f:
        f.write(updated_html)
    
    print(f" Updated {html_file} with new words: {new_words}")
    print(f" Updated {html_file} with new clues: {new_clues}")
    print(f" Updated {html_file} with company name: {company_name}")

# Main execution
if __name__ == "__main__":
    print("🎮 PDF-Based Word Search Generator with GRI Compliance Check")
    print("=" * 60)
    
    # Ask user for PDF source
    source = input("\nEnter 'url' for PDF URL or 'file' for local PDF (or press Enter for URL): ").lower() or "url"
    
    scraper = PDFScraper()
    pdf_content = ""
    
    if source == "file":
        filepath = input("Enter PDF file path: ")
        pdf_content = scraper.read_local_pdf(filepath)
    else:
        pdf_url = input("Enter PDF URL (or press Enter for Google sustainability report): ") or \
                  "https://www.gstatic.com/gumdrop/sustainability/google-2024-environmental-report.pdf"
        pdf_content = scraper.download_pdf_text(pdf_url)
    
    if not pdf_content:
        print(" Failed to extract PDF content. Exiting.")
        exit(1)
    
    # Clean the text
    cleaned_content = scraper.clean_text(pdf_content)
    
    # Analyze GRI compliance
    gri_analysis = scraper.analyze_gri_compliance(cleaned_content)
    
    # Extract company name from PDF
    print(f"\n Identifying company from PDF...")
    company_name = extract_company_name(cleaned_content)
    print(f" Found company: {company_name}")
    
    # Generate words based on PDF content and GRI analysis
    print(f"\n Analyzing PDF and generating word search (including GRI findings)...")
    new_words, new_clues = generate_words_from_pdf(cleaned_content, company_name, gri_analysis, count=5)
    
    print(f"\n Generated words: {new_words}")
    print(f" Generated clues (company-name-free): {new_clues}\n")
    
    # Update the HTML file
    update_html_words('search.html', new_words, new_clues, company_name)
    
    print("\n Done! Open search.html to see the new word search.")
    print(f" Players will need to guess this is about: {company_name}")