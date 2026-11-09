"""HTTP boundary with sanitized errors; no retries, redirects, or logging."""
from contextlib import nullcontext
import httpx
from backend.errors import UpstreamError

TIMEOUT = httpx.Timeout(90.0, connect=10.0)

def post_json(url, headers, payload, stage, client=None):
    manager = nullcontext(client) if client is not None else httpx.Client()
    try:
        with manager as connection:
            response = connection.post(url, headers=headers, json=payload,
                                       timeout=TIMEOUT, follow_redirects=False)
            if not 200 <= response.status_code < 300:
                raise UpstreamError(stage, "http_error", response.status_code)
            try:
                return response.json()
            except ValueError:
                raise UpstreamError(stage, "invalid_json") from None
    except httpx.TimeoutException:
        raise UpstreamError(stage, "timeout") from None
    except httpx.RequestError:
        raise UpstreamError(stage, "connection_error") from None
