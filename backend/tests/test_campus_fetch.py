"""Bedingte Abrufe: 304 heißt unverändert, 404 heißt weg, Umleitungen werden geprüft."""
import httpx
import pytest

from src.features.campus.services import fetch


@pytest.fixture(autouse=True)
def oeffentlich(monkeypatch):
    monkeypatch.setattr("src.services.web_page_fetch._resolve", lambda host: ["93.184.216.34"])


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def test_unveraendert_bei_304():
    gesehen = {}

    def handler(req):
        gesehen["inm"] = req.headers.get("if-none-match")
        return httpx.Response(304)

    r = fetch.fetch_conditional(_client(handler), "https://x.test/a/", etag='"abc"', last_modified="Mon, 01 Sep 2026 00:00:00 GMT")
    assert r.status == "unchanged" and r.etag == '"abc"'
    assert gesehen["inm"] == '"abc"'


def test_weg_bei_404_und_410():
    for code in (404, 410):
        r = fetch.fetch_conditional(_client(lambda req, c=code: httpx.Response(c)), "https://x.test/a/")
        assert r.status == "gone"


def test_ok_liefert_koerper_und_validatoren():
    def handler(req):
        return httpx.Response(200, headers={"etag": '"neu"', "content-type": "text/html; charset=utf-8"}, content=b"<html>hi</html>")

    r = fetch.fetch_conditional(_client(handler), "https://x.test/a/")
    assert r.status == "ok" and r.body == b"<html>hi</html>" and r.etag == '"neu"' and r.content_type == "text/html"


def test_umleitung_wird_gefolgt_aber_nicht_ins_private_netz(monkeypatch):
    def handler(req):
        if req.url.path == "/alt":
            return httpx.Response(301, headers={"location": "/neu"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<p>neu</p>")

    assert fetch.fetch_conditional(_client(handler), "https://x.test/alt").body == b"<p>neu</p>"

    def privat(req):
        return httpx.Response(301, headers={"location": "http://localhost/geheim"})

    r = fetch.fetch_conditional(_client(privat), "https://x.test/alt")
    assert r.status == "error" and "forbidden" in r.error


def test_zu_grosse_seite_und_fremder_typ():
    gross = fetch.fetch_conditional(_client(lambda req: httpx.Response(200, headers={"content-type": "text/html"}, content=b"x" * 50)), "https://x.test/a/", max_bytes=10)
    assert gross.status == "error" and "large" in gross.error
    pdf = fetch.fetch_conditional(_client(lambda req: httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")), "https://x.test/a.pdf")
    assert pdf.status == "error" and "unsupported" in pdf.error
