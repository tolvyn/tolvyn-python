"""BE-515: every client builds with a fallback key (fail-open on) on the
dependency versions pyproject.toml allows. anthropic 1.x (httpx2) raised
TypeError here, for sync and async alike."""
import warnings

import pytest

import tolvyn

CLIENTS = [
    ("OpenAI", "openai_api_key"), ("AsyncOpenAI", "openai_api_key"),
    ("DeepSeek", "deepseek_api_key"), ("AsyncDeepSeek", "deepseek_api_key"),
    ("Anthropic", "anthropic_api_key"), ("AsyncAnthropic", "anthropic_api_key"),
]


@pytest.mark.parametrize("name,keyarg", CLIENTS)
def test_client_builds_with_fallback_key(name, keyarg):
    client = getattr(tolvyn, name)(tolvyn_api_key="tlv_test_x", **{keyarg: "sk-direct"})
    assert client._tolvyn_fail_open is True


def test_google_builds_with_fallback_key():
    pytest.importorskip("google.generativeai")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tolvyn.Google(tolvyn_api_key="tlv_test_x", google_api_key="sk-direct")
