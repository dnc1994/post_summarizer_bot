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

5.  **🧪 Debug Scraping:**
    Test specific URLs with the debugger:
    ```bash
    uv run python debug_scrape.py "https://example.com/article"
    ```

## ☁️ Deployment on Railway

1.  **🐙 GitHub:** Push your code to a GitHub repo.
2.  **🚂 Railway:** Create a "New Project" and select your repo.
3.  **⚙️ Variables:** Add all your `.env` variables in the Railway dashboard.
4.  **🚢 Deploy:** Railway will handle the rest! Your bot will be live in minutes. 🎊

## 🛠️ Customization

-   **✍️ Prompt Tuning:** Edit `summarize_content` in `main.py` to change the summary's vibe.
-   **🤖 Model Choice:** We use `gemini-3-flash-preview`. See `GEMINI.md` for details.

## 🗺️ Future Work

-   [ ] **🔌 Multi-Model Support:** Add OpenAI or Anthropic integration.
-   [ ] **🌐 Advanced Scraping:** Playwright/Browserless for JS-heavy sites.
-   [ ] **👥 Whitelisting:** Support for multiple authorized users.
-   [ ] **💬 Custom Instructions:** Tailor summaries via message captions.

---
Built with ❤️ and Gemini 🚀
