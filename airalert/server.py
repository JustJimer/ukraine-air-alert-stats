"""Local web app: stdlib HTTP server in front of the statistics module.

    python -m airalert.server            # http://127.0.0.1:8777
    python -m airalert.server --port 9000 --no-browser

The dataset is loaded into memory once at startup; every query is answered
from that frame, so filtering is instant and works offline afterwards.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from . import data, stats

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_frame: pd.DataFrame | None = None
_gazetteer: dict = {}
_coverage: dict = {}
_lock = threading.Lock()


def _timestamp(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        return pd.Timestamp(value, tz="UTC")
    except ValueError:
        return None


@lru_cache(maxsize=256)
def _cached_report(oblast, raion, hromada, start, end, merge, standing_days, hours) -> str:
    payload = stats.report(
        _frame,
        oblast=oblast or None,
        raion=raion or None,
        hromada=hromada or None,
        start=_timestamp(start),
        end=_timestamp(end),
        merge=merge,
        standing_days=standing_days,
        hours=hours,
    )
    return json.dumps(payload, ensure_ascii=False)


def _merge_flag(mode: str) -> bool | None:
    """'' means let the statistics module choose based on the selected area."""
    return {"merged": True, "raw": False}.get(mode)


def _hours(value: str) -> tuple[int, ...]:
    """Parse "0,1,22" into a tuple — hashable, so lru_cache accepts it."""
    hours = set()
    for part in value.split(","):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 23:
            hours.add(int(part))
    return tuple(sorted(hours))


def _standing_days(value: str) -> float | None:
    """'off' keeps standing frontline alerts inside the duration statistics."""
    if value == "off":
        return None
    try:
        return float(value) if value else stats.STANDING_ALERT_DAYS
    except ValueError:
        return stats.STANDING_ALERT_DAYS


class Handler(BaseHTTPRequestHandler):
    server_version = "airalert/1.0"

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def do_GET(self):
        route = urlparse(self.path)

        if route.path in ("/", "/index.html"):
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")

        if route.path == "/api/meta":
            return self._send_json(json.dumps({"gazetteer": _gazetteer, "coverage": _coverage}, ensure_ascii=False))

        if route.path == "/api/stats":
            query = parse_qs(route.query)

            def value(key: str) -> str:
                return query.get(key, [""])[0].strip()

            try:
                body = _cached_report(
                    value("oblast"),
                    value("raion"),
                    value("hromada"),
                    value("start"),
                    value("end"),
                    _merge_flag(value("mode")),
                    _standing_days(value("standing")),
                    _hours(value("hours")),
                )
            except Exception as error:  # surface the reason in the UI
                return self._send_json(json.dumps({"error": str(error)}), status=500)

            return self._send_json(body)

        self.send_error(404, "not found")

    def _send_file(self, path: Path, content_type: str):
        try:
            payload = path.read_bytes()
        except OSError:
            return self.send_error(404, "not found")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, body: str, status: int = 200):
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve(port: int = 8777, dataset: str = "official", update: bool = False, open_browser: bool = True) -> None:
    global _frame, _gazetteer, _coverage

    print(f"loading {dataset} dataset ...")
    _frame = data.load(dataset, force_download=update)
    _gazetteer = data.gazetteer(_frame)
    _coverage = data.coverage(_frame)
    print(f"  {_coverage['rows']:,} alerts, {_coverage['first'][:10]} .. {_coverage['last'][:10]}")

    url = f"http://127.0.0.1:{port}/"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"serving {url}   (Ctrl+C to stop)")

    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=[url]).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="airalert.server")
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--dataset", default="official", choices=sorted(data.DATASETS))
    parser.add_argument("--update", action="store_true", help="force a fresh download")
    parser.add_argument("--no-browser", dest="browser", action="store_false")
    args = parser.parse_args(argv)

    serve(port=args.port, dataset=args.dataset, update=args.update, open_browser=args.browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
