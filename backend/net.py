"""SSRF-aware outbound HTTP used by the API and Webhook nodes."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from .config import get_settings

MAX_REDIRECTS = 3
_BLOCKED_REQUEST_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}


class NetworkError(Exception):
    """Raised when a request is blocked or cannot be completed."""


@dataclass
class SafeResponse:
    status: int
    url: str
    content_type: str
    text: str
    truncated: bool


def _check_destination(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise NetworkError("Only http:// and https:// URLs are supported")
    host = parsed.hostname
    if not host:
        raise NetworkError("URL has no host")
    if get_settings().allow_private_network:
        return
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise NetworkError(f"Could not resolve host '{host}'") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        if not address.is_global:
            raise NetworkError(
                f"Requests to private or internal addresses are blocked ({host}). "
                "Set NEXFLOW_ALLOW_PRIVATE_NETWORK=true to allow them."
            )


def safe_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    content: bytes | None = None,
    timeout: float = 20.0,
) -> SafeResponse:
    import httpx  # imported lazily so pure-logic modules stay importable without it

    settings = get_settings()
    clean_headers = {
        str(k): str(v)
        for k, v in (headers or {}).items()
        if str(k).lower() not in _BLOCKED_REQUEST_HEADERS
    }
    current_method, current_url, body = method.upper(), url, content

    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _check_destination(current_url)
            try:
                with client.stream(current_method, current_url, headers=clean_headers, content=body) as resp:
                    if resp.status_code in {301, 302, 303, 307, 308} and "location" in resp.headers:
                        current_url = urljoin(current_url, resp.headers["location"])
                        if resp.status_code in {301, 302, 303} and current_method not in {"GET", "HEAD"}:
                            current_method, body = "GET", None
                        continue
                    chunks: list[bytes] = []
                    size, truncated = 0, False
                    for chunk in resp.iter_bytes():
                        size += len(chunk)
                        if size > settings.max_response_bytes:
                            keep = len(chunk) - (size - settings.max_response_bytes)
                            chunks.append(chunk[:max(keep, 0)])
                            truncated = True
                            break
                        chunks.append(chunk)
                    return SafeResponse(
                        status=resp.status_code,
                        url=str(resp.url),
                        content_type=resp.headers.get("content-type", ""),
                        text=b"".join(chunks).decode("utf-8", errors="replace"),
                        truncated=truncated,
                    )
            except httpx.TimeoutException as exc:
                raise NetworkError(f"Request timed out after {timeout:.0f}s") from exc
            except httpx.HTTPError as exc:
                raise NetworkError(f"Request failed: {exc}") from exc
    raise NetworkError(f"Too many redirects (more than {MAX_REDIRECTS})")
