"""Unit tests for the TOLVYN Python SDK."""
import os
import pytest


# ── Test 1: Imports ───────────────────────────────────────────────────────────

def test_imports():
    from tolvyn import OpenAI, Anthropic, AsyncOpenAI, AsyncAnthropic
    assert OpenAI is not None
    assert Anthropic is not None
    assert AsyncOpenAI is not None
    assert AsyncAnthropic is not None


# ── Test 2: Constructor sets correct base_url and api_key ────────────────────

def test_constructor_openai():
    from tolvyn import OpenAI
    client = OpenAI(
        tolvyn_api_key="tlv_live_test",
        proxy_url="http://localhost:8081/v1/proxy/openai",
    )
    assert str(client.base_url).rstrip("/") == "http://localhost:8081/v1/proxy/openai"
    assert client.api_key == "tlv_live_test"


# ── Test 3: Tag headers injected; empty tags NOT sent ─────────────────────────

def test_tag_headers_openai():
    from tolvyn import OpenAI
    client = OpenAI(
        tolvyn_api_key="tlv_live_test",
        team="eng",
        service="chatbot",
        proxy_url="http://localhost:8081/v1/proxy/openai",
    )
    # Headers are stored in _custom_headers or default_headers depending on openai version.
    # Check via the client's internal default_headers dict.
    headers = dict(client.default_headers)
    assert headers.get("X-Tolvyn-Team") == "eng"
    assert headers.get("X-Tolvyn-Service") == "chatbot"
    assert "X-Tolvyn-Feature" not in headers
    assert "X-Tolvyn-Agent" not in headers


# ── Test 4: Env var resolution ───────────────────────────────────────────────

def test_env_var_resolution(monkeypatch):
    from tolvyn import OpenAI
    monkeypatch.setenv("TOLVYN_API_KEY", "tlv_live_from_env")
    monkeypatch.delenv("TOLVYN_PROXY_URL", raising=False)
    client = OpenAI()
    assert client.api_key == "tlv_live_from_env"


# ── Test 5: Missing key raises ValueError ─────────────────────────────────────

def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("TOLVYN_API_KEY", raising=False)
    from tolvyn import OpenAI
    with pytest.raises(ValueError, match="tolvyn_api_key required"):
        OpenAI()


# ── Test 6: Fail-open attributes stored ──────────────────────────────────────

def test_failopen_attributes():
    from tolvyn import OpenAI
    client = OpenAI(
        tolvyn_api_key="tlv_live_test",
        fail_open=True,
        openai_api_key="sk-fallback",
        proxy_url="http://localhost:8081/v1/proxy/openai",
    )
    assert client._tolvyn_fail_open is True
    assert client._tolvyn_fallback_key == "sk-fallback"


# ── Test 7: Integration — real proxy round-trip ───────────────────────────────

@pytest.mark.integration
def test_proxy_roundtrip_openai():
    from tolvyn import OpenAI
    key = os.environ.get("TOLVYN_API_KEY")
    if not key:
        pytest.skip("TOLVYN_API_KEY not set")
    client = OpenAI(
        tolvyn_api_key=key,
        proxy_url="http://localhost:8081/v1/proxy/openai",
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "say hello in one word"}],
        max_tokens=5,
    )
    assert response.choices[0].message.content is not None


# ── Anthropic variants ────────────────────────────────────────────────────────

def test_anthropic_constructor():
    from tolvyn import Anthropic
    client = Anthropic(
        tolvyn_api_key="tlv_live_test",
        proxy_url="http://localhost:8081/v1/proxy/anthropic",
    )
    assert str(client.base_url).rstrip("/") == "http://localhost:8081/v1/proxy/anthropic"
    assert client.api_key == "tlv_live_test"


def test_anthropic_tag_headers():
    from tolvyn import Anthropic
    client = Anthropic(
        tolvyn_api_key="tlv_live_test",
        team="ml-team",
        feature="summarizer",
        proxy_url="http://localhost:8081/v1/proxy/anthropic",
    )
    headers = dict(client.default_headers)
    assert headers.get("X-Tolvyn-Team") == "ml-team"
    assert headers.get("X-Tolvyn-Feature") == "summarizer"
    assert "X-Tolvyn-Service" not in headers


# ── Fail-open direct auth (PY-08 / PY-09) ─────────────────────────────────────

def test_fallback_auth_openai():
    from tolvyn._failopen import _apply_fallback_auth
    # OpenAI's proxy request carries Authorization: Bearer <tolvyn key>.
    h = {"authorization": "Bearer tlv_live_secret", "content-type": "application/json"}
    _apply_fallback_auth(h, "OpenAI", "sk-openai-fallback")
    assert h["authorization"] == "Bearer sk-openai-fallback"
    assert "x-api-key" not in h and "x-goog-api-key" not in h
    assert h["content-type"] == "application/json"  # non-auth headers preserved


def test_fallback_auth_anthropic_strips_tolvyn_key():
    from tolvyn._failopen import _apply_fallback_auth
    # Anthropic SDK sends the TOLVYN key in x-api-key — it MUST NOT leak, and the
    # direct call must use x-api-key (not Bearer) with the provider key.
    h = {"x-api-key": "tlv_live_secret", "anthropic-version": "2023-06-01"}
    _apply_fallback_auth(h, "Anthropic", "sk-ant-fallback")
    assert h["x-api-key"] == "sk-ant-fallback"          # provider key, not TOLVYN key
    assert "tlv_live_secret" not in h.values()           # PY-09: no leak
    assert "authorization" not in h                       # PY-08: no Bearer
    assert h["anthropic-version"] == "2023-06-01"         # required header preserved


def test_fallback_auth_google_strips_tolvyn_key():
    from tolvyn._failopen import _apply_fallback_auth
    h = {"x-goog-api-key": "tlv_live_secret"}
    _apply_fallback_auth(h, "Google", "goog-fallback")
    assert h["x-goog-api-key"] == "goog-fallback"
    assert "tlv_live_secret" not in h.values()
    assert "authorization" not in h and "x-api-key" not in h


def test_fallback_auth_strips_all_inbound_auth():
    from tolvyn._failopen import _apply_fallback_auth
    # Defensive: even if multiple auth headers are present, only the correct one survives.
    h = {"authorization": "Bearer tlv", "x-api-key": "tlv", "x-goog-api-key": "tlv"}
    _apply_fallback_auth(h, "anthropic", "sk-ant-fallback")
    assert h == {"x-api-key": "sk-ant-fallback"}
