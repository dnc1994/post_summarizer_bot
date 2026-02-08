import os
import logging
import asyncio
import re
from urllib.parse import urlparse

import trafilatura
from google import genai
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_A_ID = os.getenv("CHANNEL_A_ID") # The ID of the channel to listen to
CHANNEL_B_ID = os.getenv("CHANNEL_B_ID") # The ID of the channel to post summaries to
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Validate config
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_A_ID, CHANNEL_B_ID, GEMINI_API_KEY]):
    logger.error("Missing one or more required environment variables: TELEGRAM_BOT_TOKEN, CHANNEL_A_ID, CHANNEL_B_ID, GEMINI_API_KEY")
    exit(1)

# Initialize Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def extract_url(text):
    """Extracts the first URL from the text."""
    url_pattern = r'(https?://\S+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

def scrape_content(url):
    """Scrapes the content of the URL using trafilatura."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            return text
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    return None

async def summarize_content(text):
    """Summarizes the text using Gemini API."""
    try:
        # You can tweak this prompt later
        prompt = f"""
        Please provide a concise and engaging summary of the following article/blog post. 
        Focus on the main takeaways and key points.
        
        Article Content:
        {text[:30000]} 
        """ 
        # Truncating to avoid token limits for very large texts, though Gemini has a large context window.
        
        response = await client.aio.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler to process messages from Channel A."""
    
    # Ensure the message is from the correct channel
    # Note: Telegram channel IDs usually start with -100
    if str(update.effective_chat.id) != str(CHANNEL_A_ID):
        return

    message_text = update.channel_post.text if update.channel_post else None
    if not message_text:
        return

    logger.info(f"Processing message from Channel A: {message_text[:50]}...")

    url = extract_url(message_text)
    if not url:
        logger.info("No URL found in message.")
        return

    logger.info(f"Found URL: {url}")
    
    # Notify Channel B (or logs) that processing started? Optional. 
    # For now, let's just do the work silently.

    article_text = scrape_content(url)
    if not article_text:
        logger.warning(f"Could not extract content from {url}")
        # Optionally send a failure message to an admin or log it
        return

    logger.info("Content extracted. Summarizing...")
    summary = await summarize_content(article_text)
    
    if summary:
        message = f"**Summary of:** {url}\n\n{summary}"
        try:
            await context.bot.send_message(chat_id=CHANNEL_B_ID, text=message, parse_mode='Markdown')
            logger.info("Summary sent to Channel B.")
        except Exception as e:
            logger.error(f"Failed to send message to Channel B: {e}")
    else:
        logger.error("Failed to generate summary.")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Filter for channel posts that contain text
    # We allow text messages (filters.TEXT) and ensure it's a channel post (Update.channel_post is handled by the handler usually, but filters help)
    handler = MessageHandler(filters.Chat(chat_id=int(CHANNEL_A_ID)) & (filters.TEXT | filters.CAPTION), process_message)
    
    # Note: python-telegram-bot treats channel posts slightly differently. 
    # We should attach the handler. 
    # However, 'filters.Chat' might not work if the bot hasn't seen the chat yet or specific integer handling.
    # A safer generic handler checks the ID inside the function or uses a broader filter.
    # Let's use a broader filter but check ID inside, but optimize with filters.Chat if possible.
    # Since CHANNEL_A_ID is env var, we cast to int.
    
    try:
        channel_a_int = int(CHANNEL_A_ID)
        # Using a raw MessageHandler that catches channel posts
        application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST & filters.Chat(chat_id=channel_a_int), process_message))
        
        logger.info(f"Bot started. Listening to Channel A ({CHANNEL_A_ID})...")
        application.run_polling()
    except ValueError:
        logger.error("CHANNEL_A_ID must be an integer (e.g., -100123456789)")
