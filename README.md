# 🤖 Telegram Post Summarizer Bot 📝

A smart Telegram bot that listens to a specific channel (**Channel A**), extracts links from posts, scrapes article content using `trafilatura`, generates rich AI-powered summaries using **Google's Gemini API**, and posts them to another channel (**Channel B**). 🚀

## ✨ Features

-   **📡 Automated Monitoring:** Listens to every message in your designated Telegram source channel.
-   **🔍 Smart Extraction:** Automatically detects URLs and scrapes main content with a fallback "recall" mode for high accuracy.
-   **🧠 AI Summarization:** Powered by **Gemini 3 Flash Preview** ⚡️ for lightning-fast and intelligent summaries.
-   **🎨 Rich Formatting:** Delivers beautiful summaries in professional HTML format with bold titles, blockquotes, and bullet points.
-   **🛡️ Security First:** Built-in **User ID filtering** to protect your API keys from unauthorized usage.
-   **📢 Auto-Broadcasting:** Automatically sends the polished summary to your destination channel.
-   **⚠️ Error Reporting:** Notifies you in the destination channel if a link fails to process, so you're never in the dark.

## 📋 Prerequisites

You'll need a few things to get started:

1.  **🤖 Telegram Bot Token:** Create your bot via [@BotFather](https://t.me/botfather).
2.  **🔑 Gemini API Key:** Grab an API key from [Google AI Studio](https://aistudio.google.com/).
3.  **🆔 Channel IDs:**
    *   Add your bot as an **Admin** 👮‍♂️ to both Channel A (Source) and Channel B (Destination).
    *   **Find your ID:** Forward a message from the channel to [@userinfobot](https://t.me/userinfobot). IDs usually look like `-100xxxxxxxxxx`.

## 🔐 Security & User Filtering

To keep your bot safe and prevent unwanted API costs:

1.  **🆔 Get your User ID:** Message [@userinfobot](https://t.me/userinfobot) to get your numerical ID.
2.  **⚙️ Set the Variable:** Add `AUTHORIZED_USER_ID=your_id_here` to your configuration.
3.  **✅ Result:** The bot will only process messages sent by *you*. Unauthorized attempts are silently logged. 🕵️‍♂️

## 💻 Local Development & Testing

1.  **📥 Clone & Enter:**
    ```bash
    git clone <your-repo-url>
    cd post_summarizer_bot
    ```

2.  **🛠️ Setup Environment:**
    We recommend using [uv](https://github.com/astral-sh/uv) ⚡️:
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    uv pip install -r requirements.txt
    ```

3.  **⚙️ Configure:**
    ```bash
    cp .env.example .env
    ```
    Fill in your tokens and IDs in the `.env` file. 📝

4.  **🚀 Run:**
    ```bash
    uv run main.py
    ```

5. **🧪 Debug Scraping:**

    Test specific URLs with the debugger:

    ```bash

    uv run python debug_scrape.py "https://example.com/article"

    ```



6. **🎯 Test Prompt Tuning:**

    Test how your changes in `prompts.py` affect the output:

    ```bash

    uv run python test_prompt.py "https://example.com/article"

    ```



## 🚀 Deployment



The bot is designed as a **long-running process**. It needs to stay active 24/7 to listen for updates from Telegram.

### 🏠 General Requirements
Regardless of where you host, you will need:
-   **Python 3.10+**
-   **Persistent Internet Connection:** To poll the Telegram API.
-   **Environment Variables:** You must configure the following in your host environment:
    - `TELEGRAM_BOT_TOKEN`
    - `CHANNEL_A_ID`
    - `CHANNEL_B_ID`
    - `GEMINI_API_KEY`
    - `AUTHORIZED_USER_ID` (Recommended)

---

### 🚂 Option 1: Railway (Recommended)
Railway is extremely easy for bot deployment:
1.  **🐙 GitHub:** Push your code to a GitHub repo.
2.  **➕ New Project:** In Railway, click "New Project" -> "Deploy from GitHub repo".
3.  **⚙️ Variables:** Go to the **Variables** tab and add all keys from your `.env`.
4.  **🚢 Deploy:** Railway will use the `Procfile` and `runtime.txt` automatically.

### ☁️ Option 2: Render
1.  Create a **Background Worker** (since this isn't a web service).
2.  Connect your GitHub repository.
3.  Set the start command to: `python main.py`.
4.  Add your environment variables in the **Environment** tab.

### 🪽 Option 3: Fly.io
1.  Install the Fly CLI and run `fly launch`.
2.  Fly will detect the project as Python.
3.  Set secrets using `fly secrets set KEY=VALUE`.
4.  Run `fly deploy`.

### 🐧 Option 4: Linux VPS (Systemd)
If you have your own server, you can run it as a service:
```ini
# /etc/systemd/system/telegram-bot.service
[Unit]
Description=Telegram Summarizer Bot
After=network.target

[Service]
WorkingDirectory=/path/to/bot
ExecStart=/path/to/venv/bin/python main.py
EnvironmentFile=/path/to/bot/.env
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🛠️ Customization

-   **✍️ Prompt Tuning:** Edit the `SUMMARIZATION_PROMPT_TEMPLATE` in `prompts.py` to change the summary's vibe, structure, or emoji usage. Use `test_prompt.py` to see your changes in action immediately.
-   **🤖 Model Choice:** We use `gemini-3-flash-preview`. See `GEMINI.md` for details.

## 🗺️ Future Work

- [ ] **📊 Observability & Evaluation:** Integrate with tools like **Langfuse** to log prompts, responses, and latency.

- [ ] **👍 User Feedback:** Implement Telegram inline buttons (e.g., 👍/👎) to collect feedback on summaries, enabling offline evaluation and "quality hill climbing" for prompt optimization.

- [ ] **🔌 Multi-Model Support:** Add OpenAI or Anthropic integration.


-   [ ] **🌐 Advanced Scraping:** Playwright/Browserless for JS-heavy sites.
-   [ ] **👥 Whitelisting:** Support for multiple authorized users.
-   [ ] **💬 Custom Instructions:** Tailor summaries via message captions.

---
Built with ❤️ and Gemini 🚀