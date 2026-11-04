"""Serve the desktop UI to a normal browser, backed by the real Api.

    python -m src.desktop --serve [--port 8765]

This is the browser-preview path that replaces the old fake-data mock: the same
`Api` methods the pywebview window calls are exposed as POST /api/<method>.

The server can start scrapers, so it is locked down:
- binds to 127.0.0.1 only;
- rejects any Host header that is not this loopback address (DNS rebinding);
- every API call must carry the per-launch random token in X-Hunter-Token. The
  token lives in the URL fragment, which browsers never send to servers, and a
  custom header forces a CORS preflight that this server never approves, so
  other web pages cannot call the API.
"""
from __future__ import annotations

import hmac
import inspect
import json
import secrets
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .bridge import Api

UI_DIR = Path(__file__).resolve().parent / "ui"
MAX_BODY = 64 * 1024


def public_methods(api: Api) -> dict:
    return {name: fn for name, fn in inspect.getmembers(api, callable)
            if not name.startswith("_")}


class Handler(SimpleHTTPRequestHandler):
    api: Api
    methods: dict
    token: str
    hosts: frozenset

    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "").lower() in self.hosts

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "Forbidden host"})
        if self.path.startswith("/api/"):
            return self._json(405, {"error": "Use POST"})
        return super().do_GET()

    def do_HEAD(self):
        if not self._host_ok():
            return self._json(403, {"error": "Forbidden host"})
        return super().do_HEAD()

    def _read_body(self) -> bytes | None:
        """Consume the request body (so rejections don't abort the socket); None if too large."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if not 0 <= length <= MAX_BODY:
            self.close_connection = True
            return None
        return self.rfile.read(length) if length else b""

    def do_POST(self):
        raw = self._read_body()
        if raw is None:
            return self._json(413, {"error": "Request too large"})
        if not self._host_ok():
            return self._json(403, {"error": "Forbidden host"})
        if not hmac.compare_digest(self.headers.get("X-Hunter-Token") or "", self.token):
            return self._json(401, {"error": "Missing or wrong session token. Open the URL printed at startup."})
        name = self.path[len("/api/"):] if self.path.startswith("/api/") else ""
        fn = self.methods.get(name)
        if fn is None:
            return self._json(404, {"error": f"Unknown method: {name}"})
        try:
            body = json.loads(raw or b"{}")
            args = body.get("args", []) if isinstance(body, dict) else None
            if not isinstance(args, list):
                raise ValueError
        except ValueError:
            return self._json(400, {"error": "Body must be JSON: {\"args\": [...]}"})
        try:
            result = fn(*args)  # Api methods already turn exceptions into {"error"}
        except TypeError as exc:  # wrong arity from the client
            result = {"error": str(exc)}
        return self._json(200, result)


def make_server(port: int = 8765, api: Api | None = None, token: str | None = None):
    api = api or Api()
    token = token or secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(UI_DIR)))
    actual = server.server_address[1]
    Handler.api = api
    Handler.methods = public_methods(api)
    Handler.token = token
    Handler.hosts = frozenset({f"127.0.0.1:{actual}", f"localhost:{actual}"})
    url = f"http://127.0.0.1:{actual}/index.html#token={token}"
    return server, url


def serve(port: int = 8765, open_browser: bool = True) -> int:
    server, url = make_server(port)
    print(f"Scholarships Hunter UI (real data): {url}", flush=True)
    print("Local only. Press Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
