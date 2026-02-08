# Telegram Post Summarizer Bot

A Telegram bot that listens to a specific channel (Channel A), extracts links from posts, scrapes the article content using `trafilatura`, generates a rich HTML summary using Google's Gemini API, and posts the summary to another channel (Channel B).

## Features

-   **Automated Monitoring:** Listens to every message in a designated Telegram channel.
-   **Smart Extraction:** Detects URLs and scrapes main content using `trafilatura` with a fallback "recall" mode for better accuracy.
-   **AI Summarization:** Uses **Gemini 3 Flash Preview** (via `google-genai` SDK) for lightning-fast and intelligent summaries.
-   **Rich Formatting:** Delivers summaries in professional HTML format, including bold titles, blockquotes for overviews, and bulleted takeaways.
-   **Security:** Built-in **User ID filtering** to prevent unauthorized usage of your API keys.
-   **Broadcasting:** Automatically forwards the polished summary to a second channel.
-   **Error Reporting:** Automatically notifies the destination channel if a link fails to process.

## Prerequisites

You need the following:

1.  **Telegram Bot Token:** Create a new bot via [BotFather](https://t.me/botfather) on Telegram.
2.  **Gemini API Key:** Get an API key from [Google AI Studio](https://aistudio.google.com/).
3.  **Channel IDs:**
    *   Add your bot to both Channel A (Source) and Channel B (Destination) as an **Admin**.
    *   To get the Channel ID: Forward a message from the channel to [userinfobot](https://t.me/userinfobot) or [JsonDumpBot](https://t.me/jsondumpbot). IDs usually start with `-100`.

## Security & User Filtering

By default, the bot listens to all messages in the configured Channel A. To prevent unauthorized usage:

1.  **Get your Telegram User ID:** Message [@userinfobot](https://t.me/userinfobot).
2.  **Set the Environment Variable:** Add `AUTHORIZED_USER_ID=your_id_here` to your configuration.
3.  **Result:** The bot will only process messages where the sender matches this ID. Unauthorized attempts are logged but ignored.

## Local Development & Testing

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd post_summarizer_bot
    ```

2.  **Install dependencies:**
    It is recommended to use [uv](https://github.com/astral-sh/uv) for environment management.
    ```bash
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    uv pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    ```bash
    cp .env.example .env
    ```
    Open `.env` and fill in your tokens and IDs.

4.  **Run the Bot:**
    ```bash
    uv run main.py
    ```

5.  **Debug Scraping:**
    If a specific URL is failing to scrape, use the included debugger:
    ```bash
    uv run python debug_scrape.py "https://example.com/article"
    ```

## Deployment on Railway

1.  **Fork/Push this repo to GitHub.**
2.  **Create a New Project on Railway:** Select "Deploy from GitHub repo".
3.  **Configure Variables:** Add the variables from your `.env` in the Railway **Variables** tab.
4.  **Deploy:** Railway will automatically build and start the bot using the provided `Procfile` and `runtime.txt`.

## Customization

-   **Prompt Tuning:** Modify the `summarize_content` function in `main.py` to change the summary's tone, length, or structure.
-   **Model Choice:** The bot currently uses `gemini-3-flash-preview`. This is documented in `GEMINI.md`.

## Future Work

-   [ ] **Multi-Model Support:** Add support for other providers like OpenAI (GPT-4o) or Anthropic (Claude).
-   [ ] **Advanced Scraping:** Integrate Browserless or Playwright to handle JavaScript-heavy websites that `trafilatura` might miss.
-   [ ] **Whitelisting:** Expand the security filter to support a list of multiple authorized User IDs.
-   [ ] **Custom Prompting per Message:** Allow users to send specific instructions alongside a link for tailored summaries.