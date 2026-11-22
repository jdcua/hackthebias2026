
import requests
import io
import re
import random
from pypdf import PdfReader
from gri_standards import GRI_STANDARDS, BIAS_FLUFF_WORDS

# Example URLs of sustainability reports
DEFAULT_URLS = [
    "https://www.gstatic.com/gumdrop/sustainability/google-2024-environmental-report.pdf",
    "https://query.prod.cms.rt.microsoft.com/cms/api/am/binary/RW1lMj" 
]

OMISSION_TEMPLATES = [
    "Surprisingly, this report fails to mention _______ standards significantly.",
    "The audit reveals a lack of verified data on _______.",
    "Investors looking for _______ metrics will be disappointed here.",
    "Unlike peers, this company omits standard _______ disclosures.",
    "A key gap in this report is the absence of _______ data."
]

BIAS_TEMPLATES = [
    "The report subjectively claims to be '_______' without data.",
    "Market bias detected: using terms like '_______' lacks proof.",
    "The text relies on fluff words like '_______' instead of facts.",
    "Ambiguous language found: describing efforts as '_______' is vague.",
    "Bias Alert: The company describes itself as '_______' subjectively."
]

FACT_TEMPLATES = [
    "The report cites a metric of {val} regarding _______.",
    "Official data shows {val} related to _______ usage.",
    "They disclosed {val} in their _______ accounting.",
    "A verified figure of {val} was reported for _______.",
    "Audit confirmation: {val} linked to _______ performance."
]

class SustainabilityAuditor:
    def __init__(self):
        self.pdfs_processed = 0

    def download_pdf_text(self, url):
        """Downloads a PDF from a URL and extracts its text (all pages)."""
        print(f"Downloading report from {url}...")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            
            text = ""
            # Sampling first 50 pages is usually enough for key metrics to save time
            # but user wanted "full report". We'll stick to a reasonable limit for speed in this demo
            # or just all pages if speed isn't an issue. Let's do all.
            for page in reader.pages: 
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            self.pdfs_processed += 1
            return text
        except Exception as e:
            print(f"Error processing {url}: {e}")
            return ""

    def clean_text(self, text):
        return re.sub(r'\s+', ' ', text).strip()

    def split_into_sentences(self, text):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s) > 30]

    def extract_value_context(self, sentence, keywords, metrics):
        """
        Attempts to find a number/unit pair and the relevant keyword in the sentence.
        Returns (value_str, keyword_found) or None.
        """
        sent_lower = sentence.lower()
        
        # Find which keyword matched
        matched_kw = None
        for kw in keywords:
            if kw in sent_lower:
                matched_kw = kw
                break
        
        if not matched_kw: return None

        # Find which metric matched
        # Regex to capture number + space + metric (approximate)
        # e.g. "50 tons", "100%", "3.5 mwh"
        for metric in metrics:
            # Pattern: number (int/float) + optional space + metric
            # \d+(?:,\d+)*(?:\.\d+)? matches 1,000.50 etc
            pattern = r'(\d+(?:,\d+)*(?:\.\d+)?\s*' + re.escape(metric) + r')'
            match = re.search(pattern, sent_lower)
            if match:
                return match.group(1), matched_kw
        
        # Fallback: look for just a percentage if relevant? 
        # For simplicity, strict metric matching
        return None

    def audit_report(self, text, report_name):
        print(f"\nScanning {report_name} against GRI Standards...")
        text_lower = text.lower()
        sentences = self.split_into_sentences(text)
        
        findings = []

        # 1. CHECK GRI COVERAGE & FACTS
        for gri_code, data in GRI_STANDARDS.items():
            found_keywords = False
            relevant_sentences = []
            
            # Check for keyword coverage
            for kw in data['keywords']:
                if kw in text_lower:
                    found_keywords = True
                    break
            
            # Collect potential fact sentences
            for s in sentences:
                if any(kw in s.lower() for kw in data['keywords']):
                    relevant_sentences.append(s)

            if found_keywords:
                # Try to extract a specific fact for a clue
                fact_found = False
                random.shuffle(relevant_sentences)
                
                for s in relevant_sentences:
                    result = self.extract_value_context(s, data['keywords'], data['required_metrics'])
                    if result:
                        val_str, kw_used = result
                        # Create template-based clue
                        template = random.choice(FACT_TEMPLATES)
                        # We want to fill in the blank for the TOPIC/Standard-ish word
                        # But the user wants the blank to be "sustainability theme words".
                        # Let's blank out the KEYWORD or the CONCEPT.
                        # The code essentially mapped "theme words" earlier. 
                        # This auditor maps GRI topics.
                        # We will blank out the keyword found (e.g. "emissions", "waste").
                        
                        clue = template.format(val=val_str).replace("_______", "_______")
                        # Wait, the template has _______ hardcoded as the place for the keyword.
                        # But we need to make sure the keyword fits contextually in the blank?
                        # Actually, the template says "regarding _______."
                        # So if keyword is "emissions", "regarding emissions." works.
                        
                        # We need to preserve the finding logic
                        findings.append({
                            "type": "FACT",
                            "code": gri_code,
                            "word": kw_used.upper(), # The word to find in wordsearch
                            "clue": template.format(val=val_str), # Template already has _______
                            "original": s
                        })
                        fact_found = True
                        break # One fact per GRI code per report is enough diversity
            else:
                # OMISSION
                # Pick a missing keyword for the "Word"
                # e.g. "BIODIVERSITY"
                missing_word = data['keywords'][0].upper()
                template = random.choice(OMISSION_TEMPLATES)
                
                findings.append({
                    "type": "OMISSION",
                    "code": gri_code,
                    "word": missing_word,
                    "clue": template, # Template handles the _______
                    "original": "N/A"
                })

        # 2. DETECT BIAS
        bias_sentences = []
        for s in sentences:
            if any(w in s.lower() for w in BIAS_FLUFF_WORDS) and not re.search(r'\d', s):
                bias_sentences.append(s)
        
        if bias_sentences:
            s = random.choice(bias_sentences)
            found_fluff = [w for w in BIAS_FLUFF_WORDS if w in s.lower()][0]
            template = random.choice(BIAS_TEMPLATES)
            
            findings.append({
                "type": "BIAS",
                "code": "MARKETING",
                "word": found_fluff.upper(),
                "clue": template,
                "original": s
            })

        return findings

    def generate_game(self, urls=DEFAULT_URLS):
        all_findings = []
        for i, url in enumerate(urls):
            clean = self.clean_text(self.download_pdf_text(url))
            if clean:
                all_findings.extend(self.audit_report(clean, f"Report {i+1}"))

        # Selection Logic: Unique clues, <15 words, varied types
        final_clues = []
        seen_words = set()
        
        # Shuffle to mix reports
        random.shuffle(all_findings)
        
        for f in all_findings:
            if len(final_clues) >= 5: break
            
            # Avoid duplicate words in the puzzle
            if f['word'] in seen_words: continue
            
            # Ensure clue is short (Templates are designed to be short, but check)
            if len(f['clue'].split()) > 15: continue
            
            final_clues.append(f)
            seen_words.add(f['word'])

        print("\n=== REFINED ESG CLUES (Short & Varied) ===")
        print("------------------------------------------")
        for item in final_clues:
            print(f"WORD     : {item['word']}")
            print(f"TYPE     : {item['type']}")
            print(f"CLUE     : {item['clue']}")
            print("-" * 40)

if __name__ == "__main__":
    auditor = SustainabilityAuditor()
    auditor.generate_game()
