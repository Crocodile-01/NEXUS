import httpx

from app.core.config import settings


def get_httpx_client(
    timeout_seconds: int | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """
    Factory creating a configured AsyncClient with default NEXUS User-Agent and timeouts.
    """
    default_timeout = timeout_seconds if timeout_seconds is not None else settings.REQUEST_TIMEOUT_SECONDS
    default_headers = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
    }
    if headers:
        default_headers.update(headers)

    return httpx.AsyncClient(
        headers=default_headers,
        timeout=httpx.Timeout(default_timeout, connect=5.0),
        follow_redirects=True,
    )
