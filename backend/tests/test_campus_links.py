"""Der Linkgang findet Seiten ohne Sitemap, achtet auf noindex und canonical und bleibt unter der Startadresse."""
import pytest

from src.features.campus.services import crawler, links
from src.features.campus.services.fetch import FetchResult
from src.features.campus.services.settings import CampusSettings


def _seite(links_html: str = "", head: str = "") -> FetchResult:
    return FetchResult("ok", body=f"<html><head>{head}</head><body>{links_html}</body></html>".encode())


SEITEN = {
    "https://x.test/isy/": _seite('<a href="/isy/projekte/">P</a><a href="https://x.test/isy/team/">T</a><a href="/anderswo/">A</a><a href="/isy/flyer.pdf">F</a><a href="/isy/?type=1">Q</a><a href="#oben">O</a>'),
    "https://x.test/isy/projekte/": _seite('<a href="dlc/">D</a><a href="/isy/projekte/p/2/">2</a><a href="/isy/weg/">W</a>'),
    "https://x.test/isy/projekte/dlc/": _seite('<a href="/isy/projekte/dlc/dlc/">doppelt</a>'),
    "https://x.test/isy/projekte/dlc/dlc/": _seite(head='<meta name="robots" content="noindex,nofollow">'),
    "https://x.test/isy/projekte/p/2/": _seite('<a href="/isy/news/1/">N</a>', head='<link rel="canonical" href="https://x.test/isy/projekte/">'),
    "https://x.test/isy/news/1/": _seite(),
    "https://x.test/isy/team/": FetchResult("error", error="http 500"),
    "https://x.test/isy/weg/": FetchResult("gone"),
}


@pytest.fixture(autouse=True)
def oeffentlich(monkeypatch):
    monkeypatch.setattr("src.services.web_page_fetch._resolve", lambda host: ["93.184.216.34"])


def _fetch(client, url, etag=None, last_modified=None):
    assert url in SEITEN, url
    return SEITEN[url]


def test_findet_seiten_unter_der_startadresse():
    gefunden, ungelesen, vollstaendig = links.walk(None, "https://x.test/isy/", [], [], _fetch)
    assert sorted(e.url for e in gefunden) == [
        "https://x.test/isy/", "https://x.test/isy/news/1/", "https://x.test/isy/projekte/", "https://x.test/isy/projekte/dlc/",
    ]
    assert ungelesen == {"https://x.test/isy/team/"}
    assert vollstaendig


def test_muster_gelten_auch_im_linkgang():
    gefunden, _, _ = links.walk(None, "https://x.test/isy/", [], ["/news/"], _fetch)
    assert "https://x.test/isy/news/1/" not in {e.url for e in gefunden}


def test_obergrenze_macht_den_gang_unvollstaendig():
    gefunden, _, vollstaendig = links.walk(None, "https://x.test/isy/", [], [], _fetch, max_pages=2)
    assert len(gefunden) <= 2
    assert not vollstaendig


def test_abgleich_nimmt_gefundene_seiten_auf_und_loescht_ungelesene_nicht(monkeypatch):
    bekannt = {"https://x.test/isy/team/": 7, "https://x.test/isy/alt/": 8}
    geloescht, bearbeitet = [], []

    class _Repo:
        KIND_PAGE = "page"

        def list_page_urls(self, kind):
            return dict(bekannt)

        def delete_page(self, page_id):
            geloescht.append(page_id)
            bekannt.pop(next(u for u, i in bekannt.items() if i == page_id))

    monkeypatch.setattr(crawler, "page_repo", _Repo())
    monkeypatch.setattr(crawler, "_process", lambda client, e, *a: bearbeitet.append(e.url))
    stats = crawler.run(CampusSettings(start_urls="https://x.test/isy/"), embed=None, client=object(), fetch_fn=_fetch)
    assert geloescht == [8]
    assert "https://x.test/isy/projekte/dlc/" in bearbeitet
    assert "https://x.test/isy/team/" not in bearbeitet
    assert stats["seen"] == 4
