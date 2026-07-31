"""Schluessel-Aufbau im Bucket: abgeleitete Namen, Loeschen per Praefix, Folienreihenfolge.

Geprueft wird das, was leise falsch sein kann. Ein Loeschen, das die
Zusatzdateien einer Quelle stehen laesst, faellt im Betrieb nie auf, der
Volltext eines Videos ueberlebt dann aber seine Quelle. Und ein Auflisten, das
nach Text statt nach Zahl sortiert, vertauscht die Reihenfolge erst jenseits
von 1000 Folien.
"""

import pytest

from src import storage


class _FakeS3:
    """Minimaler S3-Ersatz: kennt eine Schluesselliste und blaettert in 1000er-Schritten.

    Das Blaettern ist der Punkt: eine echte Antwort liefert hoechstens 1000
    Schluessel, und genau daran sind die beiden Folien-Funktionen frueher
    stillschweigend abgeschnitten worden.
    """

    def __init__(self, keys: list[str]):
        self.keys = keys

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        keys = self.keys

        class _Paginator:
            def paginate(self, Bucket=None, Prefix="", **kw):
                treffer = [k for k in keys if k.startswith(Prefix)]
                for i in range(0, len(treffer), 1000):
                    yield {"Contents": [{"Key": k} for k in treffer[i:i + 1000]]}

        return _Paginator()

    def get_object(self, Bucket=None, Key=None, **kw):
        class _Body:
            def read(self_inner):
                return Key.encode()
        return {"Body": _Body()}


@pytest.fixture
def s3(monkeypatch):
    """Speicher mit S3: haengt fuer die uebergebenen Schluessel den Fake-Client ein."""
    def _einrichten(keys: list[str]) -> None:
        client = _FakeS3(keys)
        monkeypatch.setattr(storage, "USE_S3", True)
        monkeypatch.setattr(storage, "_s3", lambda: client)
    return _einrichten


# ─── Abgeleitete Schluessel ────────────────────────────────────────────────

def test_transkript_und_untertitel_haengen_am_namen_der_quelle():
    """Die Helfer nehmen den Quellpfad selbst, damit keine Aufrufstelle mehr
    die Endung von Hand abschneiden muss."""
    quelle = "users/1/aia/workspaces/w1/sources/xyz.mp4"
    basis = "users/1/aia/workspaces/w1/sources/xyz"

    assert storage.aia_source_base(quelle) == basis
    assert storage.aia_transcript_key(quelle) == basis + "_transcript.txt"
    assert storage.aia_vtt_key(quelle, "de") == basis + "_transcript.de.vtt"
    assert storage.aia_transcript_prefix(quelle) == basis + "_transcript."


def test_ein_schon_abgeschnittener_pfad_geht_auch_durch():
    """Wichtig, weil manche Aufrufer eine Basis weiterreichen statt der Quelle."""
    basis = "users/1/sources/xyz"

    assert storage.aia_source_base(basis) == basis
    assert storage.aia_vtt_key(basis, "de") == basis + "_transcript.de.vtt"


def test_ein_punkt_im_ordnernamen_kuerzt_den_pfad_nicht():
    assert storage.aia_source_base("/srv/my.data/sources/xyz") == "/srv/my.data/sources/xyz"


# ─── Quelldateien ablegen ──────────────────────────────────────────────────

def test_quelldatei_landet_unter_dem_workspace_schluessel(lokal, tmp_path):
    hochgeladen = tmp_path / "upload.bin"
    hochgeladen.write_bytes(b"inhalt")

    schluessel = storage.save_aia_source_from_path(42, "w1", "s1", ".pdf", str(hochgeladen))

    ziel = lokal / "users/42/aia/workspaces/w1/sources/s1.pdf"
    assert ziel.read_bytes() == b"inhalt"
    assert schluessel == str(ziel)


def test_bytes_landen_unter_dem_uebergebenen_schluessel(lokal):
    """Gegenstueck zu ``get_file``. Ohne das muessten Aufrufer selbst zu boto3
    greifen, und die Kenntnis vom Bucket laege wieder an mehreren Orten."""
    schluessel = str(lokal / "users/1/aia/workspaces/w1/sources/s1_transcript.txt")

    storage.put_bytes(schluessel, b"volltext")

    assert (lokal / "users/1/aia/workspaces/w1/sources/s1_transcript.txt").read_bytes() == b"volltext"


def test_transkript_wird_ueber_den_speicher_geschrieben(lokal):
    """Die Ingestion darf nicht an storage.py vorbei direkt auf S3 schreiben."""
    from src.features.ai_assistant.tasks import ingestion

    ordner = lokal / "users/1/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    schluessel = str(ordner / "s1_transcript.txt")

    ingestion._save_transcript_artifact(schluessel, "[00:00 - 00:05] hallo")

    assert (ordner / "s1_transcript.txt").read_text(encoding="utf-8") == "[00:00 - 00:05] hallo"


# ─── Loeschen per Praefix ──────────────────────────────────────────────────

