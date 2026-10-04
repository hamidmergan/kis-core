"""Der Abgleich holt nur Geändertes, löscht Verschwundenes und hält die Obergrenze."""
from datetime import datetime

import pytest

from src.features.campus.services import crawler
from src.features.campus.services.fetch import FetchResult
from src.features.campus.services.settings import CampusSettings

SITEMAP = b"""<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://x.test/a/</loc><lastmod>2026-09-01T00:00:00+00:00</lastmod></url>
<url><loc>https://x.test/b/</loc></url>
<url><loc>https://x.test/c/</loc></url>
<url><loc>https://x.test/news/1</loc></url>
<url><loc>javascript:alert(1)</loc></url>
</urlset>"""

HTML = b"<html><body><main><h1>Seite</h1><p>" + b"Ein langer Absatz mit genug Text, damit die Extraktion ihn als Haupttext erkennt. " * 5 + b"</p></main></body></html>"


class _Pages:
    def __init__(self, existing):
        self.by_url = {p["url"]: p for p in existing}
        self.deleted = []
        self.fetched = []
        self.status = []
        self._next = 100

    def get_page_by_url(self, url):
        return self.by_url.get(url)

    def upsert_page(self, kind, url, title=None, filename=None, file_path=None):
        self._next += 1
        self.by_url[url] = {"id": self._next, "url": url, "etag": None, "last_modified": None, "fetched_at": None, "status": "pending"}
        return self._next

    def set_page_fetch(self, page_id, etag, last_modified, fetched_at):
        self.fetched.append(page_id)

    def set_page_status(self, page_id, status, error_message=None):
        self.status.append((page_id, status, error_message))

    def delete_page(self, page_id):
        self.deleted.append(page_id)
        self.by_url = {u: p for u, p in self.by_url.items() if p["id"] != page_id}

    def list_page_urls(self, kind):
        return {u: p["id"] for u, p in self.by_url.items()}

    KIND_PAGE = "page"


def _fetch_factory(responses):
    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=SITEMAP)
        return responses.get(url, FetchResult("error", error="unknown"))
    return fetch_fn


@pytest.fixture(autouse=True)
def oeffentlich(monkeypatch):
    monkeypatch.setattr("src.services.web_page_fetch._resolve", lambda host: ["93.184.216.34"])


def _einstellungen():
    return CampusSettings(sitemap_url="https://x.test/sitemap.xml", url_exclude="/news/")


def test_unveraendert_gelöscht_und_neu(monkeypatch):
    seiten = _Pages([
        {"id": 1, "url": "https://x.test/a/", "etag": '"a"', "last_modified": None, "fetched_at": datetime(2026, 9, 2), "status": "ready", "content_hash": "v3:x"},
        {"id": 2, "url": "https://x.test/b/", "etag": '"b"', "last_modified": None, "fetched_at": datetime(2026, 9, 2), "status": "ready", "content_hash": "v3:x"},
        {"id": 3, "url": "https://x.test/weg/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready"},
    ])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    eingebettet = []
    monkeypatch.setattr(crawler.indexer, "index_markdown", lambda pid, title, md, embed: eingebettet.append(pid) or 1)
    antworten = {
        "https://x.test/b/": FetchResult("unchanged"),
        "https://x.test/c/": FetchResult("ok", body=HTML, etag='"c"'),
    }
    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=1, fetch_fn=_fetch_factory(antworten))
    # a: the sitemap date lies before the last fetch, so it is not even requested.
    assert stats["skipped"] == 1 and stats["unchanged"] == 1 and stats["indexed"] == 1
    # weg: no longer in the sitemap, so it is removed; news is excluded by pattern.
    assert stats["removed"] == 1 and 3 in seiten.deleted and stats["seen"] == 4
    # The javascript entry counts as failed and never becomes a row.
    assert stats["failed"] == 1 and "javascript:alert(1)" not in seiten.by_url
    assert eingebettet == [seiten.by_url["https://x.test/c/"]["id"]]


