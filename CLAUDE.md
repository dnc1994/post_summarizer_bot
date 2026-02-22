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

The bot is split across two modules: `main.py` (Telegram wiring, handlers, state) and `summarizer.py` (Gemini call + Langfuse tracing). Prompt template lives in `prompts.py`.

**Data flow:**
1. The bot listens to Channel A via `python-telegram-bot` polling (`filters.UpdateType.CHANNEL_POST`)
2. On each post, `extract_url()` finds the first URL in the message text/caption
3. A placeholder message is immediately sent to Channel B ("⏳ Summarizing...")
4. `scrape_content()` fetches and extracts article text using `trafilatura` (`favor_recall=True` for broader coverage)
5. `summarizer.summarize()` sends up to 30,000 chars to Gemini (`gemini-3-flash-preview`) using the prompt template in `prompts.py`; wraps the call in a Langfuse generation span and returns `(summary, error, trace_id)`
6. The placeholder is edited in-place: success → HTML summary with 👍/👎 feedback buttons; failure → error message with 🔄 Retry button

**Feedback flow:**
- 👍/👎 buttons call `handle_feedback`, which scores the Langfuse trace (`user_rating` BOOLEAN) and swaps the buttons to a "rated" state with an "✏️ Add note" option
- "✏️ Add note" opens a bot DM deep-link (`t.me/bot?start=note_<message_id>`); `handle_start` parses the payload and stores `_pending_note[user_id] = message_id`; the user's next DM is captured by `handle_private_message` and scored as `user_comment` CATEGORICAL on the same trace

**Key design details:**
- Gemini model is always `gemini-3-flash-preview` — do not change unless explicitly asked
- The prompt template in `prompts.py` produces Telegram-compatible HTML (only `<b>`, `<i>`, `<u>`, `<s>`, `<a>`, `<code>`, `<pre>`, `<blockquote>` are supported by Telegram)
- `AUTHORIZED_USER_ID` optionally restricts which user's messages are processed; channel posts without a signed sender bypass this check
- Error messages are sent to Channel B (not silently dropped) so failures are visible
- Langfuse is optional: absent keys → `langfuse_client = None` → tracing and feedback scoring silently skipped; if tracing fails mid-call, summarization still succeeds but the message shows `⚠️ Tracing unavailable` and feedback buttons are omitted
- `_url_store`, `_trace_store`, `_pending_note` are in-memory dicts; they reset on bot restart — old Retry/feedback buttons degrade gracefully

**Required environment variables** (in `.env`):
- `TELEGRAM_BOT_TOKEN`
- `CHANNEL_A_ID` — must be an integer (e.g. `-100123456789`)
- `CHANNEL_B_ID`
- `GEMINI_API_KEY`
- `AUTHORIZED_USER_ID` (optional)
- `LANGFUSE_PUBLIC_KEY` (optional)
- `LANGFUSE_SECRET_KEY` (optional)
- `LANGFUSE_HOST` (optional, defaults to `https://cloud.langfuse.com`)

**Python version:** Pinned to 3.13 via `.python-version` and `runtime.txt`. Do not change — Langfuse requires Python < 3.14 due to an internal Pydantic v1 dependency.

**Deployment:** Uses `Procfile` and `runtime.txt` for Railway/Render. The bot is a long-running polling process, not a webhook server.

## Eval / Prompt Tuning Workflow

Offline hill-climbing loop for improving the prompt. No new dependencies — uses existing `google-genai`, `langfuse`, and `python-dotenv`.

```
eval/
  dump_traces.py          # Script 1: Langfuse → JSONL dataset
  gen_rubrics.py          # Script 2: Generate boolean rubrics from feedback
  autorater.py            # Script 3: Rate a candidate prompt file
  prompts/
    v1_baseline.txt       # Copy of current prompt (for reference/baseline run)
  data/
    .gitignore            # Ignores traces.jsonl and results/ (contain scraped content)
    rubrics.json          # Principle-based rubrics — human-reviewed, committed to git
    example_rubrics.jsonl # Example-specific rubrics — committed to git
```

**Workflow:**
```bash
make eval-dump                                    # Pull new traces from Langfuse
make eval-rubrics                                 # Generate rubrics (review rubrics.json after)
make eval-rate PROMPT=eval/prompts/v1_baseline.txt  # Score a candidate prompt
```

**Two rubric tiers:**
- **Principle-based** (`rubrics.json`): global, applied to every example, shows per-rubric pass rate
- **Example-specific** (`example_rubrics.jsonl`): per-trace, derived from user comments, keyed by `trace_id`

**Eval scripts use `gemini-3-flash-preview`** — same model as the production bot.

**Gitignored:** `eval/data/traces.jsonl` and `eval/data/results/` (contain scraped article content). **Committed:** `eval/data/rubrics.json` and `eval/data/example_rubrics.jsonl`.