def test_praefix_loeschen_nimmt_die_geschwisterdateien_mit(lokal):
    """Der eigentliche Fehler: Transkript und Untertitel blieben liegen."""
    ordner = lokal / "users/1/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    (ordner / "xyz.mp4").write_bytes(b"video")
    (ordner / "xyz_transcript.txt").write_bytes(b"text")
    (ordner / "xyz_transcript.de.vtt").write_bytes(b"de")
    (ordner / "xyz_transcript.en.vtt").write_bytes(b"en")
    (ordner / "abc.mp4").write_bytes(b"fremde quelle")

    entfernt = storage.delete_prefix("users/1/aia/workspaces/w1/sources/xyz")

    assert entfernt == 4
    assert not (ordner / "xyz.mp4").exists()
    assert not (ordner / "xyz_transcript.txt").exists()
    assert not (ordner / "xyz_transcript.de.vtt").exists()
    assert not (ordner / "xyz_transcript.en.vtt").exists()
    assert (ordner / "abc.mp4").exists()


def test_praefix_loeschen_versteht_auch_einen_absoluten_pfad(lokal):
    """Ohne S3 steht in ``file_path`` ein absoluter Pfad, mit S3 ein relativer
    Schluessel. Beide Formen erreichen dieselben Dateien."""
    ordner = lokal / "users/1/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    (ordner / "xyz.mp4").write_bytes(b"video")
    (ordner / "xyz_transcript.txt").write_bytes(b"text")

    entfernt = storage.delete_prefix(str(ordner / "xyz"))

    assert entfernt == 2
    assert list(ordner.iterdir()) == []


def test_praefix_loeschen_raeumt_weiterhin_ganze_ordner(lokal):
    """Bestandsverhalten, das die Jobs brauchen. Darf nicht kaputtgehen."""
    ordner = lokal / "users/1/jobs/j1"
    (ordner / "audio").mkdir(parents=True)
    (ordner / "output.mp4").write_bytes(b"v")
    (ordner / "audio/slide_000.mp3").write_bytes(b"a")

    entfernt = storage.delete_prefix("users/1/jobs/j1")

    assert entfernt == 2
    assert not ordner.exists()


def test_praefix_loeschen_meldet_null_wenn_nichts_da_ist(lokal):
    assert storage.delete_prefix("users/1/jobs/gibtesnicht") == 0


# ─── Auflisten ─────────────────────────────────────────────────────────────

def test_auflisten_findet_geschwisterdateien(lokal):
    ordner = lokal / "users/1/aia/workspaces/w1/sources"
    ordner.mkdir(parents=True)
    (ordner / "xyz.mp4").write_bytes(b"v")
    (ordner / "xyz_transcript.txt").write_bytes(b"t")
    (ordner / "abc.mp4").write_bytes(b"fremd")

    treffer = storage.list_keys(str(ordner / "xyz"))

    assert sorted(treffer) == [str(ordner / "xyz.mp4"), str(ordner / "xyz_transcript.txt")]


def test_auflisten_steigt_in_einen_ordner_hinab(lokal):
    """Ohne das findet eine Bestandsaufnahme ueber ``users/`` lokal nichts.

    Mit S3 liefert ein Praefix immer alles darunter, egal wie tief. Lokal muss
    dieselbe Frage dieselbe Antwort geben, sonst haengt das Ergebnis daran, wo
    die Dateien gerade liegen."""
    (lokal / "users/1/jobs/j1/audio").mkdir(parents=True)
    (lokal / "users/1/jobs/j1/output.mp4").write_bytes(b"v")
    (lokal / "users/1/jobs/j1/audio/slide_000.mp3").write_bytes(b"a")
    (lokal / "users/2/jobs/j2").mkdir(parents=True)
    (lokal / "users/2/jobs/j2/output.mp3").write_bytes(b"b")

    treffer = storage.list_keys("users/")

    assert sorted(treffer) == [
        str(lokal / "users/1/jobs/j1/audio/slide_000.mp3"),
        str(lokal / "users/1/jobs/j1/output.mp4"),
        str(lokal / "users/2/jobs/j2/output.mp3"),
    ]


def test_auflisten_meldet_nichts_wenn_es_nichts_gibt(lokal):
    assert storage.list_keys("users/") == []


# ─── Folienreihenfolge ─────────────────────────────────────────────────────

def test_folien_bleiben_jenseits_von_1000_in_der_richtigen_reihenfolge(lokal):
    """Nach Text sortiert steht ``slide_1000`` vor ``slide_999``."""
    ordner = lokal / "users/1/jobs/j1/audio"
    ordner.mkdir(parents=True)
    for name in ("slide_009.mp3", "slide_010.mp3", "slide_999.mp3", "slide_1000.mp3"):
        (ordner / name).write_bytes(b"x")

    ergebnis = storage.get_all_audio_slides(1, "j1")

    assert [name for name, _ in ergebnis] == [
        "slide_009.mp3", "slide_010.mp3", "slide_999.mp3", "slide_1000.mp3",
    ]


def test_folien_zaehlen_blaettert_ueber_die_1000er_grenze(s3):
    """Ein einzelnes ``list_objects_v2`` liefert hoechstens 1000 Schluessel."""
    s3([f"users/1/jobs/j1/audio/slide_{i:04d}.mp3" for i in range(1200)])

    assert storage.get_audio_slide_count(1, "j1") == 1200


def test_folien_holen_blaettert_ebenfalls_und_sortiert_nach_zahl(s3):
    s3([f"users/1/jobs/j1/audio/slide_{i:03d}.mp3" for i in range(1200)])

    ergebnis = storage.get_all_audio_slides(1, "j1")

    assert len(ergebnis) == 1200
    assert ergebnis[0][0] == "slide_000.mp3"
    assert ergebnis[-1][0] == "slide_1199.mp3"
