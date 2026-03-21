"""Fail-open transport wrapper for httpx."""
import sys
import httpx


_PROXY_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.RemoteProtocolError,
)


def _should_failopen(exc: Exception) -> bool:
    """Return True if the error indicates the proxy is unreachable (not a real API error)."""
    if isinstance(exc, _PROXY_ERRORS):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 503
    return False


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
                # Rebuild request pointing at the real API.
                new_url = httpx.URL(str(request.url)).copy_with(
                    host=httpx.URL(fallback_url).host,
                    scheme=httpx.URL(fallback_url).scheme,
                    port=httpx.URL(fallback_url).port,
                )
                new_headers = dict(request.headers)
                new_headers["authorization"] = f"Bearer {fallback_key}"
                new_request = request.stream.__class__  # keep stream type
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
                new_url = httpx.URL(str(request.url)).copy_with(
                    host=httpx.URL(fallback_url).host,
                    scheme=httpx.URL(fallback_url).scheme,
                    port=httpx.URL(fallback_url).port,
                )
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
