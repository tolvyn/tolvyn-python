"""Fail-open transport wrapper for httpx."""
import re
import sys
import httpx


# FAIL OPEN ONLY WHEN THE PROXY WAS NEVER REACHED. ConnectError covers refused
# connections, DNS failure and TLS handshake failure; ConnectTimeout is a timeout
# while connecting. Nothing here can have been forwarded to the provider, so a
# direct retry cannot double-bill and cannot bypass anything TOLVYN already did.
#
# DELIBERATELY ABSENT: ReadTimeout, WriteTimeout, RemoteProtocolError, ReadError.
# Each can happen AFTER the proxy forwarded the request — the provider may already
# be serving (and charging for) it — so retrying direct produced a second,
# unmetered provider call. Measured: a read timeout after forwarding gave two
# provider calls, one through TOLVYN and one around it.
_PROXY_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
)

# A 503 fails open ONLY when TOLVYN itself says it is unavailable. A plain 503 on
# the proxy path is the PROVIDER's own 503 passed through (the server never
# writes 503 on /v1/proxy/), and retrying it direct only moved the spend out of
# TOLVYN's view. Enforcement responses (451 kill switch, 429 budget/quota) never
# fail open either.
TOLVYN_UNAVAILABLE_HEADER = "x-tolvyn-unavailable"


def _is_tolvyn_unavailable(response: httpx.Response) -> bool:
    return response.status_code == 503 and response.headers.get(TOLVYN_UNAVAILABLE_HEADER, "").strip() == "1"


_PROXY_PREFIX_RE = re.compile(r"^/v1/proxy/(?:openai|anthropic|google|deepseek)/")


def _should_failopen(exc: Exception) -> bool:
    """Return True only if the proxy was never reached (see _PROXY_ERRORS)."""
    return isinstance(exc, _PROXY_ERRORS)


def _build_fallback_url(request_url: httpx.URL, fallback_base: str) -> httpx.URL:
    """Build the direct-provider URL from a proxy request URL.

    Strips the /v1/proxy/{provider}/ prefix from the request path, then prepends
    the fallback base URL's path (e.g. "/v1" for OpenAI, "" for Anthropic) so
    the final URL hits the real provider endpoint.

    Example (OpenAI):
        request_url:    https://proxy.tolvyn.io/v1/proxy/openai/chat/completions
        fallback_base:  https://api.openai.com/v1
        → https://api.openai.com/v1/chat/completions

    Example (Anthropic):
        request_url:    https://proxy.tolvyn.io/v1/proxy/anthropic/v1/messages
        fallback_base:  https://api.anthropic.com
        → https://api.anthropic.com/v1/messages
    """
    fb = httpx.URL(fallback_base)
    fb_base_path = fb.path.rstrip("/")  # "/v1" or ""

    stripped = _PROXY_PREFIX_RE.sub("/", request_url.path)
    final_path = fb_base_path + stripped

    return request_url.copy_with(
        host=fb.host,
        scheme=fb.scheme,
        port=fb.port,
        path=final_path,
    )


# The header each provider's DIRECT API reads the API key from. The TOLVYN proxy
# accepts Authorization/x-api-key/x-goog-api-key interchangeably, but the
# providers themselves do NOT: Anthropic authenticates only via x-api-key and
# Google only via x-goog-api-key — sending Bearer to them 401s.
_PROVIDER_AUTH_HEADER = {
    "openai": "authorization",
    "anthropic": "x-api-key",
    "google": "x-goog-api-key",
    "deepseek": "authorization",  # OpenAI-compatible; Bearer auth (same as the default)
}

# Every auth header that may carry the TOLVYN key on the inbound proxy request.
# All are stripped before the correct provider header is set, so the TOLVYN key
# is never leaked to the provider on a fail-open direct call.
_ALL_AUTH_HEADERS = ("authorization", "x-api-key", "x-goog-api-key")


