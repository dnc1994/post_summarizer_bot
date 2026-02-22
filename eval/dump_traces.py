"""
dump_traces.py — Pull traces from Langfuse and append new ones to eval/data/traces.jsonl.

Usage:
    uv run python eval/dump_traces.py [--limit N]

Idempotent: skips trace IDs already present in traces.jsonl.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"
TRACES_FILE = DATA_DIR / "traces.jsonl"


def load_existing_ids() -> set[str]:
    if not TRACES_FILE.exists():
        return set()
    ids = set()
    with open(TRACES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ids.add(json.loads(line)["trace_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return ids


def get_langfuse_client():
    from langfuse import Langfuse

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not public_key or not secret_key:
        print("Error: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def extract_scores(scores: list) -> dict:
    """Extract user_rating and user_comment from Langfuse scores list."""
    result = {"user_rating": None, "user_comment": None}
    for score in scores:
        name = getattr(score, "name", None)
        if name == "user_rating":
            result["user_rating"] = getattr(score, "value", None)
        elif name == "user_comment":
            result["user_comment"] = getattr(score, "string_value", None) or getattr(score, "value", None)
    return result


def fetch_trace_record(lf, trace_id: str, retries: int = 3) -> dict | None:
    """Fetch a single trace and return a flat record dict, or None if unusable.

    Uses trace.input / trace.output / trace.observations (already embedded in
    the full trace response) — no separate observations.get_many() call needed.
    """
    trace = None
    for attempt in range(retries):
        try:
            trace = lf.api.trace.get(trace_id)
            break
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  Retrying trace {trace_id} in {wait}s ({e})...", flush=True)
                time.sleep(wait)
            else:
                print(f"  Warning: could not fetch trace {trace_id}: {e}", file=sys.stderr)
                return None

    # Prompt and response live directly on the trace
    prompt_text = getattr(trace, "input", None)
    if prompt_text is not None and not isinstance(prompt_text, str):
        prompt_text = str(prompt_text)

    response_text = getattr(trace, "output", None)
    if response_text is not None and not isinstance(response_text, str):
        response_text = str(response_text)

    # URL is in trace.metadata; fall back to first observation's metadata
    url = None
    trace_meta = getattr(trace, "metadata", None) or {}
    if isinstance(trace_meta, dict):
        url = trace_meta.get("url")

    if url is None:
        for obs in (getattr(trace, "observations", None) or []):
            obs_meta = getattr(obs, "metadata", None) or {}
            if isinstance(obs_meta, dict) and obs_meta.get("url"):
                url = obs_meta["url"]
                break

    # Extract article_text: everything after the last "Article Content:\n"
    article_text = None
    if prompt_text:
        marker = "Article Content:\n"
        idx = prompt_text.rfind(marker)
        if idx != -1:
            article_text = prompt_text[idx + len(marker):].strip()

    scores = getattr(trace, "scores", []) or []
    score_data = extract_scores(scores)

    timestamp = getattr(trace, "timestamp", None)
    if timestamp is not None:
        timestamp = timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp)

    return {
        "trace_id": trace_id,
        "url": url,
        "article_text": article_text,
        "prompt": prompt_text,
        "response": response_text,
        "user_rating": score_data["user_rating"],
        "user_comment": score_data["user_comment"],
        "timestamp": timestamp,
    }


def main():
    parser = argparse.ArgumentParser(description="Dump Langfuse traces to JSONL dataset.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of new traces to fetch")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    lf = get_langfuse_client()
    existing_ids = load_existing_ids()
    print(f"Existing traces in dataset: {len(existing_ids)}", flush=True)

    new_records = []
    skipped = 0
    page = 1
    page_size = 50

    while True:
        try:
            response = lf.api.trace.list(limit=page_size, page=page)
        except Exception as e:
            print(f"Error listing traces (page {page}): {e}", file=sys.stderr)
            break

        items = response.data if hasattr(response, "data") else []
        if not items:
            break

        for item in items:
            trace_id = getattr(item, "id", None)
            if trace_id is None:
                continue

            if trace_id in existing_ids:
                skipped += 1
                continue

            if args.limit is not None and len(new_records) >= args.limit:
                break

            print(f"  Fetching trace {trace_id}...", flush=True)
            record = fetch_trace_record(lf, trace_id)
            if record:
                new_records.append(record)

        if args.limit is not None and len(new_records) >= args.limit:
            break

        meta = getattr(response, "meta", None)
        if meta:
            total_pages = getattr(meta, "total_pages", None)
            if total_pages is not None and page >= total_pages:
                break
        elif len(items) < page_size:
            break

        page += 1

    # Append new records
    with open(TRACES_FILE, "a") as f:
        for record in new_records:
            f.write(json.dumps(record) + "\n")

    print(f"\nDone. {len(new_records)} new trace(s) written, {skipped} skipped (already present).")
    print(f"Dataset: {TRACES_FILE}")


if __name__ == "__main__":
    main()
