"""
launch_data_viewer.py — Serve the Eval Data Viewer for a dataset version with direct save support.

Usage:
    uv run python eval/launch_data_viewer.py --version v1 [--port PORT]

Starts a local HTTP server on 127.0.0.1:
  GET  /              → eval_data_viewer.html with dataset pre-loaded
  POST /save          → writes example_rubrics.jsonl directly to eval/data/<version>/
  POST /save-examples → writes examples.jsonl (eval_ready metadata) to eval/data/<version>/

Press Ctrl+C to stop.
"""

import argparse
import json
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def build_html(viewer_template: Path, preloaded: dict) -> str:
    html = viewer_template.read_text(encoding="utf-8")
    if "<!-- __PRELOADED__ -->" not in html:
        raise ValueError("eval_data_viewer.html is missing <!-- __PRELOADED__ --> placeholder.")
    injection = f"<script>window.PRELOADED = {json.dumps(preloaded)};</script>"
    return html.replace("<!-- __PRELOADED__ -->", injection)


def make_handler(
    viewer_template: Path,
    preloaded_base: dict,
    example_rubrics_path: Path,
    global_rubrics_path: Path,
    examples_path: Path,
):
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/eval_data_viewer.html"):
                # Re-read all data files on every request so a refresh
                # always reflects the latest saved state.
                example_rubrics = load_jsonl(example_rubrics_path)
                global_rubrics = load_jsonl(global_rubrics_path)
                examples_metadata = load_jsonl(examples_path)
                preloaded = {
                    **preloaded_base,
                    "exampleRubrics": example_rubrics,
                    "globalRubrics": global_rubrics,
                    "examplesMetadata": examples_metadata,
                }
                body = build_html(viewer_template, preloaded).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/save":
                self._handle_save(example_rubrics_path)
            elif self.path == "/save-examples":
                self._handle_save(examples_path)
            else:
                self.send_response(404)
                self.end_headers()

        def _handle_save(self, save_path: Path):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                save_path.write_bytes(body)
                resp = json.dumps({"ok": True, "path": str(save_path)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                print(f"  Saved → {save_path}")
            except Exception as e:
                resp = json.dumps({"ok": False, "error": str(e)}).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

        def log_message(self, fmt, *args):
            pass  # suppress per-request logging

    return ViewerHandler


def main():
    parser = argparse.ArgumentParser(description="Serve the Eval Data Viewer for a dataset version.")
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    parser.add_argument("--port", type=int, default=None, help="Port (default: auto)")
    args = parser.parse_args()

    data_dir = Path(__file__).parent / "data" / args.version
    traces_file = data_dir / "traces.jsonl"
    example_rubrics_file = data_dir / "example_rubrics.jsonl"
    global_rubrics_file = data_dir / "global_rubrics.jsonl"
    examples_file = data_dir / "examples.jsonl"
    viewer_template = Path(__file__).parent / "eval_data_viewer.html"

    if not viewer_template.exists():
        print(f"Error: eval_data_viewer.html not found at {viewer_template}", file=sys.stderr)
        sys.exit(1)
    if not traces_file.exists():
        print(f"Error: {traces_file} not found. Run make eval-dump VERSION={args.version} first.", file=sys.stderr)
        sys.exit(1)

    data_dir.mkdir(parents=True, exist_ok=True)

    traces = load_jsonl(traces_file)
    example_rubrics = load_jsonl(example_rubrics_file)
    global_rubrics = load_jsonl(global_rubrics_file)
    examples_metadata = load_jsonl(examples_file)
    port = args.port or find_free_port()

    preloaded_base = {
        "version": args.version,
        "relPath": f"eval/data/{args.version}",
        "serverMode": True,
        "traces": traces,
        # exampleRubrics, globalRubrics, examplesMetadata excluded here — added fresh per request
    }

    handler = make_handler(
        viewer_template,
        preloaded_base,
        example_rubrics_file,
        global_rubrics_file,
        examples_file,
    )
    server = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"

    print(f"Version:          {args.version}")
    print(f"Traces:           {len(traces)}")
    print(f"Global rubrics:   {len(global_rubrics)}")
    print(f"Rubric entries:   {len(example_rubrics)}")
    print(f"Examples meta:    {len(examples_metadata)}")
    print(f"Serving:          {url}")
    print(f"Saves to:         {data_dir}/")
    print(f"\nPress Ctrl+C to stop.\n")

    subprocess.run(["open", url])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
