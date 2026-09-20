# backend/tests/test_praesentation_material.py
"""The material: limits on upload, and the path to text within budget."""

import pytest
from fastapi import HTTPException, UploadFile
from io import BytesIO

from src.features.praesentation import material


def _upload(name: str, inhalt: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(inhalt))


@pytest.fixture
def ohne_pruefung(monkeypatch):
    monkeypatch.setattr(material, "validate_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(material, "pages_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(material, "max_upload_bytes", lambda: 10_000_000)


async def test_textdatei_wird_zu_quelle(ohne_pruefung):
    quellen, label = await material.aus_dateien([_upload("kapitel.txt", "Regelkreis.".encode())], "de")
    assert label == "kapitel" and quellen[0][0] == "kapitel" and "Regelkreis" in quellen[0][1][0]["content"]


async def test_zu_viele_dateien(ohne_pruefung):
    with pytest.raises(HTTPException) as e:
        await material.aus_dateien([_upload(f"{i}.txt", b"x") for i in range(11)], "de")
    assert e.value.status_code == 422


async def test_falsches_format(ohne_pruefung):
    with pytest.raises(HTTPException) as e:
        await material.aus_dateien([_upload("bild.png", b"x")], "de")
    assert e.value.status_code == 400


async def test_leere_datei(ohne_pruefung):
    with pytest.raises(HTTPException) as e:
        await material.aus_dateien([_upload("leer.txt", b"")], "de")
    assert e.value.status_code == 400


async def test_kontext_nimmt_den_podcast_weg(monkeypatch):
    async def build_context(quellen, instr, wid, suuids, zahlen):
        return "TEXT"

    monkeypatch.setattr(material.instruction, "build_context", build_context)
    assert await material.kontext([("a", [{"content": "x"}])], "", None, None) == "TEXT"


class TestMaterialFuerEineFolie:
    """A slide added later gets its own material, searched when the workspace allows it."""

    def _params(self, **kw):
        from src.features.praesentation.schemas import PraesentationParams
        return PraesentationParams(**kw)

    async def test_ohne_workspace_kommt_der_ausschnitt_aus_dem_schnappschuss(self, monkeypatch):
        gesucht = []
        monkeypatch.setattr(material.instruction, "search_context", lambda *a: gesucht.append(a))
        text = await material.fuer_folie(self._params(), "Alles über den Regelkreis.", ["Regelkreis", ""])
        assert "Regelkreis" in text
        assert gesucht == [], "ohne Workspace darf keine Suche starten"

    async def test_mit_workspace_gewinnen_die_gefundenen_stellen(self, monkeypatch):
        gefragt = []

        async def _treffer(workspace_id, source_uuids, frage, budget):
            gefragt.append((workspace_id, source_uuids, frage, budget))
            return "# a.pdf\nDie Stelle zur Kühlung"

        monkeypatch.setattr(material.instruction, "search_context", _treffer)
        text = await material.fuer_folie(
            self._params(workspace_id=42, source_uuids=["u1"]), "Nur über den Regelkreis.", ["Kühlung", "kurz halten"])
        assert text == "# a.pdf\nDie Stelle zur Kühlung"
        assert gefragt[0][0] == 42 and gefragt[0][1] == ["u1"]
        assert "Kühlung" in gefragt[0][2] and "kurz halten" in gefragt[0][2]

    async def test_ohne_treffer_faellt_sie_auf_den_ausschnitt_zurueck(self, monkeypatch):
        async def _nichts(*a):
            return ""

        monkeypatch.setattr(material.instruction, "search_context", _nichts)
        text = await material.fuer_folie(
            self._params(workspace_id=42, source_uuids=["u1"]), "Alles über den Regelkreis.", ["Kühlung", ""])
        assert "Regelkreis" in text

    async def test_kaputte_suche_kostet_die_folie_nicht(self, monkeypatch):
        async def _kaputt(*a):
            raise RuntimeError("Einbettungsdienst weg")

        monkeypatch.setattr(material.instruction, "search_context", _kaputt)
        text = await material.fuer_folie(
            self._params(workspace_id=42, source_uuids=["u1"]), "Alles über den Regelkreis.", ["Kühlung", ""])
        assert "Regelkreis" in text
