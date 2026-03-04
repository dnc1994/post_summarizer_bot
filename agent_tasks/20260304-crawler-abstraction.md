# Crawler Abstraction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract crawling logic into a dedicated `scraper.py` module with Defuddle as primary crawler and trafilatura as fallback.

**Architecture:** Each crawler is a plain function `(url: str) -> str | None`. `scrape_content()` is the public entry point that tries crawlers in order and returns the first non-None result. `main.py` just imports `scrape_content` from the new module.

**Tech Stack:** `httpx` (transitive dep, already available), `trafilatura` (existing), Defuddle public API (`https://defuddle.md/{url-without-scheme}`)

---

### Task 1: Create `scraper.py` with both crawlers

**Files:**
- Create: `post_summarizer_bot/scraper.py`

**Step 1: Create the file**

```python
import logging
import re

import httpx
import trafilatura

logger = logging.getLogger(__name__)


def scrape_defuddle(url: str) -> str | None:
    """Fetch content via the Defuddle API (defuddle.md). Returns Markdown body or None."""
    # Strip scheme: "https://example.com/path" -> "example.com/path"
    stripped = re.sub(r'^https?://', '', url)
    api_url = f"https://defuddle.md/{stripped}"
    try:
        response = httpx.get(api_url, timeout=15, follow_redirects=True)
        response.raise_for_status()
        text = response.text.strip()
        if not text:
            logger.warning(f"Defuddle returned empty response for {url}")
            return None
        # Strip YAML frontmatter (--- ... ---)
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4:].strip()
        if not text:
            logger.warning(f"Defuddle response was only frontmatter for {url}")
            return None
        logger.info(f"Defuddle: scraped {len(text)} chars from {url}")
        return text
    except Exception as e:
        logger.warning(f"Defuddle failed for {url}: {e}")
        return None


def scrape_trafilatura(url: str) -> str | None:
    """Fetch content using trafilatura. Returns plain text or None."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning(f"Trafilatura: could not download {url}")
            return None
        text = trafilatura.extract(downloaded, favor_recall=True, include_comments=False)
        if not text:
            logger.warning(f"Trafilatura: no article content found in {url}")
            return None
        logger.info(f"Trafilatura: scraped {len(text)} chars from {url}")
        return text
    except Exception as e:
        logger.warning(f"Trafilatura failed for {url}: {e}")
        return None


_CRAWLERS = [scrape_defuddle, scrape_trafilatura]


def scrape_content(url: str) -> str | None:
    """Try each crawler in order, return first successful result or None."""
    for crawler in _CRAWLERS:
        result = crawler(url)
        if result:
            return result
    logger.error(f"All crawlers failed for {url}")
    return None
```

**Step 2: Verify the file exists**

```bash
ls post_summarizer_bot/scraper.py
```

**Step 3: Commit**

```bash
git add post_summarizer_bot/scraper.py
git commit -m "feat: add scraper.py with Defuddle primary and trafilatura fallback"
```

---

### Task 2: Wire `scraper.py` into `main.py`

**Files:**
- Modify: `post_summarizer_bot/main.py`

**Step 1: Remove `import trafilatura` from the top of `main.py` and add the new import**

Remove:
```python
import trafilatura
```

Add (after the other relative imports near the bottom of the imports block):
```python
from .scraper import scrape_content
```

**Step 2: Remove the `scrape_content` function from `main.py`**

Delete the entire function:
```python
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
```

**Step 3: Smoke-test that the module imports cleanly**

```bash
uv run python -c "from post_summarizer_bot.scraper import scrape_content; print('OK')"
```
Expected output: `OK`

**Step 4: Quick manual test against a real URL**

```bash
uv run python -c "
from post_summarizer_bot.scraper import scrape_content
text = scrape_content('https://stephango.com/vibes')
print(text[:300] if text else 'FAILED')
"
```
Expected: first 300 chars of article content (not `FAILED`).

**Step 5: Commit**

```bash
git add post_summarizer_bot/main.py
git commit -m "feat: wire scraper module into main, remove inline scrape_content"
```

---

### Task 3: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update `CLAUDE.md` architecture file list**

Replace:
```
- `main.py`: Telegram wiring, handlers, state
- `summarizer.py`: Gemini call + Langfuse tracing
```
With:
```
- `main.py`: Telegram wiring, handlers, state
- `scraper.py`: Crawler chain — Defuddle (primary) → trafilatura (fallback)
- `summarizer.py`: Gemini call + Langfuse tracing
```

**Step 2: Update `CLAUDE.md` data flow step 4**

Replace:
```
4. `scrape_content()` fetches and extracts article text using `trafilatura` (`favor_recall=True` for broader coverage)
```
With:
```
4. `scraper.scrape_content()` attempts crawlers in order: first Defuddle (`defuddle.md` API, returns Markdown), then trafilatura (`favor_recall=True`). Returns the first successful result or `None`.
```

**Step 3: Update `README.md` Smart Extraction bullet**

Replace:
```markdown
- **🔍 Smart Extraction:** Automatically detects URLs and scrapes main content with a fallback "recall" mode for high accuracy.
```
With:
```markdown
- **🔍 Smart Extraction:** Automatically detects URLs and scrapes main content via a crawler chain: [Defuddle](https://defuddle.md) (primary, Markdown output) → trafilatura (fallback).
```

**Step 4: Update `README.md` crawling limitations opening paragraph**

Replace:
```markdown
The built-in scraper (`trafilatura`) works well for standard article pages but is **not robust enough for all sites**.
```
With:
```markdown
The bot uses [Defuddle](https://defuddle.md) as its primary scraper (good for clean long-form pages) with `trafilatura` as a fallback, but this chain is **not robust enough for all sites**.
```

**Step 5: Commit**

```bash
git add CLAUDE.md README.md
git commit -m "docs: update architecture and README for crawler abstraction"
```

---

## Todo

- [ ] Task 1: Create `scraper.py`
- [ ] Task 2: Wire into `main.py`
- [ ] Task 3: Update documentation
