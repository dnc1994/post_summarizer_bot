import os
import logging
import re

import trafilatura
from google import genai
from langfuse import Langfuse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, CommandHandler, filters
from dotenv import load_dotenv

import summarizer

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_A_ID = os.getenv("CHANNEL_A_ID") # The ID of the channel to listen to
CHANNEL_B_ID = os.getenv("CHANNEL_B_ID") # The ID of the channel to post summaries to
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID") # Optional: Filter by user ID

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Silence noisy library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Validate config
if not all([TELEGRAM_BOT_TOKEN, CHANNEL_A_ID, CHANNEL_B_ID, GEMINI_API_KEY]):
    logger.error("Missing one or more required environment variables: TELEGRAM_BOT_TOKEN, CHANNEL_A_ID, CHANNEL_B_ID, GEMINI_API_KEY")
    exit(1)

# Initialize Gemini
client = genai.Client(api_key=GEMINI_API_KEY)
# Using gemini-3-flash-preview
MODEL_NAME = 'gemini-3-flash-preview'

# Initialize Langfuse (optional — gracefully disabled when keys are absent)
langfuse_client: Langfuse | None = None
if os.getenv("LANGFUSE_SECRET_KEY") and os.getenv("LANGFUSE_PUBLIC_KEY"):
    langfuse_client = Langfuse(
        public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    logger.info("Langfuse tracing enabled.")
else:
    logger.info("Langfuse keys not set — tracing disabled.")

# Maps message_id → url for retry button functionality.
# Resets on bot restart; old retry buttons will fail gracefully with a user-visible error.
_url_store: dict[int, str] = {}

# Maps message_id → Langfuse trace_id for feedback scoring.
_trace_store: dict[int, str] = {}

# Maps user_id → message_id for the DM note flow.
_pending_note: dict[int, int] = {}

# Bot username; set at startup via post_init.
BOT_USERNAME: str = ""


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
        else:
            logger.warning(f"Could not download content from {url} (HTTP error or blocking)")
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
    return None

def _retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Retry", callback_data="retry")]])

def _feedback_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍", callback_data="fb:up"),
        InlineKeyboardButton("👎", callback_data="fb:down"),
    ]])

def _rated_keyboard(was_positive: bool) -> InlineKeyboardMarkup:
    label = "✅ 👍" if was_positive else "✅ 👎"
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(label, callback_data="fb:noop"),
        InlineKeyboardButton("✏️ Add note", callback_data="fb:note"),
    ]])

