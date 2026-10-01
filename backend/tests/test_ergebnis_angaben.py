"""What a result was made with stays next to it, beside the admin numbers."""

from src.services.job_statistik import angaben_merken, notiere
from src.storage import load_result_meta


UID = 7
JOB = "c" * 32


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
