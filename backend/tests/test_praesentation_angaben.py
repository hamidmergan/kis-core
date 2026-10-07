"""Die Angaben neben der fertigen Präsentation: Vorlage, Anweisung, Bildstil und wer schrieb und malte."""

from src.features.praesentation import store
from src.features.praesentation.angaben import angaben
from src.features.praesentation.schemas import PraesentationParams
from src.services import job_statistik


UID = 7
JOB = "d" * 32


def _params() -> PraesentationParams:
    return PraesentationParams(language="en", instructions=" Höchstens acht Folien. ", template_name="THL-Vorlage",
                               style_text="Tusche", source_label="Skript.pdf, Fallstudie.pdf")


def test_einstellungen_und_anbieter():
    a = angaben(_params(), "HPC", "HPC Bild")

    assert a == {"anbieter": "HPC", "bildanbieter": "HPC Bild", "vorlage": "THL-Vorlage", "sprache": "en",
                 "anweisung": "Höchstens acht Folien.", "bildstil": "Tusche", "material": "Skript.pdf, Fallstudie.pdf"}


def test_ohne_namen_steht_die_kennung_der_vorlage():
    assert angaben(PraesentationParams(template_id="eigene-1"))["vorlage"] == "eigene-1"


def test_alter_lauf_liest_seine_einstellungen(lokal):
    store.save_params(UID, JOB, _params())

    a = job_statistik.angaben_lesen({"user_id": UID, "job_uuid": JOB, "tool": "praesentation"})

    assert a["vorlage"] == "THL-Vorlage"
    assert a["anweisung"] == "Höchstens acht Folien."
    assert "anbieter" not in a


def test_gemerkte_anbieter_stehen_neben_den_einstellungen(lokal):
    store.save_params(UID, JOB, _params())
    job_statistik.angaben_merken(UID, JOB, angaben(_params(), "HPC", ""))

    a = job_statistik.angaben_lesen({"user_id": UID, "job_uuid": JOB, "tool": "praesentation"})

    assert a["anbieter"] == "HPC"
    assert "bildanbieter" not in a
    assert a["material"] == "Skript.pdf, Fallstudie.pdf"
