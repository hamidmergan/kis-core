"""What a result was made with stays next to it, beside the admin numbers."""

import pytest

from src.services import provider_transport
from src.services.job_statistik import angaben_merken, notiere
from src.storage import load_result_meta


UID = 7
JOB = "c" * 32


@pytest.fixture(autouse=True)
def _keine_aufzeichnung(monkeypatch):
    """Each test starts without a recording job and leaves none behind."""
    monkeypatch.setattr(provider_transport, "_answered", None)


def test_angaben_landen_in_der_meta(lokal):
    angaben_merken(UID, JOB, {"anbieter": "THL myLab", "ziel": "EN-US", "glossar": False})

    assert load_result_meta(UID, JOB)["angaben"] == {"anbieter": "THL myLab", "ziel": "EN-US", "glossar": False}


def test_leere_angaben_fallen_weg(lokal):
    angaben_merken(UID, JOB, {"anbieter": "", "stimme": None, "format": "srt"})

    assert load_result_meta(UID, JOB)["angaben"] == {"format": "srt"}


def test_zahlen_bleiben_erhalten(lokal):
    notiere(UID, JOB, "vertonung", {"folien": 3})
    angaben_merken(UID, JOB, {"anbieter": "HPC"})

    meta = load_result_meta(UID, JOB)
    assert meta["stats"]["vertonung"] == {"folien": 3}
    assert meta["angaben"] == {"anbieter": "HPC"}


def _tuer():
    from src.services.provider_transport import Target, _Door

    hpc = Target(provider_id=1, name="HPC", root="http://hpc", api_key="k", model="m")
    mylab = Target(provider_id=2, name="THL myLab", root="http://mylab", api_key="k", model="m")
    return _Door(hpc, mylab, "llm"), hpc, mylab


def test_der_rueckfall_steht_als_anbieter_da():
    from src.services import provider_transport
    from src.services.job_statistik import wer_antwortete

    tuer, _, mylab = _tuer()
    provider_transport.record_answering()
    tuer.served(mylab)

    assert wer_antwortete("chat") == "THL myLab"


def test_wechsel_mitten_im_auftrag_nennt_beide():
    from src.services import provider_transport
    from src.services.job_statistik import wer_antwortete

    tuer, hpc, mylab = _tuer()
    provider_transport.record_answering()
    tuer.served(hpc)
    tuer.served(mylab)
    tuer.served(hpc)

    assert wer_antwortete("chat") == "HPC, THL myLab"


def test_ohne_aufruf_durch_die_tuer_gilt_der_gewaehlte(monkeypatch):
    from src.services import job_statistik, provider_transport

    provider_transport.record_answering()
    monkeypatch.setattr(job_statistik, "route_kennung", lambda feature, pid=None: {"anbieter": "DeepL"})

    assert job_statistik.wer_antwortete("doc_translate", 5) == "DeepL"


def test_ein_neuer_auftrag_beginnt_leer():
    from src.services import provider_transport

    tuer, _, mylab = _tuer()
    provider_transport.record_answering()
    tuer.served(mylab)
    provider_transport.record_answering()

    assert provider_transport.answered() == []
