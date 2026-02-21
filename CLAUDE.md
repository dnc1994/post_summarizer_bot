# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup (using uv)
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Run the bot
uv run main.py

# Debug scraping for a specific URL
uv run python debug_scrape.py "https://example.com/article"

# Test prompt output end-to-end (scrape + summarize)
uv run python test_prompt.py "https://example.com/article"
```

## Architecture

This is a single-file Telegram bot (`main.py`) with one companion module (`prompts.py`).

**Data flow:**
1. The bot listens to Channel A via `python-telegram-bot` polling (`filters.UpdateType.CHANNEL_POST`)
2. On each post, `extract_url()` finds the first URL in the message text/caption
3. `scrape_content()` fetches and extracts article text using `trafilatura` (`favor_recall=True` for broader coverage)
4. `summarize_content()` sends up to 30,000 chars to Gemini (`gemini-3-flash-preview`) using the prompt template in `prompts.py`
5. The formatted HTML summary is posted to Channel B with a link back to the original article

**Key design details:**
- Gemini model is always `gemini-3-flash-preview` — do not change unless explicitly asked
- The prompt template in `prompts.py` produces Telegram-compatible HTML (only `<b>`, `<i>`, `<u>`, `<s>`, `<a>`, `<code>`, `<pre>`, `<blockquote>` are supported by Telegram)
- `AUTHORIZED_USER_ID` optionally restricts which user's messages are processed; channel posts without a signed sender bypass this check
- Error messages are sent to Channel B (not silently dropped) so failures are visible

**Required environment variables** (in `.env`):
- `TELEGRAM_BOT_TOKEN`
- `CHANNEL_A_ID` — must be an integer (e.g. `-100123456789`)
- `CHANNEL_B_ID`
- `GEMINI_API_KEY`
- `AUTHORIZED_USER_ID` (optional)

**Deployment:** Uses `Procfile` and `runtime.txt` for Railway/Render. The bot is a long-running polling process, not a webhook server.
