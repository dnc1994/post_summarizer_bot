import os
import asyncio
import sys
import trafilatura
from google import genai
from dotenv import load_dotenv

from prompts import SUMMARIZATION_PROMPT_TEMPLATE

# Load environment variables
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = 'gemini-3-flash-preview'

async def test_summary(url):
    print(f"🚀 Testing summary for: {url}")
    
    # 1. Scrape
    print("📥 Scraping content...")
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        print("❌ Failed to download content.")
        return
    
    text = trafilatura.extract(downloaded, favor_recall=True)
    if not text:
        print("❌ Failed to extract text.")
        return
    
    print(f"✅ Extracted {len(text)} characters.")

    # 2. Summarize
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not found in .env file.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    
    print(f"🧠 Sending to Gemini ({MODEL_NAME})...")
    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(text=text[:30000])
    
    try:
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        summary = response.text
        
        print("
--- ✨ GENERATED SUMMARY ---")
        print(summary)
        print("----------------------------
")
        print("📝 Note: The above is HTML-formatted for Telegram.")
        
    except Exception as e:
        print(f"❌ Error during summarization: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        asyncio.run(test_summary(target_url))
    else:
        print("Usage: uv run python test_prompt.py <URL>")
