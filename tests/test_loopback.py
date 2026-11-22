import threading
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from ytmcp.auth.loopback import LoopbackReceiver
from ytmcp.errors import AuthFailedError


def visit(url, delay=0.0):
    """Pretend to be the browser coming back, from another thread."""
    result = {}

    def go():
        try:
            with urlopen(url, timeout=5) as response:
                result["body"] = response.read().decode()
        except HTTPError as exc:
            result["status"] = exc.code

    thread = threading.Thread(target=go)
    thread.start()
    return thread, result


def test_listens_on_loopback_only():
    with LoopbackReceiver() as receiver:
        assert receiver.redirect_uri.startswith("http://127.0.0.1:")
        assert receiver.redirect_uri.endswith("/callback")
        assert receiver._server.server_address[0] == "127.0.0.1"


def test_returns_the_redirect_parameters():
    with LoopbackReceiver() as receiver:
        thread, result = visit(f"{receiver.redirect_uri}?code=abc&state=xyz")
        assert receiver.wait(timeout=5) == {"code": "abc", "state": "xyz"}
        thread.join()
    assert "Signed in" in result["body"]


def test_page_does_not_repeat_the_code():
    with LoopbackReceiver() as receiver:
        thread, result = visit(f"{receiver.redirect_uri}?code=SECRET-CODE&state=s")
        receiver.wait(timeout=5)
        thread.join()
    assert "SECRET-CODE" not in result["body"]


def test_error_redirect_is_returned():
    with LoopbackReceiver() as receiver:
        thread, _ = visit(f"{receiver.redirect_uri}?error=access_denied&state=s")
        assert receiver.wait(timeout=5)["error"] == "access_denied"
        thread.join()


def test_other_paths_are_ignored_until_the_real_callback():
    statuses = []

    def browser(base, callback):
        # one visitor: first a stray request (e.g. a favicon), then the real redirect
        try:
            urlopen(f"{base}/favicon.ico", timeout=5)
        except HTTPError as exc:
            statuses.append(exc.code)
        urlopen(callback, timeout=5).read()

    with LoopbackReceiver() as receiver:
        base = receiver.redirect_uri.rsplit("/", 1)[0]
        thread = threading.Thread(target=browser, args=(base, f"{receiver.redirect_uri}?code=abc&state=s"))
        thread.start()
        assert receiver.wait(timeout=5)["code"] == "abc"
        thread.join()
    assert statuses == [404]


def test_times_out():
    with LoopbackReceiver() as receiver, pytest.raises(AuthFailedError) as exc:
        receiver.wait(timeout=0.2)
    assert "Timed out" in str(exc.value)
