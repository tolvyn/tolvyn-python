"""BE-90: DeepSeek wrapper fail-open tests (Python SDK, mirrors Node v1.0.9).

Written BEFORE the implementation. On current code:
  - _build_fallback_url test  -> RED (_PROXY_PREFIX_RE excludes `deepseek`, so the
    proxy prefix is not stripped and the path doubles to /v1/v1/proxy/deepseek/...)
  - end-to-end fail-open       -> RED (same regex gap -> retry URL has the wrong path)
  - construction tests         -> RED (DeepSeek/AsyncDeepSeek not exported yet)
  - _apply_fallback_auth test  -> GREEN already (unknown providers default to
    `authorization: Bearer`, exactly what DeepSeek needs) — pinned so it can't
    regress when `deepseek` is added to the map.
"""
import httpx
import pytest


# ── Wrapper wiring: export, proxy base_url, fail-open attributes ───────────────

def test_imports_deepseek():
    from tolvyn import DeepSeek, AsyncDeepSeek
    assert DeepSeek is not None
    assert AsyncDeepSeek is not None


def test_constructor_deepseek():
    from tolvyn import DeepSeek
    client = DeepSeek(
        tolvyn_api_key="tlv_live_test",
        proxy_url="http://localhost:8081/v1/proxy/deepseek",
    )
    assert str(client.base_url).rstrip("/") == "http://localhost:8081/v1/proxy/deepseek"
    assert client.api_key == "tlv_live_test"


def test_failopen_attributes_deepseek():
    from tolvyn import DeepSeek
    client = DeepSeek(
        tolvyn_api_key="tlv_live_test",
        fail_open=True,
        deepseek_api_key="sk-deepseek-fallback",
        proxy_url="http://localhost:8081/v1/proxy/deepseek",
    )
    assert client._tolvyn_fail_open is True
    assert client._tolvyn_fallback_key == "sk-deepseek-fallback"


def test_async_constructor_deepseek():
    from tolvyn import AsyncDeepSeek
    client = AsyncDeepSeek(
        tolvyn_api_key="tlv_live_test",
        proxy_url="http://localhost:8081/v1/proxy/deepseek",
    )
    assert str(client.base_url).rstrip("/") == "http://localhost:8081/v1/proxy/deepseek"


# ── Regression: fallback URL lands on api.deepseek.com, NOT api.openai.com ─────

def test_build_fallback_url_deepseek():
    from tolvyn._failopen import _build_fallback_url
    url = _build_fallback_url(
        httpx.URL("https://proxy.tolvyn.io/v1/proxy/deepseek/chat/completions"),
        "https://api.deepseek.com/v1",
    )
    assert url.host == "api.deepseek.com"
    assert url.host != "api.openai.com"  # must not bleed into OpenAI
    # The regex fix is what makes the PATH correct (no doubled /v1/proxy/deepseek):
    assert url.path == "/v1/chat/completions"
    assert str(url) == "https://api.deepseek.com/v1/chat/completions"


# ── Direct-call auth for DeepSeek -> Bearer, no key-header leak ─────────────────

def test_fallback_auth_deepseek():
    from tolvyn._failopen import _apply_fallback_auth
    h = {
        "authorization": "Bearer tlv_live_secret",
        "x-api-key": "tlv_live_secret",
        "content-type": "application/json",
    }
    _apply_fallback_auth(h, "DeepSeek", "sk-deepseek-fallback")
    assert h["authorization"] == "Bearer sk-deepseek-fallback"
    assert "x-api-key" not in h and "x-goog-api-key" not in h
    assert "tlv_live_secret" not in h.values()  # no TOLVYN-key leak
    assert h["content-type"] == "application/json"  # non-auth preserved


# ── End-to-end: proxy ConnectError -> retry hits api.deepseek.com with the key ─
# Fills the gap: no existing test drives make_failopen_transport through a real
# proxy-outage -> direct-retry cycle. Mocks the underlying httpx.HTTPTransport so
# the proxy call fails and the fallback call is captured.

def test_failopen_transport_deepseek_retries_deepseek(monkeypatch):
    from tolvyn._failopen import make_failopen_transport

    calls = {"n": 0, "url": None, "headers": None}

    def fake_handle_request(self, request):
        calls["n"] += 1
        if calls["n"] == 1:
            # First call = the TOLVYN proxy -> simulate it being unreachable.
            raise httpx.ConnectError("connection refused", request=request)
        # Second call = the direct DeepSeek fallback -> capture and succeed.
        calls["url"] = str(request.url)
        calls["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake_handle_request)

    transport = make_failopen_transport(
        "https://proxy.tolvyn.io/v1/proxy/deepseek/",
        "https://api.deepseek.com/v1",
        "sk-deepseek-key",
        "DeepSeek",
    )
    request = httpx.Request(
        "POST",
        "https://proxy.tolvyn.io/v1/proxy/deepseek/chat/completions",
        headers={"authorization": "Bearer tlv_live_secret"},
    )
    response = transport.handle_request(request)

    assert response.status_code == 200
    assert calls["n"] == 2  # proxy failed, direct retried
    assert calls["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert "api.openai.com" not in calls["url"]
    assert calls["headers"]["authorization"] == "Bearer sk-deepseek-key"
