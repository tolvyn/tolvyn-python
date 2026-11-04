"""Fail-open hardening.

Fail open ONLY when the proxy was never reached, or answered 503 with
X-Tolvyn-Unavailable: 1. Never forward any X-Tolvyn-* header to the provider,
replay the body intact, send the provider's own Host, and close the 503.

Real sockets: a stand-in provider records every request; stand-in proxies refuse,
answer 503 (marked or not), enforce (451/429), or forward and then hang or reset —
the cases where a direct retry would be a second, unmetered provider call.
"""
import asyncio
import json
import socket
import struct
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

import tolvyn
import tolvyn._anthropic as _ta
import tolvyn._client as _tc
import tolvyn._deepseek as _td
from tolvyn._failopen import make_failopen_async_transport, make_failopen_transport

try:  # present when anthropic >= 1 is installed
    import httpx2
except ImportError:
    httpx2 = None

# The fail-open matrix runs once per httpx-compatible module installed: httpx
# (openai, deepseek, anthropic 0.x) and httpx2 (anthropic >= 1).
HTTP_MODULES = [httpx] + ([httpx2] if httpx2 is not None else [])
HTTP_IDS = [m.__name__ for m in HTTP_MODULES]

SEEN = []  # every request the stand-in provider received
PORT = {}
BODY = json.dumps({"model": "m", "messages": [{"role": "user", "content": "hi"}]}).encode()
ATTR = {"X-Tolvyn-Team": "t-team", "X-Tolvyn-User": "pii-user@example.com",
        "x-tolvyn-end-customer": "pii-customer-42", "X-TOLVYN-FEATURE": "t-feature"}


