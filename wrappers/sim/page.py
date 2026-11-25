"""The simulated body's page: it draws itself as a stick figure, and lets a person do to it what hands do.

It answers this computer only. The page reads what the body is doing; its buttons reach the WORLD (tip it, set
it level, a hand in front, a pat, the servo power switch) and never one of the driver's calls.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = "127.0.0.1"
PAGE = Path(__file__).with_name("page.html")


def _number(value: Any, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        raise ValueError("not a number")
    return max(lo, min(hi, float(value)))


def _world(driver, ask: dict) -> None:
    """One thing done to the body by hand. A closed list: anything else is refused."""
    do = ask.get("do")
    if do == "tip":
        driver.tip(_number(ask.get("roll", 0), -180, 180), _number(ask.get("pitch", 0), -180, 180))
    elif do == "level":
        driver.level()
    elif do == "hand":
        driver.hand(None if ask.get("m") is None else _number(ask.get("m"), 0, 10))
    elif do == "pat":
        pad = ask.get("pad")
        driver.pat(pad if isinstance(pad, str) else None)
    elif do == "power":
        driver.power(ask.get("on") is True)
    else:
        raise ValueError("not something a hand can do to it")


def serve(driver, port: int) -> ThreadingHTTPServer:
    """Start the page on this computer, on its own thread. The caller shuts it down."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, kind: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 (the library's name)
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE.read_bytes())
            elif self.path == "/look":
                self._send(200, "application/json", json.dumps(driver.look()).encode("utf-8"))
            else:
                self._send(404, "text/plain; charset=utf-8", b"nothing here")

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/world" or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._send(404, "text/plain; charset=utf-8", b"nothing here")
                return
            try:
                length = min(int(self.headers.get("Content-Length", "0")), 4096)
                ask = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(ask, dict):
                    raise ValueError("not a table")
                _world(driver, ask)
            except (ValueError, TypeError) as e:
                self._send(400, "application/json", json.dumps({"ok": False, "why": str(e)}).encode("utf-8"))
                return
            self._send(200, "application/json", b'{"ok": true}')

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer((HOST, int(port)), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="simulated-body-page", daemon=True).start()
    return server
