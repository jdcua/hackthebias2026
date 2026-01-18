from anthropic import Anthropic
import re

ANTHROPIC_API_KEY = "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"

# Initialize Claude API
client = Anthropic(api_key=ANTHROPIC_API_KEY)

def generate_words(theme="programming", count=5):
    """Generate words using Claude"""
    
    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1000,
        messages=[
            {
                "role": "user", 
                "content": f"""Generate {count} words related to {theme} for a word search game.

For each word, provide:
1. The word (3-8 letters, uppercase)
2. A clue for that word

Format your response EXACTLY like this:
WORD1
Clue for word 1
WORD2
Clue for word 2

No explanations, no numbering, just word then clue, alternating."""
            }
        ]
    )
    
    # Extract words and hints from response
    response_text = message.content[0].text
    lines = [line.strip() for line in response_text.split('\n') if line.strip()]
    
    # Separate words and hints (alternating lines)
    words = []
    clues = []
    for i, line in enumerate(lines):
        if i % 2 == 0:  # Even indices are words
            words.append(line.upper())
        else:  # Odd indices are hints
            clues.append(line)
    
    return words[:count], clues[:count]

def update_html_words(html_file, new_words, new_clues):
    """Update the word list and hints in the HTML file"""
    
    # Read the HTML file
    with open(html_file, 'r') as f:
        html_content = f.read()
    
    # Update words array
    words_pattern = r'const words = \[.*?\];'
    new_words_str = '["' + '", "'.join(new_words) + '"]'
    words_replacement = f'const words = {new_words_str};'
    updated_html = re.sub(words_pattern, words_replacement, html_content, flags=re.DOTALL)
    
    # Update clues array (if it exists in your HTML)
    clues_pattern = r'const clues = \[.*?\];'
    new_clues_str = '["' + '", "'.join(new_clues) + '"]'
    clues_replacement = f'const clues = {new_clues_str};'
    updated_html = re.sub(clues_pattern, clues_replacement, updated_html, flags=re.DOTALL)
    
    # Write back to file
    with open(html_file, 'w') as f:
        f.write(updated_html)
    
    print(f"✅ Updated {html_file} with new words: {new_words}")
    print(f"✅ Updated {html_file} with new clues: {new_clues}")

# Main execution
if __name__ == "__main__":
    # Generate words with LLM
    theme = input("Enter theme (or press Enter for 'programming'): ") or "programming"
    new_words, new_clues = generate_words(theme=theme, count=5)  # Fixed: unpack both returns
    
    print(f"\n🤖 Generated words: {new_words}")
    print(f"🤖 Generated clues: {new_clues}\n")
    
    # Update the HTML file
    update_html_words('search.html', new_words, new_clues)  # Fixed: pass both arguments
    
    print("Done! Open search.html to see the new word search.")
