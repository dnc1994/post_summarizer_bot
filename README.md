# Telegram Post Summarizer Bot

A Telegram bot that listens to a specific channel (Channel A), extracts links from posts, scrapes the article content using `trafilatura`, generates a summary using Google's Gemini API, and posts the summary to another channel (Channel B).

## Features

-   **Automated Monitoring:** Listens to every message in a designated Telegram channel.
-   **Smart Extraction:** Detects URLs and scrapes main content, ignoring clutter.
-   **AI Summarization:** Uses Gemini 1.5 Flash for fast and accurate summaries.
-   **Broadcasting:** Automatically forwards the summary to a second channel.

## Prerequisites

You need the following:

1.  **Telegram Bot Token:** Create a new bot via [BotFather](https://t.me/botfather) on Telegram.
2.  **Gemini API Key:** Get an API key from [Google AI Studio](https://aistudio.google.com/).
3.  **Channel IDs:**
    *   Add your bot to both Channel A (Source) and Channel B (Destination) as an **Admin** (so it can read messages and post).
    *   To get the Channel ID:
        *   Forward a message from the channel to [userinfobot](https://t.me/userinfobot) or [JsonDumpBot](https://t.me/jsondumpbot).
        *   The ID usually looks like `-100xxxxxxxxxx`.

## Security & User Filtering

By default, the bot listens to all messages in the configured Channel A. To prevent unauthorized usage of your Gemini API key (e.g., if someone adds your bot to another group or if you want to restrict who can trigger the bot via DMs), you can enable **User ID Filtering**.

1.  **Get your Telegram User ID:**
    *   Message [@userinfobot](https://t.me/userinfobot) on Telegram.
    *   It will reply with your unique numerical ID.
2.  **Set the Environment Variable:**
    *   Add `AUTHORIZED_USER_ID=your_id_here` to your `.env` file or Railway variables.
3.  **Result:**
    *   If set, the bot will only process messages where the sender matches this ID.
    *   Unauthorized attempts are logged on the server but receive no response from the bot.
    *   If left empty/unset, the bot will process all messages in Channel A.

## Local Development & Testing

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd post_summarizer_bot
    ```

2.  **Install dependencies:**
    It is recommended to use [uv](https://github.com/astral-sh/uv) for extremely fast environment management.
    ```bash
    # Create a virtual environment and install dependencies
    uv venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    uv pip install -r requirements.txt
    ```

3.  **Configure Environment Variables:**
    Copy the example file and edit it with your credentials.
    ```bash
    cp .env.example .env
    ```
    Open `.env` and fill in:
    *   `TELEGRAM_BOT_TOKEN`
    *   `CHANNEL_A_ID`
    *   `CHANNEL_B_ID`
    *   `GEMINI_API_KEY`

4.  **Run the Bot:**
    ```bash
    uv run main.py
    ```
    Send a message with a link to Channel A. The bot should log the activity in your terminal and post a summary to Channel B.

## Deployment on Railway

This project is ready to be deployed on [Railway](https://railway.app/).

1.  **Fork/Push this repo to GitHub.**
2.  **Create a New Project on Railway:**
    *   Go to Railway Dashboard.
    *   Click "New Project" -> "Deploy from GitHub repo".
    *   Select your repository.
3.  **Configure Variables:**
    *   Once the project is created, go to the **Variables** tab.
    *   Add the following variables (same as your `.env`):
        *   `TELEGRAM_BOT_TOKEN`
        *   `CHANNEL_A_ID`
        *   `CHANNEL_B_ID`
        *   `GEMINI_API_KEY`
4.  **Deploy:**
    *   Railway usually triggers a deploy automatically after variables are set. If not, click "Deploy".
    *   The bot will start running. You can check the "Logs" tab to see its status.

## Customization

-   **Prompt Tuning:** You can modify the summarization prompt in `main.py` inside the `summarize_content` function to change the tone or length of the summary.
-   **Filters:** Adjust the filters in `main.py` if you want to support specific file types or text patterns.