def _apply_fallback_auth(headers: dict, provider: str, fallback_key: str) -> None:
    """Rewrite *headers* in place to authenticate a direct provider call.

    Strips every inbound auth header (each may carry the TOLVYN key) and sets the
    single header the provider's direct API expects, with the provider's own key:
      - OpenAI    -> Authorization: Bearer <key>
      - Anthropic -> x-api-key: <key>
      - Google    -> x-goog-api-key: <key>

    Fixes PY-08 (Bearer sent to Anthropic/Google → 401) and PY-09 (the TOLVYN key
    in the original x-api-key/x-goog-api-key leaking to the provider on fallback).
    httpx lowercases header keys in dict(request.headers), so keys are lowercase.
    """
    for h in _ALL_AUTH_HEADERS:
        headers.pop(h, None)
    header = _PROVIDER_AUTH_HEADER.get(provider.lower(), "authorization")
    headers[header] = f"Bearer {fallback_key}" if header == "authorization" else fallback_key


# Never copied onto the direct request. `host` is the PROXY's host — sending it to
# the provider names the wrong virtual host; content-length and the hop-by-hop
# headers are recomputed for the new request.
_NOT_FORWARDED = frozenset({"host", "content-length", "transfer-encoding", "connection",
                            "keep-alive", "te", "trailer", "upgrade", "proxy-connection"})


def _fallback_headers(request_headers, provider: str, fallback_key: str) -> dict:
    """Headers for the direct provider request.

    Drops every X-Tolvyn-* header in any casing, whether the client set it at
    construction or the caller passed it per request: they carry attribution —
    X-Tolvyn-User and X-Tolvyn-End-Customer can be personal data — and mean
    nothing to the provider. Then replaces auth with the provider's own key.
    """
    headers = {k: v for k, v in request_headers.items()
               if k.lower() not in _NOT_FORWARDED and not k.lower().startswith("x-tolvyn-")}
    _apply_fallback_auth(headers, provider, fallback_key)
    return headers


def make_failopen_transport(
    proxy_url: str,
    fallback_url: str,
    fallback_key: str,
    provider: str,
) -> httpx.HTTPTransport:
    """
    Return an httpx.HTTPTransport subclass that retries against the fallback
    URL only when the proxy was never reached, or answered 503 with
    X-Tolvyn-Unavailable: 1.
    """

    class FailOpenTransport(httpx.HTTPTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            body = request.read()  # buffered once, replayed intact on fallback
            try:
                response = super().handle_request(request)
            except Exception as exc:
                if not _should_failopen(exc) or not fallback_key:
                    raise
            else:
                if not (fallback_key and _is_tolvyn_unavailable(response)):
                    return response
                response.close()  # discard TOLVYN's 503 before going direct
            print(
                f"TOLVYN proxy unreachable — routing direct to {provider} (fail-open)",
                file=sys.stderr,
            )
            fallback_req = httpx.Request(
                method=request.method,
                url=_build_fallback_url(request.url, fallback_url),
                headers=_fallback_headers(request.headers, provider, fallback_key),
                content=body,
            )
            return httpx.HTTPTransport().handle_request(fallback_req)

    return FailOpenTransport()


def make_failopen_async_transport(
    proxy_url: str,
    fallback_url: str,
    fallback_key: str,
    provider: str,
) -> httpx.AsyncHTTPTransport:
    """Async variant of the fail-open transport."""

    class AsyncFailOpenTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            body = await request.aread()  # buffered once, replayed intact on fallback
            try:
                response = await super().handle_async_request(request)
            except Exception as exc:
                if not _should_failopen(exc) or not fallback_key:
                    raise
            else:
                if not (fallback_key and _is_tolvyn_unavailable(response)):
                    return response
                await response.aclose()  # discard TOLVYN's 503 before going direct
            print(
                f"TOLVYN proxy unreachable — routing direct to {provider} (fail-open)",
                file=sys.stderr,
            )
            fallback_req = httpx.Request(
                method=request.method,
                url=_build_fallback_url(request.url, fallback_url),
                headers=_fallback_headers(request.headers, provider, fallback_key),
                content=body,
            )
            return await httpx.AsyncHTTPTransport().handle_async_request(fallback_req)

    return AsyncFailOpenTransport()
