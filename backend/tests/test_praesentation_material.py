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
    """Die Rueckfallebene, und sie reicht den Fakten-Weg als erste Stufe durch."""
    gereicht = {}

    async def build_context(quellen, instr, wid, suuids, zahlen, facts=None):
        gereicht["facts"] = facts
        return "TEXT"

    async def _fakten():
        return "AUS FAKTEN"

    monkeypatch.setattr(material.instruction, "build_context", build_context)
    assert await material.kontext([("a", [{"content": "x"}])], "", None, None, _fakten) == "TEXT"
    assert gereicht["facts"] is _fakten


def _pool(*aussagen):
    from src.services.facts import Fact
    return [Fact(fact_id=n, category="These", fact=a, citation=f"Beleg {n}",
                 source_id="doc_01", source_name="a.pdf")
            for n, a in enumerate(aussagen, start=1)]


class TestQuellenFuerDenAuftragsordner:
    """Die Rohquellen, wie sie der Leseaufruf spaeter bekommt."""

    def test_stuecke_werden_zu_einem_text_je_datei(self):
        quellen = [("a.pdf", [{"content": "Erster Teil."}, {"content": "Zweiter Teil."}])]
        assert material.als_quellen(quellen) == [
            {"source_id": "doc_01", "filename": "a.pdf", "content": "Erster Teil.\nZweiter Teil."}]

    def test_die_nummer_haelt_die_reihenfolge_der_person(self):
        quellen = [("b.pdf", [{"content": "B"}]), ("a.pdf", [{"content": "A"}])]
        assert [q["source_id"] for q in material.als_quellen(quellen)] == ["doc_01", "doc_02"]

    def test_eine_leere_datei_kommt_nicht_mit(self):
        quellen = [("leer.pdf", [{"content": "  "}]), ("a.pdf", [{"content": "A"}])]
        assert [q["filename"] for q in material.als_quellen(quellen)] == ["a.pdf"]


class TestAusschnitt:
    """Was eine einzelne Folie aus dem Material bekommt, mit Vorrat und ohne."""

    def test_aus_dem_vorrat_gewinnen_die_passenden_fakten(self):
        pool = _pool("Der Regelkreis regelt die Temperatur.", "Die Kuehlung braucht Wasser.")
        text = material.ausschnitt(pool, "", ["Kuehlung"], 10_000)
        assert "Kuehlung braucht Wasser" in text
        assert "Regelkreis" not in text

    def test_ohne_treffer_im_vorrat_kommt_trotzdem_etwas(self):
        """Lieber unpassendes Material als eine Folie ohne jede Grundlage."""
        pool = _pool("Der Regelkreis regelt.", "Die Kuehlung braucht Wasser.")
        assert material.ausschnitt(pool, "", ["Blumentopf"], 10_000).strip()

    def test_der_vorrat_gewinnt_gegen_den_schnappschuss(self):
        pool = _pool("Die Kuehlung braucht Wasser.")
        text = material.ausschnitt(pool, "Alles ueber den Regelkreis.", ["Kuehlung"], 10_000)
        assert "Kuehlung" in text and "Regelkreis" not in text

    def test_ohne_vorrat_wird_der_schnappschuss_ausgeschnitten(self):
        text = material.ausschnitt([], "Alles ueber den Regelkreis.", ["Regelkreis"], 10_000)
        assert "Regelkreis" in text

    def test_ohne_beides_kommt_nichts(self):
        assert material.ausschnitt([], "", ["Regelkreis"], 10_000) == ""

    def test_die_grenze_wird_eingehalten(self):
        pool = _pool(*[f"Aussage {n} ueber die Kuehlung." for n in range(50)])
        assert len(material.ausschnitt(pool, "", ["Kuehlung"], 200)) <= 200


class TestMaterialFuerEineFolieMitVorrat:
    """Die gezielte Suche bleibt vorn, der Vorrat loest das Zeichenfenster ab."""

    def _params(self, **kw):
        from src.features.praesentation.schemas import PraesentationParams
        return PraesentationParams(**kw)

    async def test_ohne_workspace_kommen_die_fakten_statt_eines_fensters(self, monkeypatch):
        gesucht = []
        monkeypatch.setattr(material.instruction, "search_context", lambda *a: gesucht.append(a))
        pool = _pool("Der Regelkreis regelt.", "Die Kuehlung braucht Wasser.")
        text = await material.fuer_folie(self._params(), pool, "", ["Kuehlung"])
        assert "Kuehlung braucht Wasser" in text and "Regelkreis" not in text
        assert gesucht == [], "ohne Workspace darf keine Suche starten"

    async def test_mit_workspace_gewinnen_die_gefundenen_stellen(self, monkeypatch):
        async def _treffer(workspace_id, source_uuids, frage, budget):
            return "# a.pdf\nDie Stelle zur Kuehlung"

        monkeypatch.setattr(material.instruction, "search_context", _treffer)
        text = await material.fuer_folie(
            self._params(workspace_id=42, source_uuids=["u1"]), _pool("Etwas anderes."),
            "", ["Kuehlung"])
        assert text == "# a.pdf\nDie Stelle zur Kuehlung"

    async def test_kaputte_suche_faellt_auf_den_vorrat_zurueck(self, monkeypatch):
        async def _kaputt(*a):
            raise RuntimeError("Einbettungsdienst weg")

        monkeypatch.setattr(material.instruction, "search_context", _kaputt)
        text = await material.fuer_folie(
            self._params(workspace_id=42, source_uuids=["u1"]),
            _pool("Die Kuehlung braucht Wasser."), "", ["Kuehlung"])
        assert "Kuehlung braucht Wasser" in text
