"""
gen_rubrics.py — Generate evaluation rubrics from trace feedback.

Produces two outputs (both in eval/data/<version>/):
  global_rubrics.jsonl  — Principle-based rubrics (global, human-reviewed; one per line)
  example_rubrics.jsonl — Example-specific rubrics (per trace, from user comments)

Usage:
    uv run python eval/gen_rubrics.py --version v1
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_gemini_client():
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    return genai.Client(api_key=api_key)


def load_traces(traces_file: Path) -> list[dict]:
    if not traces_file.exists():
        print(f"Error: {traces_file} not found. Run dump_traces.py --version <v> first.", file=sys.stderr)
        sys.exit(1)
    records = []
    with open(traces_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def load_processed_comments(example_rubrics_file: Path) -> dict[str, str | None]:
    """Return {trace_id: generated_from_comment} for entries already processed.

    When duplicate trace_ids exist (append-only re-generation), keeps the latest.
    None means the entry predates the generated_from_comment field.
    """
    if not example_rubrics_file.exists():
        return {}
    result: dict[str, str | None] = {}
    with open(example_rubrics_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    tid = entry.get("trace_id")
                    if tid:
                        result[tid] = entry.get("generated_from_comment")
                except (json.JSONDecodeError, KeyError):
                    pass
    return result


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

    prompt = f"""You are designing evaluation criteria for an AI article summarizer bot that outputs Telegram-compatible HTML summaries.

POSITIVELY RATED summaries (users gave thumbs up):
{fmt_examples(positives)}

NEGATIVELY RATED summaries with user comments (users gave thumbs down):
{fmt_examples(negatives, include_comment=True)}

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
    parser = argparse.ArgumentParser(description="Generate evaluation rubrics from trace feedback.")
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / args.version
    traces_file = data_dir / "traces.jsonl"
    global_rubrics_file = data_dir / "global_rubrics.jsonl"
    example_rubrics_file = data_dir / "example_rubrics.jsonl"
    data_dir.mkdir(parents=True, exist_ok=True)

    client = get_gemini_client()
    traces = load_traces(traces_file)
    print(f"Version: {args.version} | Loaded {len(traces)} trace(s)")

    # ── Principle-based rubrics (merge-safe) ─────────────────────────────────
    # Load existing rubrics from global_rubrics.jsonl (JSONL format)
    existing_rubrics: list[dict] = []
    if global_rubrics_file.exists():
        for line in global_rubrics_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    existing_rubrics.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    print(f"Existing global rubrics: {len(existing_rubrics)}")
    print("Calling Gemini to generate principle rubrics...")
    candidates = generate_principle_rubrics(client, traces)

    # Dedup: skip candidates whose statement matches any existing (case-insensitive)
    existing_stmts = {r["statement"].strip().lower() for r in existing_rubrics}
    new_rubrics = [r for r in candidates if r["statement"].strip().lower() not in existing_stmts]

    if not new_rubrics:
        print(f"No new rubrics to add. ({len(existing_rubrics)} existing)")
    else:
        # Renumber new rubric IDs to continue from highest existing ID
        max_id = 0
        for r in existing_rubrics:
            try:
                n = int("".join(filter(str.isdigit, r.get("id", "0"))) or "0")
                max_id = max(max_id, n)
            except ValueError:
                pass
        for i, r in enumerate(new_rubrics, max_id + 1):
            r["id"] = f"r{i}"

        merged = existing_rubrics + new_rubrics
        with open(global_rubrics_file, "w") as f:
            for r in merged:
                f.write(json.dumps(r) + "\n")
        print(f"Merged: {len(existing_rubrics)} existing + {len(new_rubrics)} new = {len(merged)} rubrics")
        print(f"Wrote to {global_rubrics_file}")
        print("Review and edit global_rubrics.jsonl before running autorater.")

    # ── Example-specific rubrics ─────────────────────────────────────────────
    processed = load_processed_comments(example_rubrics_file)
    candidates = [
        t for t in traces
        if t.get("user_comment") and t.get("response")
        and (
            t["trace_id"] not in processed                          # never processed
            or processed[t["trace_id"]] != str(t["user_comment"])  # new/changed comment
        )
    ]
    print(f"\nTraces with new or updated user comments: {len(candidates)}")

    new_entries = 0
    with open(example_rubrics_file, "a") as f:
        for trace in candidates:
            print(f"  Generating example rubrics for trace {trace['trace_id']}...")
            try:
                rubrics = generate_example_rubrics(client, trace)
                entry = {
                    "trace_id": trace["trace_id"],
                    "generated_from_comment": str(trace["user_comment"]),
                    "rubrics": rubrics,
                }
                f.write(json.dumps(entry) + "\n")
                new_entries += 1
            except Exception as e:
                print(f"    Warning: failed for trace {trace['trace_id']}: {e}", file=sys.stderr)

    print(f"Appended {new_entries} new example rubric entry(ies) to {example_rubrics_file}")


if __name__ == "__main__":
    main()
