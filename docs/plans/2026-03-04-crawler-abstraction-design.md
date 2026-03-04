# Crawler Abstraction Design

**Date:** 2026-03-04
**Status:** Approved

## Problem

`scrape_content()` is a single function in `main.py` that uses only `trafilatura`. It is not modular, and adding a new crawler requires editing unrelated bot wiring code. Defuddle (`defuddle.md`) has been identified as a better primary crawler for long-form content.

## Goal

- Add Defuddle as the primary crawler, trafilatura as fallback
- Decouple crawlers into a dedicated module so adding new ones is a one-function change
- Update documentation to reflect the new architecture

## Design

### New module: `post_summarizer_bot/scraper.py`

Each crawler is a plain function with the signature `(url: str) -> str | None`.

```
scrape_defuddle(url)     — primary; HTTP GET defuddle.md/{url-without-scheme}
scrape_trafilatura(url)  — fallback; existing trafilatura logic
scrape_content(url)      — public entry point; tries [defuddle, trafilatura] in order
```

**Defuddle API:** Strip the scheme from the URL (`https://example.com/path` → `example.com/path`) and `GET https://defuddle.md/{rest}`. Response is Markdown with YAML frontmatter. Strip the frontmatter block before returning the body text.

**Chain logic in `scrape_content`:**
1. Try each crawler in order
2. On success (non-None, non-empty result), log which crawler succeeded and return
3. On failure/exception, log the error and try the next
4. Return `None` if all crawlers fail

**No new dependencies** — HTTP calls use `httpx` (already a transitive dependency via `python-telegram-bot`).

### Changes to `main.py`

- Remove `scrape_content` function
- Remove `import trafilatura`
- Add `from .scraper import scrape_content`

### Documentation updates

- `CLAUDE.md`: Update architecture section to describe `scraper.py` and the crawler chain
- `README.md`: Update "Smart Extraction" feature bullet and the crawling limitations section to note Defuddle as the primary crawler

## Non-goals

- Env-var-driven crawler configuration (YAGNI)
- Class hierarchy / ABC (unnecessary abstraction for 2 crawlers)
- Parallel crawling (sequential fallback is sufficient)
