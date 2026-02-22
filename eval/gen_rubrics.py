"""
gen_rubrics.py — Generate evaluation rubrics from trace feedback.

Produces two outputs:
  eval/data/rubrics.json          — Principle-based rubrics (global, human-reviewed)
  eval/data/example_rubrics.jsonl — Example-specific rubrics (per trace, from user comments)

Usage:
    uv run python eval/gen_rubrics.py
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data"
TRACES_FILE = DATA_DIR / "traces.jsonl"
RUBRICS_FILE = DATA_DIR / "rubrics.json"
EXAMPLE_RUBRICS_FILE = DATA_DIR / "example_rubrics.jsonl"


def get_gemini_client():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def load_traces() -> list[dict]:
    if not TRACES_FILE.exists():
        print(f"Error: {TRACES_FILE} not found. Run eval/dump_traces.py first.", file=sys.stderr)
        sys.exit(1)
    records = []
    with open(TRACES_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def load_existing_example_rubric_ids() -> set[str]:
    if not EXAMPLE_RUBRICS_FILE.exists():
        return set()
    ids = set()
    with open(EXAMPLE_RUBRICS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ids.add(json.loads(line)["trace_id"])
                except (json.JSONDecodeError, KeyError):
                    pass
    return ids


def call_gemini_json(client, prompt: str) -> list | dict:
    """Call Gemini and parse JSON from the response."""
    from google.genai import types

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def generate_principle_rubrics(client, traces: list[dict]) -> list[dict]:
    """Generate 8-12 principle-based rubrics from rated examples."""
    rated = [t for t in traces if t.get("user_rating") is not None and t.get("response")]
    if not rated:
        print("Warning: No rated traces found. Generating rubrics from all available summaries.")
        rated = [t for t in traces if t.get("response")]

    positives = [t for t in rated if t.get("user_rating") == 1 or t.get("user_rating") is True]
    negatives = [t for t in rated if t.get("user_rating") == 0 or t.get("user_rating") is False]

    def fmt_examples(items, include_comment=False, max_items=5):
        out = []
        for t in items[:max_items]:
            entry = f"[trace_id={t['trace_id']}]\n{t['response']}"
            if include_comment and t.get("user_comment"):
                entry += f"\nUser comment: {t['user_comment']}"
            out.append(entry)
        return "\n\n---\n\n".join(out) if out else "(none)"

    pos_block = fmt_examples(positives)
    neg_block = fmt_examples(negatives, include_comment=True)

    prompt = f"""You are designing evaluation criteria for an AI article summarizer bot that outputs Telegram-compatible HTML summaries.

POSITIVELY RATED summaries (users gave thumbs up):
{pos_block}

NEGATIVELY RATED summaries with user comments (users gave thumbs down):
{neg_block}

Generate 8-12 boolean rubric statements that capture what makes a good summary.
Each rubric must be:
- A complete declarative sentence evaluatable as strictly TRUE or FALSE
- Evaluatable from the summary text alone (no access to original article needed)
- Unambiguous (two independent evaluators would agree on the verdict)
- Cover a mix of: formatting quality, completeness, conciseness, absence of hallucination markers, tone, and Telegram HTML correctness

Return a JSON array (no markdown fences):
[
  {{"id": "r1", "statement": "...", "rationale": "..."}},
  ...
]"""

    print("Calling Gemini to generate principle rubrics...")
    rubrics = call_gemini_json(client, prompt)
    if not isinstance(rubrics, list):
        raise ValueError(f"Expected a JSON array, got: {type(rubrics)}")
    return rubrics


def generate_example_rubrics(client, trace: dict) -> list[dict]:
    """Generate 1-3 example-specific rubrics from a user comment."""
    prompt = f"""A user left this feedback on an AI-generated article summary:

User comment: "{trace['user_comment']}"

Summary:
---
{trace['response']}
---

Derive 1-3 boolean rubric statements that capture what this user wanted from the summary.
Each rubric must be:
- A self-contained TRUE/FALSE statement evaluatable on future summaries of the same article
- Specific enough to reflect the user's actual concern
- Not redundant with each other

Return a JSON array (no markdown fences):
[
  {{"id": "er1", "statement": "...", "source": "user_comment"}},
  ...
]"""

    rubrics = call_gemini_json(client, prompt)
    if not isinstance(rubrics, list):
        raise ValueError(f"Expected a JSON array, got: {type(rubrics)}")
    return rubrics


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    client = get_gemini_client()
    traces = load_traces()
    print(f"Loaded {len(traces)} trace(s) from {TRACES_FILE}")

    # ── Principle-based rubrics ──────────────────────────────────────────────
    if RUBRICS_FILE.exists():
        answer = input(f"\n{RUBRICS_FILE} already exists. Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Skipping principle rubric generation.")
        else:
            rubrics = generate_principle_rubrics(client, traces)
            with open(RUBRICS_FILE, "w") as f:
                json.dump(rubrics, f, indent=2)
            print(f"Wrote {len(rubrics)} principle rubric(s) to {RUBRICS_FILE}")
            print("Review and edit rubrics.json before running autorater.")
    else:
        rubrics = generate_principle_rubrics(client, traces)
        with open(RUBRICS_FILE, "w") as f:
            json.dump(rubrics, f, indent=2)
        print(f"Wrote {len(rubrics)} principle rubric(s) to {RUBRICS_FILE}")
        print("Review and edit rubrics.json before running autorater.")

    # ── Example-specific rubrics ─────────────────────────────────────────────
    existing_ids = load_existing_example_rubric_ids()
    candidates = [
        t for t in traces
        if t.get("user_comment") and t.get("response") and t["trace_id"] not in existing_ids
    ]
    print(f"\nTraces with new user comments: {len(candidates)}")

    new_entries = 0
    with open(EXAMPLE_RUBRICS_FILE, "a") as f:
        for trace in candidates:
            print(f"  Generating example rubrics for trace {trace['trace_id']}...")
            try:
                rubrics = generate_example_rubrics(client, trace)
                entry = {"trace_id": trace["trace_id"], "rubrics": rubrics}
                f.write(json.dumps(entry) + "\n")
                new_entries += 1
            except Exception as e:
                print(f"    Warning: failed for trace {trace['trace_id']}: {e}", file=sys.stderr)

    print(f"Appended {new_entries} new example rubric entry(ies) to {EXAMPLE_RUBRICS_FILE}")


if __name__ == "__main__":
    main()
