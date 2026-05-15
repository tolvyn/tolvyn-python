"""TOLVYN OpenAI wrapper — thin drop-in over the official openai package."""
from __future__ import annotations

import openai as _openai
import httpx

from tolvyn._config import resolve_tolvyn_key, resolve_proxy_url, resolve_fallback_key
from tolvyn._failopen import make_failopen_transport, make_failopen_async_transport

_OPENAI_DEFAULT_URL = "https://proxy.tolvyn.io/v1/proxy/openai/"
_OPENAI_DIRECT_URL = "https://api.openai.com/v1"


def _build_tolvyn_headers(
    team: str | None,
    service: str | None,
    feature: str | None,
    agent: str | None,
    user: str | None,
    end_customer: str | None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if team:
        headers["X-Tolvyn-Team"] = team
    if service:
        headers["X-Tolvyn-Service"] = service
    if feature:
        headers["X-Tolvyn-Feature"] = feature
    if agent:
        headers["X-Tolvyn-Agent"] = agent
    if user:
        headers["X-Tolvyn-User"] = user
    if end_customer:
        headers["X-Tolvyn-End-Customer"] = end_customer
    return headers


class OpenAI(_openai.OpenAI):
    """
    Drop-in replacement for openai.OpenAI that routes through TOLVYN proxy.

    Usage::

        from tolvyn import OpenAI
        client = OpenAI(tolvyn_api_key="tlv_live_...")
        # Everything else identical to openai.OpenAI
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
        openai_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _OPENAI_DEFAULT_URL)
        fallback = resolve_fallback_key(openai_api_key, "OPENAI_API_KEY")
        headers = _build_tolvyn_headers(team, service, feature, agent, user, end_customer)

        # Build custom httpx client with fail-open transport if requested.
        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_transport(url, _OPENAI_DIRECT_URL, fallback, "OpenAI")
            kwargs["http_client"] = httpx.Client(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback


class AsyncOpenAI(_openai.AsyncOpenAI):
    """Async variant of the TOLVYN OpenAI wrapper."""

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
        openai_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _OPENAI_DEFAULT_URL)
        fallback = resolve_fallback_key(openai_api_key, "OPENAI_API_KEY")
        headers = _build_tolvyn_headers(team, service, feature, agent, user, end_customer)

        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_async_transport(url, _OPENAI_DIRECT_URL, fallback, "OpenAI")
            kwargs["http_client"] = httpx.AsyncClient(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback
