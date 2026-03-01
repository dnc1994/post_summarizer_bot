# 🤖 Telegram Post Summarizer Bot 📝

A Telegram bot that monitors a source channel (**Channel A**), extracts links from posts, scrapes article content, generates AI-powered summaries, and posts them to a destination channel (**Channel B**). Comes with an offline eval workflow lets you systematically hill-climb the prompt using collected user feedback.

## ✨ Features

- **📡 Automated Monitoring:** Listens to every message in your designated source channel.
- **🔍 Smart Extraction:** Automatically detects URLs and scrapes main content with a fallback "recall" mode for high accuracy.
- **🧠 AI Summarization:** Powered by **Gemini 3 Flash Preview** for fast and intelligent summaries.
- **🎨 Rich Formatting:** Delivers summaries in Telegram-compatible HTML with bold titles, blockquotes, and bullet points.
- **🛡️ Security First:** Built-in **User ID filtering** to protect your API keys from unauthorized usage.
- **⚠️ Error Reporting:** Notifies you in Channel B if a link fails to process.
- **🔄 Retry Button:** Failed scrapes or summarizations show a Retry button directly in Channel B.
- **👍👎 Feedback Buttons:** Rate summaries inline; add free-form comments via bot DM deep-link.
- **📊 Langfuse Observability:** Optional integration — logs every generation (prompt, response, latency) and user feedback scores to [Langfuse](https://langfuse.com).
- **🧪 Eval Tooling:** Offline prompt hill-climbing loop — dump traces, generate rubrics, rate candidate prompts, and browse results in an HTML viewer.

## 📋 Prerequisites

1. **Telegram Bot Token:** Create your bot via [@BotFather](https://t.me/botfather).
2. **Gemini API Key:** Grab an API key from [Google AI Studio](https://aistudio.google.com/).
3. **Channel IDs:**
   - Add your bot as an **Admin** to both Channel A (source) and Channel B (destination).
   - **Find your ID:** Forward a message from the channel to [@userinfobot](https://t.me/userinfobot). IDs look like `-100xxxxxxxxxx`.

## 🔐 Security & User Filtering

To keep your bot safe and prevent unwanted API costs:

1. **Get your User ID:** Message [@userinfobot](https://t.me/userinfobot) to get your numerical ID.
2. **Set the Variable:** Add `AUTHORIZED_USER_ID=your_id_here` to your configuration.
3. **Result:** The bot will only process messages sent by *you*. Unauthorized attempts are silently logged.

## 💻 Local Development & Testing

1. **Clone & Enter:**
   ```bash
   git clone <your-repo-url>
   cd post_summarizer_bot
   ```

2. **Setup Environment:**
   We recommend [uv](https://github.com/astral-sh/uv):
   ```bash
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   uv pip install -r requirements.txt
   ```
   > **Note:** Python 3.13 is required (pinned via `.python-version`). `uv` will download it automatically.

3. **Configure:**
   ```bash
   cp .env.example .env
   ```
   Fill in your tokens and IDs in the `.env` file. Langfuse keys are optional.

4. **Run:**
   ```bash
   uv run python -m post_summarizer_bot.main
   ```

5. **Debug Scraping:**
   ```bash
   uv run python scripts/debug_scrape.py "https://example.com/article"
   ```

6. **Test Prompt Tuning:**
   ```bash
   uv run python scripts/test_prompt.py "https://example.com/article"
   ```

## 📊 Langfuse Observability (Optional)

The bot integrates with [Langfuse](https://langfuse.com) to log every summarization and collect user feedback. It is fully optional — the bot runs normally without it.

To enable, add to your `.env`:
```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com  # optional, this is the default
```

Each successful summarization creates a Langfuse trace containing the full prompt and response. User 👍/👎 ratings and text comments are attached as scores on the same trace.

## 🚀 Deployment

The bot is a **long-running process** and needs to stay active 24/7 to poll Telegram.

### General Requirements
- Python 3.13
- Persistent internet connection
- Environment variables (see `.env.example`)

---

### Option 1: Railway (Recommended)
1. Push your code to a GitHub repo.
2. In Railway, click "New Project" → "Deploy from GitHub repo".
3. Go to the **Variables** tab and add all keys from your `.env`.
4. Railway will use the `Procfile` and `runtime.txt` automatically.

### Option 2: Render
1. Create a **Background Worker** (not a web service).
2. Connect your GitHub repository.
3. Set the start command to: `python -m post_summarizer_bot.main`.
4. Add your environment variables in the **Environment** tab.

### Option 3: Fly.io
1. Install the Fly CLI and run `fly launch`.
2. Set secrets using `fly secrets set KEY=VALUE`.
3. Run `fly deploy`.

### Option 4: Linux VPS (Systemd)
```ini
# /etc/systemd/system/telegram-bot.service
[Unit]
Description=Telegram Summarizer Bot
After=network.target

[Service]
WorkingDirectory=/path/to/bot
ExecStart=/path/to/venv/bin/python -m post_summarizer_bot.main
EnvironmentFile=/path/to/bot/.env
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🛠️ Customization

- **Prompt Tuning:** Edit `SUMMARIZATION_PROMPT_TEMPLATE` in `post_summarizer_bot/prompts.py`. Use `scripts/test_prompt.py` to preview changes immediately.
- **Model Choice:** The model is `gemini-3-flash-preview` (set as `MODEL_NAME` in `post_summarizer_bot/main.py`).

## 📊 Eval / Prompt Tuning Workflow

An offline hill-climbing loop for systematically improving the prompt using collected feedback. Datasets are always versioned (e.g. `eval/data/v1/`).

### Usage

```bash
# 1. Pull new traces from Langfuse
make eval-dump VERSION=v1

# 2. Generate global or example-specific rubrics using LLMs (review before proceeding)
make eval-rubrics VERSION=v1

# 3. Browse traces, mark examples as eval-ready, and edit example-specific rubrics
make eval-data-viewer VERSION=v1

# 4. Score the baseline prompt
make eval-rate VERSION=v1 PROMPT=eval/prompts/v1_baseline.txt

# 5. Write a new prompt variant, then compare
make eval-rate VERSION=v1 PROMPT=eval/prompts/v2.txt
```

### HTML Eval Data Viewer

`make eval-dataviewer VERSION=v1` starts a local server and opens the browser. You can:
- Edit example-specific rubrics — saved directly to `eval/data/v1/example_rubrics.jsonl` on disk
- Toggle **"Ready for eval"** on each trace — `autorater.py` filters to only marked traces
- Delete traces or export with automatic backup

### Rubric Tiers

| Tier | Scope | Applied to | Output |
|---|---|---|---|
| **Principle-based** | Global (`global_rubrics.jsonl`) | Every example | Per-rubric pass rate |
| **Example-specific** | Per-trace (`example_rubrics.jsonl`) | Matching trace only | Overall pass rate |

## 🗺️ Future Work

- [ ] **🌐 Advanced Scraping:** Playwright/Browserless for JS-heavy sites.
- [ ] **👥 Whitelisting:** Support for multiple authorized users.
- [ ] **💬 Custom Instructions:** Tailor summaries via message captions.
- [ ] **🔌 Multi-Model Support:** Add OpenAI or Anthropic integration.

---
Built with ❤️ and Gemini / Claude 🚀
