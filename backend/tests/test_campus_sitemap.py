"""Sitemap-Index und Urlset werden gelesen, Muster entscheiden über die Aufnahme."""
from src.features.campus.services import sitemap

INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.test/sitemaps/pages/sitemap.xml</loc><lastmod>2026-10-03T12:18:17+02:00</lastmod></sitemap>
  <sitemap><loc>https://x.test/sitemaps/news/sitemap.xml</loc></sitemap>
</sitemapindex>"""

URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.test/studium/start/</loc><lastmod>2026-09-01</lastmod></url>
  <url><loc>https://x.test/hochschule/</loc></url>
  <url><loc> </loc></url>
</urlset>"""


def test_index_liefert_kinder_und_keine_seiten():
    kinder, seiten = sitemap.parse(INDEX)
    assert kinder == ["https://x.test/sitemaps/pages/sitemap.xml", "https://x.test/sitemaps/news/sitemap.xml"]
    assert seiten == []


def test_urlset_liefert_seiten_mit_aenderungsdatum():
    kinder, seiten = sitemap.parse(URLSET)
    assert kinder == []
    assert [(s.url, s.lastmod) for s in seiten] == [
        ("https://x.test/studium/start/", "2026-09-01"),
        ("https://x.test/hochschule/", None),
    ]


def test_kaputtes_xml_ergibt_leer():
    assert sitemap.parse(b"<urlset><url><loc>x") is None
    assert sitemap.parse(b"<html><body>Wartung</body></html>") is None


def test_xml_mit_entitaeten_wird_abgewiesen():
    boese = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><urlset><url><loc>https://x.test/&a;</loc></url></urlset>'
    assert sitemap.parse(boese) is None


def test_muster_pruefen():
    include = sitemap.parse_patterns("/studium/\n\n  /international/ \n")
    exclude = sitemap.parse_patterns("/news/")
    assert include == ["/studium/", "/international/"]
    assert sitemap.allowed("https://x.test/studium/a/", include, exclude)
    assert sitemap.allowed("https://x.test/International/b/", include, exclude)
    assert not sitemap.allowed("https://x.test/hochschule/", include, exclude)
    assert not sitemap.allowed("https://x.test/studium/news/1", include, exclude)
    assert sitemap.allowed("https://x.test/irgendwas/", [], [])
