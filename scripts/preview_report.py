"""Serve only the self-contained report on loopback for local review."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


REPORT = Path(__file__).resolve().parents[1] / "index.html"


class ReportHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if urlsplit(self.path).path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = REPORT.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    print(f"Local report preview: http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), ReportHandler).serve_forever()
