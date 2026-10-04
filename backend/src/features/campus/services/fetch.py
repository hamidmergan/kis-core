"""Conditional page fetches for the crawl, every hop restricted to public web hosts."""
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from src.limits import CAMPUS_FETCH_TIMEOUT_SECONDS, CAMPUS_PAGE_MAX_BYTES
from src.services.web_page_fetch import LinkError, validate_url

_USER_AGENT = "KIS-Infoassistent/1.0 (+sitemap crawl)"
_MAX_HOPS = 5
_HTML_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "application/xml", "text/xml", "application/json")


@dataclass
class FetchResult:
    status: str  # ok | unchanged | gone | error
    body: bytes = b""
    etag: str | None = None
    last_modified: str | None = None
    content_type: str = ""
    error: str = ""
    headers: dict = field(default_factory=dict)


def make_client(timeout: float = CAMPUS_FETCH_TIMEOUT_SECONDS) -> httpx.Client:
    return httpx.Client(follow_redirects=False, trust_env=False, timeout=timeout, headers={"User-Agent": _USER_AGENT})


def is_web_url(url: str) -> bool:
    """Only plain http(s) links to public hosts, the same rule as for pasted links."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    try:
        validate_url(url)
    except LinkError:
        return False
    return True


def fetch_conditional(
    client: httpx.Client,
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    max_bytes: int = CAMPUS_PAGE_MAX_BYTES,
) -> FetchResult:
    """GET with validators; 304 means unchanged, 404 and 410 mean the page is gone."""
    headers = {"Accept": "text/html, application/xhtml+xml, application/xml;q=0.9, application/json;q=0.9, text/plain;q=0.8"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    current = url
    for _ in range(_MAX_HOPS + 1):
        if not is_web_url(current):
            return FetchResult("error", error="forbidden url")
        try:
            with client.stream("GET", current, headers=headers) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    target = resp.headers.get("location")
                    if not target:
                        return FetchResult("error", error="redirect without location")
                    current = urljoin(current, target)
                    continue
                if resp.status_code == 304:
                    return FetchResult("unchanged", etag=etag, last_modified=last_modified)
                if resp.status_code in (404, 410):
                    return FetchResult("gone")
                if resp.status_code != 200:
                    return FetchResult("error", error=f"http {resp.status_code}")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if ctype and not any(ctype.startswith(t) for t in _HTML_TYPES):
                    return FetchResult("error", error=f"unsupported type {ctype}", content_type=ctype)
                body = b""
                for part in resp.iter_bytes():
                    body += part
                    if len(body) > max_bytes:
                        return FetchResult("error", error="page too large", content_type=ctype)
                return FetchResult(
                    "ok", body=body, etag=resp.headers.get("etag"), last_modified=resp.headers.get("last-modified"),
                    content_type=ctype, headers=dict(resp.headers),
                )
        except httpx.HTTPError as e:
            return FetchResult("error", error=f"{type(e).__name__}: {e}"[:200])
    return FetchResult("error", error="too many redirects")
