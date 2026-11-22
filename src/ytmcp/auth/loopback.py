"""Local receiver for the OAuth redirect (RFC 8252, installed apps).

Google sends the browser back to http://127.0.0.1:<port>/callback with the
result in the URL. This listens on the loopback address only, so nothing
outside this computer can reach it, and it handles requests one at a time
(no threads). The page it shows never repeats the code.
"""

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Self
from urllib.parse import parse_qs, urlparse

from ytmcp.errors import AuthFailedError

CALLBACK_PATH = "/callback"
PAGE = b"<html><body><h2>Signed in.</h2><p>You can close this tab and go back to the terminal.</p></body></html>"


class LoopbackReceiver:
    def __init__(self, host: str = "127.0.0.1"):
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != CALLBACK_PATH:
                    self.send_error(404)
                    return
                receiver._params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(PAGE)))
                self.end_headers()
                self.wfile.write(PAGE)

            def log_message(self, format, *args):
                pass

        self._params: dict[str, str] | None = None
        self._server = HTTPServer((host, 0), Handler)  # port 0 = any free port

    @property
    def redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}{CALLBACK_PATH}"

    def wait(self, timeout: float = 120) -> dict[str, str]:
        """Block until the browser comes back, then return the URL parameters."""
        deadline = time.monotonic() + timeout
        while self._params is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuthFailedError("Timed out waiting for you to finish signing in.")
            self._server.timeout = remaining
            self._server.handle_request()
        return self._params

    def close(self) -> None:
        self._server.server_close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
