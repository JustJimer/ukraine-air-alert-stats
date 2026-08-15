"""Serve web/ locally, the way the host serves it in production.

    python build.py && python -m airalert.server

The site is static: the packed dataset ships with the page and web/stats.js
does the filtering in the browser. This serves files and nothing else.

It used to answer /api/stats from pandas as well, which meant loading the
whole dataset before it could serve a single byte. Nothing has called that
since the move to a static site, so it is gone — along with a second
implementation of the statistics that could quietly drift from the one
actually shipped.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

WEB_DIR = (Path(__file__).resolve().parent.parent / "web").resolve()

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".bin": "application/octet-stream",
    # Served as a type, never as Content-Encoding: the page inflates it itself,
    # and announcing the encoding would make the browser decompress it first
    # and leave stats.js inflating plain bytes. This matches what Cloudflare
    # does with the same file.
    ".gz": "application/gzip",
    ".svg": "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "airalert/2.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        target = (WEB_DIR / path.lstrip("/")).resolve()

        if target.is_dir():
            target = target / "index.html"
        if path in ("", "/"):
            target = WEB_DIR / "index.html"

        # Refuse anything that resolves outside web/.
        if not target.is_relative_to(WEB_DIR) or not target.is_file():
            return self.send_error(404, "not found")

        try:
            payload = target.read_bytes()
        except OSError:
            return self.send_error(404, "not found")

        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve(port: int = 8777, open_browser: bool = True) -> None:
    if not (WEB_DIR / "data" / "meta.json").exists():
        print("web/data is missing — run `python build.py` first.")

    url = f"http://127.0.0.1:{port}/"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"serving {WEB_DIR} at {url}   (Ctrl+C to stop)")

    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=[url]).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airalert.server", description=__doc__)
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--no-browser", dest="browser", action="store_false")
    args = parser.parse_args(argv)

    serve(port=args.port, open_browser=args.browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
