"""
launch_result_viewer.py — Serve the Eval Result Viewer for an autorater result file.

Usage:
    uv run python eval/launch_result_viewer.py --result eval/data/v2/results/run.json [--port PORT]

Starts a local HTTP server on 127.0.0.1:
  GET  /  → eval_result_viewer.html with result data pre-loaded

Press Ctrl+C to stop.
"""

import argparse
import json
import socket
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def build_html(viewer_template: Path, preloaded: dict) -> str:
    html = viewer_template.read_text(encoding="utf-8")
    if "<!-- __PRELOADED__ -->" not in html:
        raise ValueError("eval_result_viewer.html is missing <!-- __PRELOADED__ --> placeholder.")
    injection = f"<script>window.PRELOADED = {json.dumps(preloaded)};</script>"
    return html.replace("<!-- __PRELOADED__ -->", injection)


def make_handler(viewer_template: Path, result_data: dict):
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/eval_result_viewer.html"):
                body = build_html(viewer_template, result_data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # suppress per-request logging

    return ViewerHandler


def main():
    parser = argparse.ArgumentParser(description="Serve the Eval Result Viewer for an autorater result file.")
    parser.add_argument("--result", required=True, help="Path to result JSON file (e.g. eval/data/v2/results/run.json)")
    parser.add_argument("--port", type=int, default=None, help="Port (default: auto)")
    args = parser.parse_args()

    result_path = Path(args.result)
    if not result_path.exists():
        print(f"Error: result file not found: {result_path}", file=sys.stderr)
        sys.exit(1)

    viewer_template = Path(__file__).parent / "eval_result_viewer.html"
    if not viewer_template.exists():
        print(f"Error: eval_result_viewer.html not found at {viewer_template}", file=sys.stderr)
        sys.exit(1)

    with open(result_path, encoding="utf-8") as f:
        result_data = json.load(f)

    port = args.port or find_free_port()
    handler = make_handler(viewer_template, result_data)
    server = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"

    n_examples = result_data.get("n_examples", len(result_data.get("examples", [])))
    n_rubrics = len(result_data.get("global_rubrics", []))
    prompt_file = result_data.get("prompt_file", "unknown")
    judge_model = result_data.get("judge_model", "unknown")
    timestamp = result_data.get("timestamp", "unknown")

    print(f"Result file:      {result_path}")
    print(f"Prompt:           {prompt_file}")
    print(f"Judge model:      {judge_model}")
    print(f"Timestamp:        {timestamp}")
    print(f"Examples:         {n_examples}")
    print(f"Global rubrics:   {n_rubrics}")
    print(f"Serving:          {url}")
    print(f"\nPress Ctrl+C to stop.\n")

    subprocess.run(["open", url])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
