"""
launch_viewer.py — Inject versioned dataset into viewer.html and open in browser.

Usage:
    uv run python eval/launch_viewer.py --version v1

Reads eval/data/<version>/traces.jsonl and example_rubrics.jsonl, injects them
into viewer.html as a PRELOADED global, writes a temp file, and opens it.
After editing rubrics, export downloads example_rubrics.jsonl — place the file
back at eval/data/<version>/example_rubrics.jsonl.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().strip().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def main():
    parser = argparse.ArgumentParser(description="Open the eval viewer for a dataset version.")
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / args.version
    traces_file = data_dir / "traces.jsonl"
    rubrics_file = data_dir / "example_rubrics.jsonl"
    viewer_template = Path(__file__).parent / "viewer.html"

    if not viewer_template.exists():
        print(f"Error: viewer.html not found at {viewer_template}", file=sys.stderr)
        sys.exit(1)

    if not traces_file.exists():
        print(f"Error: {traces_file} not found. Run make eval-dump VERSION={args.version} first.", file=sys.stderr)
        sys.exit(1)

    traces = load_jsonl(traces_file)
    rubrics = load_jsonl(rubrics_file)

    print(f"Version:             {args.version}")
    print(f"Traces:              {len(traces)}")
    print(f"Rubric entries:      {len(rubrics)}")

    preloaded = {
        "version": args.version,
        "relPath": f"eval/data/{args.version}",
        "traces": traces,
        "exampleRubrics": rubrics,
    }

    html = viewer_template.read_text()
    injection = f"<script>window.PRELOADED = {json.dumps(preloaded)};</script>"
    if "<!-- __PRELOADED__ -->" not in html:
        print("Error: viewer.html is missing <!-- __PRELOADED__ --> placeholder.", file=sys.stderr)
        sys.exit(1)
    html = html.replace("<!-- __PRELOADED__ -->", injection)

    out_path = data_dir / ".viewer_temp.html"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)

    print(f"\nOpening viewer...")
    print(f"After editing, save the exported file to: eval/data/{args.version}/example_rubrics.jsonl")
    subprocess.run(["open", str(out_path)])


if __name__ == "__main__":
    main()
