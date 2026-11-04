"""Fetches one public web page for the link source, with guards against the own network."""
from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from src.limits import (
    WEB_PAGE_CONNECT_TIMEOUT_SECONDS,
    WEB_PAGE_MAX_HTML_BYTES,
    WEB_PAGE_MAX_PDF_BYTES,
    WEB_PAGE_MAX_REDIRECTS,
    WEB_PAGE_MAX_URL_CHARS,
    WEB_PAGE_TIMEOUT_SECONDS,
)

USER_AGENT = "askFrancis/1.0"
_ACCEPT = "text/html, application/xhtml+xml, application/pdf, text/plain;q=0.8"
_ALLOWED_PORTS = (None, 80, 443)
# Names that never need a lookup to be known as the own machine.
_LOCAL_NAMES = ("localhost", "localhost.localdomain")


class LinkError(Exception):
    """A rejected link carries the message key and the HTTP status the route answers with."""

    def __init__(self, key: str, status: int, /, **params: object):
        super().__init__(key)
        self.key = key
        self.status = status
        self.params = params


@dataclass
class FetchedPage:
    kind: str  # "html", "text" or "pdf"
    body: bytes
    final_url: str
    content_type: str


def normalize_url(raw: str) -> str:
    """Lower-cased host, no fragment, no trailing slash, for the duplicate check only."""
    parts = urlsplit(raw.strip())
    host = (parts.hostname or "").lower()
    try:
        port = parts.port
    except ValueError:
        port = None
    if port and port not in (80, 443):
        host = f"{host}:{port}"
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), host, path, parts.query, ""))


def validate_url(raw: str) -> str:
    """Rejects everything but a plain public http(s) link and returns the trimmed link."""
    raw = raw.strip()
    if not raw or len(raw) > WEB_PAGE_MAX_URL_CHARS:
        raise LinkError("ai.link.invalid", 400)
    # urlsplit silently drops \t \r \n, so a control character must be caught before it does.
    if any(ch.isascii() and not ch.isprintable() for ch in raw):
        raise LinkError("ai.link.invalid", 400)
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise LinkError("ai.link.invalid", 400)
    if parts.username or parts.password:
        raise LinkError("ai.link.invalid", 400)
    try:
        port = parts.port
    except ValueError:
        raise LinkError("ai.link.invalid", 400)
    if port not in _ALLOWED_PORTS:
        raise LinkError("ai.link.invalid", 400)
    _require_public_host(parts.hostname)
    return raw


def _resolve(host: str) -> list[str]:
    """Every address the name points to, v4 and v6, patched in tests."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _is_public(address: str) -> bool:
    """Only globally routable unicast counts, mapped v4 is judged as v4."""
    ip = ipaddress.ip_address(address.split("%")[0])
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_global and not ip.is_multicast


def _require_public_host(host: str) -> None:
    if host.lower() in _LOCAL_NAMES:
        raise LinkError("ai.link.forbiddenAddress", 400)
    try:
        addresses = _resolve(host)
    except (socket.gaierror, UnicodeError):
        raise LinkError("ai.link.unreachable", 502)
    if not addresses or not all(_is_public(a) for a in addresses):
        raise LinkError("ai.link.forbiddenAddress", 400)


def fetch_page(url: str, transport: httpx.BaseTransport | None = None) -> FetchedPage:
    """Follows a few redirects, checks every hop, caps size and time."""
    current = validate_url(url)
    timeout = httpx.Timeout(WEB_PAGE_TIMEOUT_SECONDS, connect=WEB_PAGE_CONNECT_TIMEOUT_SECONDS)
    headers = {"User-Agent": USER_AGENT, "Accept": _ACCEPT}
    # Wall-clock budget across all hops and streaming, the per-I/O httpx timeout alone cannot cap a slow drip.
    deadline = time.monotonic() + WEB_PAGE_TIMEOUT_SECONDS
    # Neither proxy env vars nor netrc may steer this guarded fetch.
    with httpx.Client(
        timeout=timeout, follow_redirects=False, headers=headers, transport=transport, trust_env=False,
    ) as client:
        for _ in range(WEB_PAGE_MAX_REDIRECTS + 1):
            if time.monotonic() > deadline:
                raise LinkError("ai.link.unreachable", 502)
            # Nothing a hop set travels to the next one.
            client.cookies.clear()
            try:
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        target = response.headers.get("location")
                        if not target:
                            raise LinkError("ai.link.unreachable", 502)
                        current = validate_url(urljoin(current, target))
                        continue
                    return _read_body(response, current, deadline)
            except httpx.RemoteProtocolError as e:
                # httpx itself parses the redirect location and wraps a bad URL in this error.
                if isinstance(e.__context__, httpx.InvalidURL):
                    raise LinkError("ai.link.invalid", 400)
                raise LinkError("ai.link.unreachable", 502)
            except (httpx.HTTPError, httpx.InvalidURL):
                raise LinkError("ai.link.unreachable", 502)
    raise LinkError("ai.link.tooManyRedirects", 502)


def _read_body(response: httpx.Response, url: str, deadline: float) -> FetchedPage:
    """Streams the answer, decides the kind on the first bytes, stops at the cap or the deadline."""
    status = response.status_code
    if status in (401, 403):
        raise LinkError("ai.link.loginRequired", 502)
    if status >= 400:
        raise LinkError("ai.link.httpError", 502, status=status)
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    kind: str | None = None
    limit = WEB_PAGE_MAX_HTML_BYTES
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        if kind is None:
            kind = _kind_of(content_type, chunk)
            limit = WEB_PAGE_MAX_PDF_BYTES if kind == "pdf" else WEB_PAGE_MAX_HTML_BYTES
        total += len(chunk)
        if total > limit:
            raise LinkError("ai.link.tooLarge", 413)
        chunks.append(chunk)
        # A slow drip stays under the per-chunk I/O timeout but must not outlast the total budget.
        if time.monotonic() > deadline:
            raise LinkError("ai.link.unreachable", 502)
    if kind is None:
        kind = _kind_of(content_type, b"")
    return FetchedPage(kind=kind, body=b"".join(chunks), final_url=url, content_type=content_type)


def _kind_of(content_type: str, head: bytes) -> str:
    """PDF by type or magic bytes, HTML and plain text by type, nothing else."""
    if content_type == "application/pdf" or head.lstrip().startswith(b"%PDF"):
        return "pdf"
    if content_type in ("text/html", "application/xhtml+xml"):
        return "html"
    if content_type == "text/plain":
        return "text"
    raise LinkError("ai.link.unsupportedType", 415)
