"""
launch_viewer.py — Serve the eval viewer for a dataset version with direct save support.

Usage:
    uv run python eval/launch_viewer.py --version v1 [--port PORT]

Starts a local HTTP server on 127.0.0.1:
  GET  /      → viewer.html with dataset pre-loaded
  POST /save  → writes example_rubrics.jsonl directly to eval/data/<version>/

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
        raise ValueError("viewer.html is missing <!-- __PRELOADED__ --> placeholder.")
    injection = f"<script>window.PRELOADED = {json.dumps(preloaded)};</script>"
    return html.replace("<!-- __PRELOADED__ -->", injection)


def make_handler(html: str, save_path: Path):
    class ViewerHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/viewer.html"):
                body = html.encode("utf-8")
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
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # suppress per-request logging

    return ViewerHandler


def main():
    parser = argparse.ArgumentParser(description="Serve the eval viewer for a dataset version.")
    parser.add_argument("--version", required=True, help="Dataset version (e.g. v1)")
    parser.add_argument("--port", type=int, default=None, help="Port (default: auto)")
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

    data_dir.mkdir(parents=True, exist_ok=True)

    traces = load_jsonl(traces_file)
    rubrics = load_jsonl(rubrics_file)
    port = args.port or find_free_port()

    preloaded = {
        "version": args.version,
        "relPath": f"eval/data/{args.version}",
        "serverMode": True,
        "traces": traces,
        "exampleRubrics": rubrics,
    }

    html = build_html(viewer_template, preloaded)
    handler = make_handler(html, rubrics_file)
    server = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/"

    print(f"Version:        {args.version}")
    print(f"Traces:         {len(traces)}")
    print(f"Rubric entries: {len(rubrics)}")
    print(f"Serving:        {url}")
    print(f"Saves to:       {rubrics_file}")
    print(f"\nPress Ctrl+C to stop.\n")

    subprocess.run(["open", url])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
