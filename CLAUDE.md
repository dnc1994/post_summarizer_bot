# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Planning Complex Tasks

For any complex task where plan mode is activated, always write the plan to a Markdown file before touching any code:

- **Location:** `agent_tasks/` directory at the project root
- **File name:** `YYYYMMDD-feature.md` (e.g., `20260228-eval-scripts.md`)
- **Required section:** A `## Todo` checklist in the plan that is updated as work progresses (check off items as they are completed)

This creates a paper trail, makes it easy to resume interrupted work, and allows other agents to pick up specific sub-tasks.

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
  dump_traces.py            # Langfuse → JSONL dataset
  gen_rubrics.py            # Generate boolean global rubrics from feedback (merge-safe)
  autorater.py              # Rate a candidate prompt file (filters by eval_ready)
  view_traces.py            # Terminal viewer (list + detail)
  launch_data_viewer.py     # Serve the Eval Data Viewer with direct-to-disk save
  eval_data_viewer.html     # Self-contained HTML viewer / rubric editor
  prompts/
    v1_baseline.txt         # Copy of current prompt
  data/
    .gitignore              # Ignores */traces.jsonl and */results/
    v1/                     # Example versioned dataset (created at runtime)
      traces.jsonl          #   gitignored — scraped article content
      examples.jsonl        #   committed — per-example metadata: { trace_id, eval_ready }
      global_rubrics.jsonl  #   committed — global rubrics, one per line (human-reviewed)
      example_rubrics.jsonl #   committed — per-trace rubrics from user comments
      results/              #   gitignored — per-run score reports
```

**All Makefile targets require `VERSION=`:**
```bash
make eval-dump    VERSION=v1               # Pull new traces from Langfuse
make eval-rubrics VERSION=v1               # Generate/merge rubrics into global_rubrics.jsonl
make eval-rate    VERSION=v1 PROMPT=eval/prompts/v1_baseline.txt  # Score a prompt
make eval-view    VERSION=v1               # Terminal list view
make eval-show    VERSION=v1 TRACE=<id>   # Terminal detail view for one trace
make eval-viewer  VERSION=v1               # Launch Eval Data Viewer (opens browser)
```

**Two rubric tiers:**
- **Global** (`global_rubrics.jsonl`): principle-based, applied to every example, one JSON object per line; `gen_rubrics.py` is merge-safe — re-running appends only novel statements (deduped case-insensitively)
- **Example-specific** (`example_rubrics.jsonl`): per-trace, derived from user comments, keyed by `trace_id`; `generated_from_comment` field enables idempotent re-generation without clobbering human edits

**"Ready for eval"** (`examples.jsonl`): per-example metadata committed to git. Each record: `{ "trace_id": "...", "eval_ready": true }`. Toggle in the Eval Data Viewer saves automatically. `autorater.py` filters to only eval-ready traces when this file has entries.

**Eval Data Viewer** (`make eval-viewer`): runs a local HTTP server, opens browser. Tabs: Article | Preview | Response | Prompt | Rubrics | Global Rubrics | Metadata. Supports editing example-specific rubrics and toggling "ready for eval", both saved directly to disk.

**Eval scripts use `gemini-3-flash-preview`** — same model as the production bot.

**Gitignored:** `eval/data/*/traces.jsonl` and `eval/data/*/results/` (contain scraped article content). **Committed:** `examples.jsonl`, `global_rubrics.jsonl`, and `example_rubrics.jsonl` per version.
