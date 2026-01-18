import requests
import io
import re
from pypdf import PdfReader

class PDFScraper:
    def __init__(self):
        self.pdfs_processed = 0

    def download_pdf_text(self, url):
        """Downloads a PDF from a URL and extracts its text (all pages)."""
        print(f"Downloading PDF from {url}...")
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            
            f = io.BytesIO(response.content)
            reader = PdfReader(f)
            
            text = ""
            # Extract text from all pages
            for page in reader.pages: 
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            self.pdfs_processed += 1
            print(f"✅ Successfully extracted text from PDF ({self.pdfs_processed} processed)")
            return text
        except Exception as e:
            print(f"❌ Error processing {url}: {e}")
            return ""

    def read_local_pdf(self, filepath):
        """Reads a PDF from local file path and extracts its text."""
        print(f"Reading PDF from {filepath}...")
        try:
            reader = PdfReader(filepath)
            
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            self.pdfs_processed += 1
            print(f"✅ Successfully extracted text from PDF ({self.pdfs_processed} processed)")
            return text
        except Exception as e:
            print(f"❌ Error reading {filepath}: {e}")
            return ""

    def clean_text(self, text):
        """Removes extra whitespace and normalizes text."""
        return re.sub(r'\s+', ' ', text).strip()

    def split_into_sentences(self, text):
        """Splits text into sentences (filters out very short ones)."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s) > 30]

    def search_keywords(self, text, keywords):
        """
        Searches for keywords in text.
        Returns dict with keyword matches and relevant sentences.
        """
        text_lower = text.lower()
        sentences = self.split_into_sentences(text)
        
        results = {
            'found_keywords': [],
            'relevant_sentences': []
        }
        
        for keyword in keywords:
            if keyword.lower() in text_lower:
                results['found_keywords'].append(keyword)
        
        for sentence in sentences:
            if any(kw.lower() in sentence.lower() for kw in keywords):
                results['relevant_sentences'].append(sentence)
        
        return results

    def extract_metrics(self, text, metric_patterns):
        """
        Extracts numerical metrics from text based on patterns.
        
        Args:
            text: The text to search
            metric_patterns: List of metric units to look for (e.g., ['tons', 'kwh', '%'])
        
        Returns:
            List of tuples: (value, metric, sentence)
        """
        sentences = self.split_into_sentences(text)
        metrics_found = []
        
        for sentence in sentences:
            sent_lower = sentence.lower()
            
            for metric in metric_patterns:
                # Pattern: number (int/float) + optional space + metric
                # Matches: "1,000.50 tons", "50%", "3.5 kwh"
                pattern = r'(\d+(?:,\d+)*(?:\.\d+)?\s*' + re.escape(metric.lower()) + r')'
                match = re.search(pattern, sent_lower)
                
                if match:
                    metrics_found.append({
                        'value': match.group(1),
                        'metric': metric,
                        'sentence': sentence
                    })
        
        return metrics_found


# Usage Examples
if __name__ == "__main__":
    scraper = PDFScraper()
    
    # Example 1: Download and extract from URL
    pdf_url = "https://www.gstatic.com/gumdrop/sustainability/google-2024-environmental-report.pdf"
    text = scraper.download_pdf_text(pdf_url)
    
    if text:
        # Clean the text
        cleaned = scraper.clean_text(text)
        print(f"\nExtracted {len(cleaned)} characters")
        
        # Search for keywords
        keywords = ['emissions', 'carbon', 'renewable', 'waste']
        results = scraper.search_keywords(cleaned, keywords)
        print(f"\nFound keywords: {results['found_keywords']}")
        print(f"Relevant sentences: {len(results['relevant_sentences'])}")
        
        # Extract metrics
        metrics = scraper.extract_metrics(cleaned, ['tons', 'kwh', '%', 'mwh'])
        print(f"\nFound {len(metrics)} metrics:")
        for m in metrics[:3]:  # Show first 3
            print(f"  - {m['value']} in: {m['sentence'][:100]}...")
    
    # Example 2: Read local PDF file
    # text = scraper.read_local_pdf("path/to/your/file.pdf")