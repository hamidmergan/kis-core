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


@pytest.fixture
def ablage(monkeypatch):
    a = FakeAblage()
    monkeypatch.setattr(store, "save_job_file", a.save_job_file)
    monkeypatch.setattr(store, "get_job_file", a.get_job_file)
    monkeypatch.setattr(store, "job_file_exists", a.job_file_exists)
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
