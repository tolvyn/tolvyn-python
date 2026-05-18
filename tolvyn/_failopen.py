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
                new_headers["authorization"] = f"Bearer {fallback_key}"
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
                new_headers["authorization"] = f"Bearer {fallback_key}"
                fallback_req = httpx.Request(
                    method=request.method,
                    url=new_url,
                    headers=new_headers,
                    content=request.content,
                )
                transport = httpx.AsyncHTTPTransport()
                return await transport.handle_async_request(fallback_req)

    return AsyncFailOpenTransport()