class _Provider(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        SEEN.append({"via": self.headers.get("x-via", "direct"), "path": self.path,
                     "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body})
        self._reply(200, b'{"ok":true}')

    def _reply(self, code, payload, extra=None):
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


def _proxy(mode):
    class Proxy(_Provider):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("content-length", 0)))
            if mode in ("timeout", "reset"):
                # Forward first, as the real proxy would, then fail.
                urllib.request.urlopen(urllib.request.Request(
                    f"http://127.0.0.1:{PORT['provider']}{self.path}", data=body, method="POST",
                    headers={"content-type": "application/json", "x-via": "proxy"})).read()
                if mode == "timeout":
                    time.sleep(3)
                    return
                self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                self.connection.close()
                return
            extra = {"X-Tolvyn-Unavailable": "1"} if mode == "503-tolvyn" else None
            self._reply(int(mode.split("-")[0]), b'{"error":"stand-in"}', extra)
    return Proxy


@pytest.fixture(scope="module", autouse=True)
def standins():
    servers = []
    for name, handler in [("provider", _Provider)] + [(m, _proxy(m)) for m in
                                                       ("503", "503-tolvyn", "451", "429", "timeout", "reset")]:
        s = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        s.daemon_threads = True
        threading.Thread(target=s.serve_forever, daemon=True).start()
        PORT[name] = s.server_address[1]
        servers.append(s)
    tmp = socket.socket()
    tmp.bind(("127.0.0.1", 0))
    PORT["refused"] = tmp.getsockname()[1]
    tmp.close()
    yield
    for s in servers:
        s.shutdown()


@pytest.fixture(autouse=True)
def _clear():
    SEEN.clear()


PROVIDERS = [
    # provider, proxy path, direct base path
    ("openai", "/v1/proxy/openai/chat/completions", "/v1"),
    ("anthropic", "/v1/proxy/anthropic/v1/messages", ""),
    ("deepseek", "/v1/proxy/deepseek/chat/completions", "/v1"),
]
FALLS_OPEN = ["refused", "503-tolvyn"]
NO_FAILOPEN_STATUS = ["503", "451", "429"]
AFTER_FORWARD = ["timeout", "reset"]


def _request(provider, path, mode, http=httpx):
    headers = {"content-type": "application/json", "authorization": "Bearer tlv_x", "x-api-key": "tlv_x", **ATTR}
    return http.Request("POST", f"http://127.0.0.1:{PORT[mode]}{path}", headers=headers, content=BODY)


def _send(provider, path, base, mode, flavour, http=httpx):
    direct = f"http://127.0.0.1:{PORT['provider']}{base}"
    req = _request(provider, path, mode, http)
    if flavour == "sync":
        t = make_failopen_transport("", direct, "sk-direct", provider, http=http)
        with http.Client(transport=t, timeout=1.0) as c:
            return c.send(req)

    async def go():
        t = make_failopen_async_transport("", direct, "sk-direct", provider, http=http)
        async with http.AsyncClient(transport=t, timeout=1.0) as c:
            return await c.send(req)
    return asyncio.run(go())


def _direct():
    return [r for r in SEEN if r["via"] == "direct"]


@pytest.mark.parametrize("flavour", ["sync", "async"])
@pytest.mark.parametrize("mode", FALLS_OPEN)
@pytest.mark.parametrize("provider,path,base", PROVIDERS)
@pytest.mark.parametrize("http", HTTP_MODULES, ids=HTTP_IDS)
def test_fails_open_without_tolvyn_headers(provider, path, base, mode, flavour, http):
    resp = _send(provider, path, base, mode, flavour, http)
    assert resp.status_code == 200
    (d,) = _direct()
    assert [h for h in d["headers"] if h.startswith("x-tolvyn-")] == []
    assert "pii-" not in json.dumps(d["headers"])
    assert "tlv_" not in json.dumps(d["headers"])
    assert d["headers"]["host"] == f"127.0.0.1:{PORT['provider']}"
    assert d["body"] == BODY
    assert d["path"] == base + path.split(f"/v1/proxy/{provider}", 1)[1]


@pytest.mark.parametrize("flavour", ["sync", "async"])
@pytest.mark.parametrize("mode", NO_FAILOPEN_STATUS)
@pytest.mark.parametrize("provider,path,base", PROVIDERS)
@pytest.mark.parametrize("http", HTTP_MODULES, ids=HTTP_IDS)
def test_provider_503_and_enforcement_do_not_fail_open(provider, path, base, mode, flavour, http):
    resp = _send(provider, path, base, mode, flavour, http)
    assert resp.status_code == int(mode)
    assert SEEN == []


@pytest.mark.parametrize("flavour", ["sync", "async"])
@pytest.mark.parametrize("mode", AFTER_FORWARD)
@pytest.mark.parametrize("provider,path,base", PROVIDERS)
@pytest.mark.parametrize("http", HTTP_MODULES, ids=HTTP_IDS)
def test_failure_after_forwarding_does_not_duplicate(provider, path, base, mode, flavour, http):
    with pytest.raises(http.TransportError):
        _send(provider, path, base, mode, flavour, http)
    assert [r["via"] for r in SEEN] == ["proxy"]


def test_marked_503_is_closed_before_fallback(monkeypatch):
    seen = []
    real = httpx.HTTPTransport.handle_request

    def spy(self, request):
        r = real(self, request)
        seen.append(r)
        return r
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", spy)
    _send("openai", "/v1/proxy/openai/chat/completions", "/v1", "503-tolvyn", "sync")
    assert seen[0].status_code == 503 and seen[0].is_closed


@pytest.mark.parametrize("hdrmode", ["client", "request"])
@pytest.mark.parametrize("cls,mod,attr", [(tolvyn.OpenAI, _tc, "_OPENAI_DIRECT_URL"),
                                          (tolvyn.DeepSeek, _td, "_DEEPSEEK_DIRECT_URL")])
def test_sdk_client_strips_client_and_request_headers(monkeypatch, cls, mod, attr, hdrmode):
    monkeypatch.setattr(mod, attr, f"http://127.0.0.1:{PORT['provider']}/v1")
    kw = dict(tolvyn_api_key="tlv_x", proxy_url=f"http://127.0.0.1:{PORT['refused']}/v1/proxy/x/",
              max_retries=0, timeout=2.0, openai_api_key="sk-direct", deepseek_api_key="sk-direct")
    if cls is tolvyn.OpenAI:
        kw.pop("deepseek_api_key")
    else:
        kw.pop("openai_api_key")
    extra = {}
    if hdrmode == "client":
        kw.update(team="t-team", user="pii-user@example.com", end_customer="pii-customer-42")
    else:
        extra = ATTR
    cls(**kw).chat.completions.create(model="m", messages=[{"role": "user", "content": "hi"}], extra_headers=extra)
    (d,) = _direct()
    assert [h for h in d["headers"] if h.startswith("x-tolvyn-")] == []
    assert d["headers"]["authorization"] == "Bearer sk-direct"


# End to end through the real anthropic client, whichever major is installed:
# a refused proxy fails open to the provider with the provider key and without
# any X-Tolvyn-* header. On anthropic >= 1 this exercises the httpx2 transport.
@pytest.mark.parametrize("flavour", ["sync", "async"])
def test_anthropic_client_fails_open(monkeypatch, flavour):
    monkeypatch.setattr(_ta, "_ANTHROPIC_DIRECT_URL", f"http://127.0.0.1:{PORT['provider']}")
    kw = dict(tolvyn_api_key="tlv_x", proxy_url=f"http://127.0.0.1:{PORT['refused']}/v1/proxy/anthropic/",
              anthropic_api_key="sk-direct", max_retries=0, timeout=2.0,
              team="t-team", user="pii-user@example.com")
    args = dict(model="claude-x", max_tokens=8, messages=[{"role": "user", "content": "hi"}],
                extra_headers={"X-Tolvyn-End-Customer": "pii-customer-42"})
    if flavour == "sync":
        tolvyn.Anthropic(**kw).messages.create(**args)
    else:
        async def go():
            await tolvyn.AsyncAnthropic(**kw).messages.create(**args)
        asyncio.run(go())
    (d,) = _direct()
    assert d["path"] == "/v1/messages"
    assert d["headers"]["x-api-key"] == "sk-direct"
    assert [h for h in d["headers"] if h.startswith("x-tolvyn-")] == []
    assert d["body"] and json.loads(d["body"])["model"] == "claude-x"
