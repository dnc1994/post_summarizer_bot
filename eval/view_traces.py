"""
view_traces.py — Inspect a versioned trace dataset without scrolling through long text.

Usage:
    # Compact list of all traces
    uv run python eval/view_traces.py --version v1

    # Full detail for one trace (prompt/response truncated to --width chars per line)
    uv run python eval/view_traces.py --version v1 --trace-id <id> [--width 120]
"""

import argparse
import json
import textwrap
from pathlib import Path

TERM_WIDTH = 100


def load_traces(examples_file: Path) -> list[dict]:
    if not examples_file.exists():
        print(f"No dataset found at {examples_file}. Run make eval-dump VERSION=<v> first.")
        return []
    records = []
    with open(examples_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def fmt_rating(val) -> str:
    if val is None:
        return "—"
    return "👍" if val == 1 or val is True or val == 1.0 else "👎"


def truncate(s, n: int) -> str:
    if s is None:
        return "—"
    s = str(s).replace("\n", " ")
    return s[:n] + "…" if len(s) > n else s


def print_list(traces: list[dict], examples_file: Path):
    if not traces:
        print("No traces.")
        return

    print(f"\n{'#':<4} {'TRACE ID':<10} {'RATING':<7} {'URL':<45} {'COMMENT':<30} {'CHARS (prompt/resp/article)'}")
    print("─" * TERM_WIDTH)

    for i, t in enumerate(traces, 1):
        tid = t["trace_id"][:8]
        rating = fmt_rating(t.get("user_rating"))
        url = truncate(t.get("url"), 43)
        comment = truncate(t.get("user_comment"), 28)
        pl = len(t.get("prompt") or "")
        rl = len(t.get("response") or "")
        al = len(t.get("article_text") or "")
        print(f"{i:<4} {tid:<10} {rating:<7} {url:<45} {comment:<30} {pl}/{rl}/{al}")

    print(f"\n{len(traces)} trace(s) in {examples_file}")


def print_field(label: str, text: str | None, width: int, max_lines: int = 40):
    bar = "─" * TERM_WIDTH
    print(f"\n{bar}")
    print(f"  {label}")
    print(bar)
    if not text:
        print("  (empty)")
        return
    lines = text.splitlines()
    printed = 0
    for line in lines:
        for wrapped in textwrap.wrap(line, width) or [""]:
            print(f"  {wrapped}")
            printed += 1
            if printed >= max_lines:
                remaining = sum(len(textwrap.wrap(l, width) or [""]) for l in lines) - printed
                if remaining > 0:
                    print(f"\n  … ({remaining} more lines, {len(text) - width * max_lines} chars truncated)")
                return


def print_detail(trace: dict, width: int):
    tid = trace["trace_id"]
    print(f"\n{'═' * TERM_WIDTH}")
    print(f"  TRACE: {tid}")
    print(f"  URL:   {trace.get('url') or '—'}")
    print(f"  Time:  {trace.get('timestamp') or '—'}")
    print(f"  Rating: {fmt_rating(trace.get('user_rating'))}  Comment: {trace.get('user_comment') or '—'}")
    print(f"{'═' * TERM_WIDTH}")

    print_field(f"PROMPT  ({len(trace.get('prompt') or '')} chars)", trace.get("prompt"), width)
    print_field(f"RESPONSE  ({len(trace.get('response') or '')} chars)", trace.get("response"), width)
    print_field(f"ARTICLE TEXT  ({len(trace.get('article_text') or '')} chars)", trace.get("article_text"), width)


def main():
    parser = argparse.ArgumentParser(description="View a versioned trace dataset.")
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    parser.add_argument("--trace-id", default=None, help="Show full detail for a specific trace (prefix match)")
    parser.add_argument("--width", type=int, default=120, help="Max line width for detail view (default: 120)")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / args.version
    examples_file = data_dir / "examples.jsonl"
    traces = load_traces(examples_file)
    if not traces:
        return

    if args.trace_id:
        matches = [t for t in traces if t["trace_id"].startswith(args.trace_id)]
        if not matches:
            print(f"No trace found with id starting with '{args.trace_id}'.")
            print("Available IDs:")
            for t in traces:
                print(f"  {t['trace_id']}")
            return
        for t in matches:
            print_detail(t, args.width)
    else:
        print_list(traces, examples_file)


if __name__ == "__main__":
    main()
