import trafilatura
import logging
import sys

# Enable verbose logging for trafilatura
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

def debug_url(url):
    print(f"\n--- Testing URL: {url} ---\n")
    
    # 1. Try standard fetch
    print("Step 1: Downloading HTML...")
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        print("FAIL: Could not download content. The site might be blocking the request or the URL is invalid.")
        return

    print(f"SUCCESS: Downloaded {len(downloaded)} bytes of HTML.")

    # 2. Try standard extraction
    print("\nStep 2: Extracting content (Standard)...")
    result = trafilatura.extract(downloaded)
    
    if result:
        print("SUCCESS: Content Extracted!")
        print("-" * 30)
        print(result[:1000] + ("..." if len(result) > 1000 else "")) 
        print("-" * 30)
    else:
        print("FAIL: Standard extraction returned nothing.")
        
        # 3. Try "recall" mode (less strict)
        print("\nStep 3: Trying 'favor_recall' mode (less strict)...")
        fallback = trafilatura.extract(downloaded, favor_recall=True)
        if fallback:
            print("SUCCESS: Content found using favor_recall mode.")
            print("-" * 30)
            print(fallback[:1000] + ("..." if len(fallback) > 1000 else ""))
            print("-" * 30)
        else:
            print("FAIL: Even favor_recall mode returned nothing.")
            print("\nPossible reasons:")
            print("- The site is a Single Page Application (SPA) requiring JavaScript execution.")
            print("- The content is protected by a CAPTCHA or Cloudflare.")
            print("- The site structure is extremely non-standard.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug_url(sys.argv[1])
    else:
        print("Usage: uv run python debug_scrape.py <URL>")