def test_404_entfernt_die_seite_und_fehler_markiert(monkeypatch):
    seiten = _Pages([{"id": 1, "url": "https://x.test/a/", "etag": None, "last_modified": None, "fetched_at": None, "status": "pending"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    antworten = {
        "https://x.test/a/": FetchResult("gone"),
        "https://x.test/b/": FetchResult("error", error="http 500"),
        "https://x.test/c/": FetchResult("ok", body=b"<html><body><p>kurz</p></body></html>"),
    }
    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=2, fetch_fn=_fetch_factory(antworten))
    assert 1 in seiten.deleted and stats["removed"] == 1
    # b with its 500, c without text and the javascript entry.
    assert stats["failed"] == 3
    assert ("no text" in [s[2] for s in seiten.status])


def test_obergrenze_laesst_den_rest_stehen(monkeypatch):
    seiten = _Pages([{"id": 9, "url": "https://x.test/alt/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    monkeypatch.setattr(crawler.indexer, "index_markdown", lambda *a, **k: 1)
    antworten = {u: FetchResult("ok", body=HTML) for u in ("https://x.test/a/", "https://x.test/b/", "https://x.test/c/")}
    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), max_pages=2, concurrency=1, fetch_fn=_fetch_factory(antworten))
    assert stats["indexed"] == 2 and stats["seen"] == 4
    # Nothing was removed, the run did not see every page.
    assert seiten.deleted == []


def test_unlesbare_teil_sitemap_loescht_nichts(monkeypatch):
    seiten = _Pages([{"id": 9, "url": "https://x.test/alt/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)

    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://x.test/a.xml</loc></sitemap><sitemap><loc>https://x.test/b.xml</loc></sitemap></sitemapindex>')
        if url == "https://x.test/a.xml":
            return FetchResult("ok", body=SITEMAP)
        if url == "https://x.test/b.xml":
            return FetchResult("error", error="http 500")
        return FetchResult("unchanged")

    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=1, fetch_fn=fetch_fn)
    assert stats["removed"] == 0 and seiten.deleted == []


def test_leere_sitemap_loescht_nichts(monkeypatch):
    seiten = _Pages([{"id": 9, "url": "https://x.test/alt/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    leer = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), fetch_fn=lambda c, u, e=None, l=None: FetchResult("ok", body=leer))
    assert seiten.deleted == [] and stats["removed"] == 0


def test_alte_indexversion_wird_voll_geholt(monkeypatch):
    seiten = _Pages([{"id": 1, "url": "https://x.test/a/", "etag": '"a"', "last_modified": None, "fetched_at": datetime(2026, 9, 2), "status": "ready", "content_hash": "abc"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    monkeypatch.setattr(crawler.indexer, "index_markdown", lambda *a, **k: 1)
    gesehen = {}

    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=SITEMAP)
        gesehen[url] = etag
        return FetchResult("ok", body=HTML)

    crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=1, fetch_fn=fetch_fn)
    # Despite an older lastmod and a stored etag, page a is fetched without validators.
    assert "https://x.test/a/" in gesehen and gesehen["https://x.test/a/"] is None


def test_html_statt_teil_sitemap_loescht_nichts(monkeypatch):
    seiten = _Pages([{"id": 9, "url": "https://x.test/alt/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    monkeypatch.setattr(crawler.indexer, "index_markdown", lambda *a, **k: 1)

    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://x.test/a.xml</loc></sitemap><sitemap><loc>https://x.test/b.xml</loc></sitemap></sitemapindex>')
        if url == "https://x.test/a.xml":
            return FetchResult("ok", body=SITEMAP)
        if url == "https://x.test/b.xml":
            return FetchResult("ok", body=b"<!DOCTYPE html><html><body>Wartung</body></html>")
        return FetchResult("ok", body=HTML)

    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=1, fetch_fn=fetch_fn)
    assert seiten.deleted == [] and stats["removed"] == 0


def test_datum_ohne_uhrzeit_gilt_bis_tagesende():
    assert crawler._parse_lastmod("2026-10-04") == datetime(2026, 10, 4, 23, 59, 59)
    assert crawler._parse_lastmod("2026-10-04T10:00:00+02:00") == datetime(2026, 10, 4, 8, 0, 0)


def test_fehler_einer_seite_stoppt_den_lauf_nicht(monkeypatch):
    seiten = _Pages([])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    aufrufe = []

    def index(pid, title, md, embed):
        aufrufe.append(pid)
        return 1

    monkeypatch.setattr(crawler.indexer, "index_markdown", index)
    kaputt = {"n": 0}

    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=SITEMAP)
        if url == "https://x.test/a/":
            raise RuntimeError("Datenbank weg")
        return FetchResult("ok", body=HTML)

    stats = crawler.run(_einstellungen(), embed=lambda t: [], client=object(), concurrency=1, fetch_fn=fetch_fn)
    assert stats["failed"] >= 1 and stats["indexed"] == 2


def test_mehrere_sitemaps_und_ausgeschlossene_seiten(monkeypatch):
    seiten = _Pages([{"id": 7, "url": "https://x.test/b/", "etag": None, "last_modified": None, "fetched_at": None, "status": "ready", "content_hash": "v3:x"}])
    monkeypatch.setattr(crawler, "page_repo", seiten)
    monkeypatch.setattr(crawler.indexer, "index_markdown", lambda pid, title, md, embed: 1)
    zweite = b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://y.test/z/</loc></url></urlset>'

    def fetch_fn(client, url, etag=None, last_modified=None):
        if url == "https://y.test/sitemap.xml":
            return FetchResult("ok", body=zweite)
        if url == "https://x.test/sitemap.xml":
            return FetchResult("ok", body=SITEMAP)
        return FetchResult("ok", body=HTML)

    einstellungen = CampusSettings(sitemap_url="https://x.test/sitemap.xml\nhttps://y.test/sitemap.xml", url_exclude="/news/")
    stats = crawler.run(einstellungen, embed=lambda t: [], client=object(), concurrency=1, fetch_fn=fetch_fn, excluded_urls={"https://x.test/c/"})
    # a, b, z and the bad link are seen; c is excluded by address, so it never becomes a row.
    assert "https://y.test/z/" in seiten.by_url and "https://x.test/c/" not in seiten.by_url
    assert stats["seen"] == 4
