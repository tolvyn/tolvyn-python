"""TOLVYN Anthropic wrapper — thin drop-in over the official anthropic package."""
from __future__ import annotations

import anthropic as _anthropic
import httpx

from tolvyn._config import resolve_tolvyn_key, resolve_proxy_url, resolve_fallback_key
from tolvyn._failopen import make_failopen_transport, make_failopen_async_transport

_ANTHROPIC_DEFAULT_URL = "https://proxy.tolvyn.io/v1/proxy/anthropic/"
_ANTHROPIC_DIRECT_URL = "https://api.anthropic.com"


def _build_tolvyn_headers(
    team: str | None,
    service: str | None,
    feature: str | None,
    agent: str | None,
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
    return headers


class Anthropic(_anthropic.Anthropic):
    """
    Drop-in replacement for anthropic.Anthropic that routes through TOLVYN proxy.

    Usage::

        from tolvyn import Anthropic
        client = Anthropic(tolvyn_api_key="tlv_live_...")
    """

    def __init__(
        self,
        tolvyn_api_key: str | None = None,
        proxy_url: str | None = None,
        team: str | None = None,
        service: str | None = None,
        feature: str | None = None,
        agent: str | None = None,
        fail_open: bool = True,
        anthropic_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _ANTHROPIC_DEFAULT_URL)
        fallback = resolve_fallback_key(anthropic_api_key, "ANTHROPIC_API_KEY")
        headers = _build_tolvyn_headers(team, service, feature, agent)

        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_transport(url, _ANTHROPIC_DIRECT_URL, fallback, "Anthropic")
            kwargs["http_client"] = httpx.Client(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback


class AsyncAnthropic(_anthropic.AsyncAnthropic):
    """Async variant of the TOLVYN Anthropic wrapper."""

    def __init__(
        self,
        tolvyn_api_key: str | None = None,
        proxy_url: str | None = None,
        team: str | None = None,
        service: str | None = None,
        feature: str | None = None,
        agent: str | None = None,
        fail_open: bool = True,
        anthropic_api_key: str | None = None,
        **kwargs,
    ) -> None:
        key = resolve_tolvyn_key(tolvyn_api_key)
        url = resolve_proxy_url(proxy_url, _ANTHROPIC_DEFAULT_URL)
        fallback = resolve_fallback_key(anthropic_api_key, "ANTHROPIC_API_KEY")
        headers = _build_tolvyn_headers(team, service, feature, agent)

        if fail_open and fallback and "http_client" not in kwargs:
            transport = make_failopen_async_transport(url, _ANTHROPIC_DIRECT_URL, fallback, "Anthropic")
            kwargs["http_client"] = httpx.AsyncClient(transport=transport)

        super().__init__(
            api_key=key,
            base_url=url,
            default_headers=headers,
            **kwargs,
        )

        self._tolvyn_fail_open: bool = fail_open
        self._tolvyn_fallback_key: str | None = fallback
