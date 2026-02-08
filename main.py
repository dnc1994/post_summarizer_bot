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
# Using gemini-3-flash-preview
MODEL_NAME = 'gemini-3-flash-preview'

def extract_url(text):
    """Extracts the first URL from the text."""
    url_pattern = r'(https?://\S+)'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None

def scrape_content(url):
    """Scrapes the content of the URL using trafilatura."""
    logger.info(f"Attempting to scrape URL: {url}")
    try:
        # Some sites block default scrapers; trafilatura's fetch_url is basic
        downloaded = trafilatura.fetch_url(url)
        
        if downloaded:
            # favor_recall=True makes extraction less strict, helpful for non-standard blogs
            text = trafilatura.extract(downloaded, favor_recall=True, include_comments=False)
            
            if text:
                logger.info(f"Successfully scraped {len(text)} characters from {url}")
                return text
            else:
                logger.warning(f"Trafilatura failed to find article content in the HTML from {url}")
                # You could log the first 500 chars of 'downloaded' here if you really need to see the HTML
        else:
            logger.warning(f"Could not download content from {url} (HTTP error or blocking)")
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    return None

async def summarize_content(text):
    """Summarizes the text using Gemini API."""
    try:
        logger.info(f"Sending content to Gemini ({MODEL_NAME})...")
        # You can tweak this prompt later
        prompt = f"""
        Please provide a concise and engaging summary of the following article/blog post. 
        Focus on the main takeaways and key points.
        
        Article Content:
        {text[:30000]} 
        """ 
        
        response = await client.aio.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        summary = response.text
        logger.info("Summary generated successfully.")
        return summary
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler to process messages from Channel A."""
    
    # Debug logging for every message received
    chat_id = update.effective_chat.id if update.effective_chat else "Unknown"
    logger.info(f"Received update from chat_id: {chat_id}")

    if update.channel_post:
        logger.info(f"Update is a channel_post from: {update.channel_post.chat.title} ({update.channel_post.chat.id})")
    elif update.message:
        logger.info(f"Update is a private/group message from: {update.message.chat.id}")

    # Check if the message is from the target channel
    if str(chat_id) != str(CHANNEL_A_ID):
        logger.info(f"Ignoring message: Chat ID {chat_id} does not match CHANNEL_A_ID {CHANNEL_A_ID}")
        return

    message_text = update.channel_post.text or update.channel_post.caption if update.channel_post else None
    if not message_text:
        logger.info("Message has no text or caption. Skipping.")
        return

    logger.info(f"Processing message from Channel A: {message_text[:100]}...")

    url = extract_url(message_text)
    if not url:
        logger.info("No URL found in message.")
        return

    logger.info(f"Found URL: {url}")
    
    try:
        article_text = scrape_content(url)
        if not article_text:
            logger.warning(f"Could not extract content from {url}")
            await context.bot.send_message(
                chat_id=CHANNEL_B_ID, 
                text=f"❌ **Error:** Could not extract article content from {url}",
                parse_mode='Markdown'
            )
            return

        summary = await summarize_content(article_text)
        
        if summary:
            message = f"**Summary of:** {url}\n\n{summary}"
            try:
                logger.info(f"Sending summary to Channel B ({CHANNEL_B_ID})...")
                await context.bot.send_message(chat_id=CHANNEL_B_ID, text=message, parse_mode='Markdown')
                logger.info("Summary successfully sent to Channel B.")
            except Exception as e:
                logger.error(f"Failed to send message to Channel B: {e}")
        else:
            logger.error("Failed to generate summary.")
            await context.bot.send_message(
                chat_id=CHANNEL_B_ID, 
                text=f"❌ **Error:** Gemini failed to generate a summary for {url}",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Unexpected error processing {url}: {e}")
        await context.bot.send_message(
            chat_id=CHANNEL_B_ID, 
            text=f"❌ **Unexpected Error:** {str(e)}\nURL: {url}",
            parse_mode='Markdown'
        )

async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch-all logger to see what's coming in."""
    logger.info(f"RAW UPDATE: {update.to_dict()}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Log when we receive ANY update to help debug
    # application.add_handler(MessageHandler(filters.ALL, log_all_updates), group=-1)

    try:
        channel_a_int = int(CHANNEL_A_ID)
        # Using a raw MessageHandler that catches channel posts
        # Note: filters.UpdateType.CHANNEL_POST is crucial for channel bots
        channel_handler = MessageHandler(filters.UpdateType.CHANNEL_POST, process_message)
        application.add_handler(channel_handler)
        
        logger.info("--- Bot Configuration ---")
        logger.info(f"Target Channel A: {CHANNEL_A_ID}")
        logger.info(f"Target Channel B: {CHANNEL_B_ID}")
        logger.info(f"Gemini Model: {MODEL_NAME}")
        logger.info("-------------------------")
        logger.info("Bot started. Polling for updates...")
        
        application.run_polling()
    except ValueError:
        logger.error("CHANNEL_A_ID must be an integer (e.g., -100123456789)")
