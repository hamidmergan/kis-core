"""The job folder of a presentation: the user's version wins, images attach to the slide."""

import pytest

from src.features.praesentation import store
from src.features.praesentation.schemas import Body, Outline, OutlineRow, PraesentationParams, Slide
from src.features.praesentation.vorlage import Analyse


class FakeAblage:
    def __init__(self):
        self.dateien = {}

    def save_job_file(self, user_id, job_uuid, filename, data):
        self.dateien[(user_id, job_uuid, filename)] = data
        return f"users/{user_id}/jobs/{job_uuid}/{filename}"

    def get_job_file(self, user_id, job_uuid, filename):
        try:
            return self.dateien[(user_id, job_uuid, filename)]
        except KeyError as e:
            raise FileNotFoundError(filename) from e

    def job_file_exists(self, user_id, job_uuid, filename):
        return (user_id, job_uuid, filename) in self.dateien

    def delete_job_file(self, user_id, job_uuid, filename):
        self.dateien.pop((user_id, job_uuid, filename), None)


@pytest.fixture
def ablage(monkeypatch):
    a = FakeAblage()
    monkeypatch.setattr(store, "save_job_file", a.save_job_file)
    monkeypatch.setattr(store, "get_job_file", a.get_job_file)
    monkeypatch.setattr(store, "job_file_exists", a.job_file_exists)
    monkeypatch.setattr(store, "delete_job_file", a.delete_job_file)
    return a


JOB = "c" * 32


def test_nutzerfassung_der_gliederung_gewinnt(ablage):
    store.save_outline(7, JOB, Outline(title="KI", rows=[OutlineRow(id="s1", role="deckblatt", title="A")]))
    assert store.load_outline(7, JOB).rows[0].title == "A"
    store.save_user_outline(7, JOB, Outline(title="KI", rows=[OutlineRow(id="s1", role="deckblatt", title="B")]))
    assert store.load_outline(7, JOB).rows[0].title == "B"


def test_ohne_gliederung_kommt_none(ablage):
    assert store.load_outline(7, JOB) is None
    assert store.load_slides(7, JOB) == []


def test_folien_rundreise(ablage):
    store.save_slides(7, JOB, [Slide(id="s2", role="text", body=Body(items=["x"]))])
    assert store.load_slides(7, JOB)[0].body.items == ["x"]


def test_bilder_und_vorschau_haengen_an_der_folie(ablage):
    store.save_image(7, JOB, "s2", 0, b"png")
    store.save_image(7, JOB, "s2", "body", b"png2")
    assert store.has_image(7, JOB, "s2", 0) and store.get_image(7, JOB, "s2", "body") == b"png2"
    assert not store.has_image(7, JOB, "s3", 0)
    store.save_preview(7, JOB, "s2", b"prev")
    assert store.get_preview(7, JOB, "s2") == b"prev"
    assert store.image_name("s2", 1) == "images/s2_1.png"


def test_params_und_vorlage(ablage):
    store.save_params(7, JOB, PraesentationParams(language="en"))
    assert store.load_params(7, JOB).language == "en"
    store.save_template(7, JOB, b"pptx")
    assert store.load_template(7, JOB) == b"pptx"
    store.save_template_meta(7, JOB, Analyse(breite=1, hoehe=1, typeface="Arial"))
    assert store.load_template_meta(7, JOB).typeface == "Arial"


def test_neue_id_zaehlt_hinter_der_hoechsten():
    assert store.neue_id({"s1", "s7", "s3"}) == "s8"
    assert store.neue_id(set()) == "s1"


class TestMaterialUndVorrat:
    """Die Rohquellen tragen nur ueber eine abgebrochene Etappe, der Vorrat traegt den Lauf."""

    def _quellen(self):
        return [{"source_id": "doc_01", "filename": "a.pdf", "content": "Text A"}]

    def test_rohquellen_kommen_hin_und_zurueck(self, ablage):
        store.save_material(7, JOB, self._quellen(), 42, ["u1"])
        material = store.load_material(7, JOB)
        assert material["sources"] == self._quellen()
        assert material["workspace_id"] == 42 and material["source_uuids"] == ["u1"]

    def test_ohne_material_kommt_ein_leeres_ergebnis(self, ablage):
        assert store.load_material(7, JOB) == {}

    def test_der_vorrat_kommt_hin_und_zurueck(self, ablage):
        from src.services.facts import Fact

        pool = [Fact(fact_id=1, category="Zahl", fact="40 Grad.", citation="Beleg",
                     source_id="doc_01", source_name="a.pdf", reference="Kapitel 3")]
        store.save_pool(7, JOB, pool)
        assert store.load_pool(7, JOB) == pool

    def test_ohne_vorrat_kommt_eine_leere_liste(self, ablage):
        assert store.load_pool(7, JOB) == []

    def test_aufraeumen_loescht_rohquellen_und_gelesene_fakten(self, ablage):
        """Beides liegt sonst als zweite Kopie des Uploads im Speicher, solange der Auftrag lebt."""
        from src.services.facts import FACTS_FILE

        store.save_material(7, JOB, self._quellen(), None, [])
        ablage.dateien[(7, JOB, FACTS_FILE)] = b"{}"
        store.save_pool(7, JOB, [])
        store.drop_material(7, JOB)
        assert store.load_material(7, JOB) == {}
        assert not ablage.job_file_exists(7, JOB, FACTS_FILE)
        assert ablage.job_file_exists(7, JOB, store.POOL_FILE)

    def test_aufraeumen_ohne_dateien_stuerzt_nicht(self, ablage):
        store.drop_material(7, JOB)