async def _process_url(url: str, message_id: int, bot) -> None:
    """Scrape and summarize url, editing the placeholder message in place."""
    article_text = scrape_content(url)
    if not article_text:
        await bot.edit_message_text(
            chat_id=CHANNEL_B_ID, message_id=message_id, parse_mode='HTML',
            text=f"❌ <b>Scraping Failed</b>\n\nCould not extract article content.\n\n🔗 {url}",
            reply_markup=_retry_keyboard(),
        )
        return

    summary, error, trace_id = await summarizer.summarize(
        client, MODEL_NAME, article_text,
        langfuse_client=langfuse_client, url=url,
    )
    if summary:
        tracing_failed = langfuse_client is not None and trace_id is None
        if trace_id:
            _trace_store[message_id] = trace_id
        footer = f"{summary}\n\n---\n🔗 <b><a href=\"{url}\">Read Full Article</a></b> ✨"
        if tracing_failed:
            footer += "\n<i>⚠️ Tracing unavailable for this message.</i>"
        await bot.edit_message_text(
            chat_id=CHANNEL_B_ID, message_id=message_id, parse_mode='HTML',
            text=footer,
            reply_markup=_feedback_keyboard() if trace_id else None,
        )
    else:
        await bot.edit_message_text(
            chat_id=CHANNEL_B_ID, message_id=message_id, parse_mode='HTML',
            text=f"❌ <b>Summarization Failed</b>\n\n{error}\n\n🔗 {url}",
            reply_markup=_retry_keyboard(),
        )

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler to process messages from Channel A."""

    # 1. Security Check: User ID Filtering
    if AUTHORIZED_USER_ID:
        # For channel posts, effective_user might be None or represent the channel.
        # However, if 'from_user' is present (e.g. in signed posts or if bot is used in groups/DMs), we check it.
        sender = update.effective_user
        if sender and str(sender.id) != str(AUTHORIZED_USER_ID):
            logger.warning(f"Unauthorized access attempt by User ID: {sender.id} ({sender.username})")
            return
        elif not sender and update.channel_post:
            # Channel posts don't always have a 'user' unless signed.
            # If AUTHORIZED_USER_ID is set, we might want to be careful.
            # For now, we'll assume if it's from the target channel, it's okay,
            # UNLESS you specifically want to filter who posts to that channel (if signed).
            pass

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

    # Send placeholder immediately
    placeholder = await context.bot.send_message(
        chat_id=CHANNEL_B_ID,
        text=f"⏳ <b>Summarizing...</b>\n\n🔗 {url}",
        parse_mode='HTML',
    )
    _url_store[placeholder.message_id] = url

    try:
        await _process_url(url, placeholder.message_id, context.bot)
    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        await context.bot.edit_message_text(
            chat_id=CHANNEL_B_ID, message_id=placeholder.message_id, parse_mode='HTML',
            text=f"❌ <b>Unexpected Error</b>\n\n{e}\n\n🔗 {url}",
            reply_markup=_retry_keyboard(),
        )

async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the Retry inline button press."""
    query = update.callback_query
    await query.answer()  # acknowledge button press; clears the loading indicator

    message_id = query.message.message_id
    url = _url_store.get(message_id)
    if not url:
        await query.answer("Original URL not found — please re-post the link.", show_alert=True)
        return

    await query.edit_message_text(
        text=f"⏳ <b>Retrying summarization...</b>\n\n🔗 {url}",
        parse_mode='HTML',
    )
    try:
        await _process_url(url, message_id, context.bot)
    except Exception as e:
        logger.error(f"Unexpected error retrying {url}: {e}")
        await context.bot.edit_message_text(
            chat_id=CHANNEL_B_ID, message_id=message_id, parse_mode='HTML',
            text=f"❌ <b>Unexpected Error</b>\n\n{e}\n\n🔗 {url}",
            reply_markup=_retry_keyboard(),
        )

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 👍/👎 feedback and 'Add note' inline button presses."""
    query = update.callback_query
    action = query.data.split(":")[1]  # "up" | "down" | "note" | "noop"

    if action == "noop":
        await query.answer()
        return

    message_id = query.message.message_id

    if action == "note":
        _pending_note[query.from_user.id] = message_id
        logger.info(f"Note flow started: user_id={query.from_user.id} message_id={message_id}")
        await query.answer(url=f"https://t.me/{BOT_USERNAME}?start=note_{message_id}")
        return

    await query.answer()
    was_positive = action == "up"
    trace_id = _trace_store.get(message_id)
    if trace_id and langfuse_client:
        langfuse_client.create_score(
            trace_id=trace_id,
            name="user_rating",
            value=1 if was_positive else 0,
            data_type="BOOLEAN",
        )
        logger.info(f"Langfuse score recorded: trace_id={trace_id} user_rating={'up' if was_positive else 'down'}")
    elif not trace_id:
        logger.warning(f"Langfuse score skipped: no trace_id for message_id={message_id}")
    await query.edit_message_reply_markup(reply_markup=_rated_keyboard(was_positive))

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start in DMs — used to receive the note deep-link from the feedback flow."""
    args = context.args
    if args and args[0].startswith("note_"):
        try:
            message_id = int(args[0].removeprefix("note_"))
        except ValueError:
            return
        _pending_note[update.effective_user.id] = message_id
        await update.message.reply_text("Got it! Please type your feedback for this summary:")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Collect free-form feedback text in a DM after the note flow is started."""
    user_id = update.effective_user.id
    message_id = _pending_note.pop(user_id, None)
    if message_id is None:
        return

    trace_id = _trace_store.get(message_id)
    if trace_id and langfuse_client:
        langfuse_client.create_score(
            trace_id=trace_id,
            name="user_comment",
            value=update.message.text,
            data_type="CATEGORICAL",
        )
        logger.info(f"Langfuse score recorded: trace_id={trace_id} user_comment={update.message.text!r}")
    elif not trace_id:
        logger.warning(f"Langfuse score skipped: no trace_id for message_id={message_id}")
    await update.message.reply_text("Thanks for the feedback! It's been recorded. ✅")

async def log_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catch-all logger to see what's coming in."""
    logger.info(f"RAW UPDATE: {update.to_dict()}")

async def post_init(application) -> None:
    """Capture bot username at startup for use in deep-links."""
    global BOT_USERNAME
    me = await application.bot.get_me()
    BOT_USERNAME = me.username
    logger.info(f"Bot username: @{BOT_USERNAME}")

if __name__ == '__main__':
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Log when we receive ANY update to help debug
    # application.add_handler(MessageHandler(filters.ALL, log_all_updates), group=-1)

    try:
        int(CHANNEL_A_ID)
        application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, process_message))
        application.add_handler(CallbackQueryHandler(handle_retry, pattern="^retry$"))
        application.add_handler(CallbackQueryHandler(handle_feedback, pattern="^fb:"))
        application.add_handler(CommandHandler("start", handle_start))
        application.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_private_message,
        ))

        logger.info("--- Bot Configuration ---")
        logger.info(f"Target Channel A: {CHANNEL_A_ID}")
        logger.info(f"Target Channel B: {CHANNEL_B_ID}")
        logger.info(f"Gemini Model: {MODEL_NAME}")
        logger.info("-------------------------")
        logger.info("Bot started. Polling for updates...")

        application.run_polling()
    except ValueError:
        logger.error("CHANNEL_A_ID must be an integer (e.g., -100123456789)")
