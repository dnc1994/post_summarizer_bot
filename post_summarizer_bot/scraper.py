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
