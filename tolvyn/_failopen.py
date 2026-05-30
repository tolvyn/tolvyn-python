"""Fail-open transport wrapper for httpx."""
import re
import sys
import httpx


_PROXY_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)

_PROXY_PREFIX_RE = re.compile(r"^/v1/proxy/(?:openai|anthropic|google)/")


def _should_failopen(exc: Exception) -> bool:
    """Return True if the error indicates the proxy is unreachable (not a real API error)."""
    if isinstance(exc, _PROXY_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 503
    return False


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


def make_failopen_transport(
    proxy_url: str,
    fallback_url: str,
    fallback_key: str,
    provider: str,
) -> httpx.HTTPTransport:
    """
    Return an httpx.HTTPTransport subclass that retries against the fallback
    URL when the proxy is unreachable or returns 503.
    """

    class FailOpenTransport(httpx.HTTPTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            try:
                response = super().handle_request(request)
                if response.status_code == 503:
                    raise httpx.HTTPStatusError(
                        "503 from proxy", request=request, response=response
                    )
                return response
            except Exception as exc:
                if not _should_failopen(exc) or not fallback_key:
                    raise
                print(
                    f"TOLVYN proxy unreachable — routing direct to {provider} (fail-open)",
                    file=sys.stderr,
                )
                new_url = _build_fallback_url(request.url, fallback_url)
                new_headers = dict(request.headers)
                _apply_fallback_auth(new_headers, provider, fallback_key)
                fallback_req = httpx.Request(
                    method=request.method,
                    url=new_url,
                    headers=new_headers,
                    content=request.content,
                )
                transport = httpx.HTTPTransport()
                return transport.handle_request(fallback_req)

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
            try:
                response = await super().handle_async_request(request)
                if response.status_code == 503:
                    raise httpx.HTTPStatusError(
                        "503 from proxy", request=request, response=response
                    )
                return response
            except Exception as exc:
                if not _should_failopen(exc) or not fallback_key:
                    raise
                print(
                    f"TOLVYN proxy unreachable — routing direct to {provider} (fail-open)",
                    file=sys.stderr,
                )
                new_url = _build_fallback_url(request.url, fallback_url)
                new_headers = dict(request.headers)
                _apply_fallback_auth(new_headers, provider, fallback_key)
                fallback_req = httpx.Request(
                    method=request.method,
                    url=new_url,
                    headers=new_headers,
                    content=request.content,
                )
                transport = httpx.AsyncHTTPTransport()
                return await transport.handle_async_request(fallback_req)

    return AsyncFailOpenTransport()
