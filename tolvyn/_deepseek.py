"""TOLVYN DeepSeek wrapper — thin drop-in over the official openai package.

DeepSeek exposes an OpenAI-compatible API, so this wraps the same `openai`
package as the OpenAI wrapper but points the proxy/fallback at DeepSeek and
falls back with the DeepSeek key. Fail-open routes direct to
https://api.deepseek.com/v1 (Bearer auth) when the TOLVYN proxy is unreachable.
"""
from __future__ import annotations

import openai as _openai
import httpx

from tolvyn._config import (
    build_tolvyn_headers,
    resolve_fallback_key,
    resolve_proxy_url,
    resolve_tolvyn_key,
)
from tolvyn._failopen import make_failopen_transport, make_failopen_async_transport

_DEEPSEEK_DEFAULT_URL = "https://proxy.tolvyn.io/v1/proxy/deepseek/"
_DEEPSEEK_DIRECT_URL = "https://api.deepseek.com/v1"


class DeepSeek(_openai.OpenAI):
    """
    Drop-in replacement for openai.OpenAI pointed at DeepSeek, routed through TOLVYN.

    Usage::

        from tolvyn import DeepSeek
        client = DeepSeek(tolvyn_api_key="tlv_live_...")
        client.chat.completions.create(model="deepseek-chat", messages=[...])
    """

    def __init__(
        self,
        tolvyn_api_key: str | None = None,
        proxy_url: str | None = None,
        team: str | None = None,
        service: str | None = None,
        feature: str | None = None,
        agent: str | None = None,
        user: str | None = None,
        end_customer: str | None = None,
        fail_open: bool = True,
        deepseek_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _DEEPSEEK_DEFAULT_URL)
        fallback = resolve_fallback_key(deepseek_api_key, "DEEPSEEK_API_KEY")
        headers = build_tolvyn_headers(team, service, feature, agent, user, end_customer)

        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_transport(url, _DEEPSEEK_DIRECT_URL, fallback, "DeepSeek")
            kwargs["http_client"] = httpx.Client(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback


class AsyncDeepSeek(_openai.AsyncOpenAI):
    """Async variant of the TOLVYN DeepSeek wrapper."""

    def __init__(
        self,
        tolvyn_api_key: str | None = None,
        proxy_url: str | None = None,
        team: str | None = None,
        service: str | None = None,
        feature: str | None = None,
        agent: str | None = None,
        user: str | None = None,
        end_customer: str | None = None,
        fail_open: bool = True,
        deepseek_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _DEEPSEEK_DEFAULT_URL)
        fallback = resolve_fallback_key(deepseek_api_key, "DEEPSEEK_API_KEY")
        headers = build_tolvyn_headers(team, service, feature, agent, user, end_customer)

        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_async_transport(url, _DEEPSEEK_DIRECT_URL, fallback, "DeepSeek")
            kwargs["http_client"] = httpx.AsyncClient(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback
