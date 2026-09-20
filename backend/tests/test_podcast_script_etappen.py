"""Das Skript arbeitet jetzt in Etappen: erst jede Quelle lesen, dann schreiben."""

import json
from contextlib import contextmanager

import pytest

from src.features.podcast.schemas import Person, PodcastParams
from src.services.facts import RunInterrupted
from src.tasks._stage import StageLost
from src.tasks.podcast_tasks import _script
from src.tasks.podcast_tasks._shared import JobCancelled

UID = 7
JOB = "s" * 32


class _Store:
    """Auftragsordner im Speicher, mit genau den Dateien die das Skript braucht."""

    def __init__(self, material: dict | None = None, params=None, source: str = "") -> None:
        self.material = material if material is not None else {"sources": [
            {"source_id": "doc_01", "filename": "a.pdf", "content": "Der Regelkreis."}]}
        self.params = params
        self.source = source
        self.script = None
        self.user_script = None
        self.aufgeraeumt = False

    def load_material(self, uid, job):
        return self.material

    def load_params(self, uid, job):
        return self.params

    def save_params(self, uid, job, params):
        self.params = params

    def load_source(self, uid, job):
        return self.source

    def save_source(self, uid, job, text):
        self.source = text

    def drop_material(self, uid, job):
        self.aufgeraeumt = True

    def save_script(self, uid, job, lines):
        self.script = lines

    def save_user_script(self, uid, job, lines):
        self.user_script = lines

    def next_ids(self, lines):
        return lines


class _Db:
    def __init__(self):
        self.status = []

    def update_job_status(self, job_uuid, status, progress=None, error_message=None):
        self.status.append((status, (progress or {}).get("step")))

    def reset_job_to_awaiting(self, job_uuid):
        self.status.append(("awaiting_user", None))

    def schritte(self):
        return [schritt for _status, schritt in self.status]


class _Task:
    def __init__(self):
        self.aufrufe = []

    def apply_async(self, args=None, **kwargs):
        self.aufrufe.append(args)
        return type("R", (), {"id": "task-2"})()


def _params(**kw):
    return PodcastParams(persons=[Person(name="Lena", role="host", voice_id="a"),
                                  Person(name="Jonas", role="expert", voice_id="b")], **kw)


_ANTWORT = json.dumps({"lines": [{"speaker": 0, "text": "Hallo zusammen."},
                                 {"speaker": 1, "text": "Guten Tag."}]})


@pytest.fixture
def umgebung(monkeypatch):
    db = _Db()
    task = _Task()
    gemeldet: list[tuple] = []
    monkeypatch.setattr(_script, "db", db)
    monkeypatch.setattr(_script, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(_script, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_script, "continue_stage",
                        lambda selbst, args, job: task.apply_async(args=args))
    monkeypatch.setattr(_script, "notiere",
                        lambda uid, job, phase, werte: gemeldet.append((phase, dict(werte))))

    @contextmanager
    def _stumm(*args, **kwargs):
        yield {}

    monkeypatch.setattr(_script, "job_heartbeat", _stumm)
    monkeypatch.setattr(_script, "messe", _stumm)
    monkeypatch.setattr(_script, "route_kennung", lambda feature: {})

    from src.services import aia_json_llm, feature_router
    monkeypatch.setattr(feature_router, "resolve", lambda feature: object())
    monkeypatch.setattr(feature_router, "make_llm_client", lambda binding: object())
    monkeypatch.setattr(aia_json_llm, "call_json_llm",
                        lambda llm, msgs, endpoint="tool": type(
                            "A", (), {"choices": [type("C", (), {"message": type(
                                "M", (), {"content": _ANTWORT})()})()]})())
    return db, task, gemeldet


class TestMaterialVorDemSkript:
    def test_die_quellen_werden_gelesen_bevor_geschrieben_wird(self, umgebung, monkeypatch):
        db, _task, _ = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)
        monkeypatch.setattr(_script._material, "build",
                            lambda *a, **k: "#1 (Kernaussage) [a.pdf] Der Regelkreis.")

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        assert store.source.startswith("#1 (Kernaussage)")
        assert db.schritte() == ["material", "script", "script_done"]

    def test_das_rohmaterial_wird_nach_der_lesephase_aufgeraeumt(self, umgebung, monkeypatch):
        """material.json und facts.json sind danach nur noch der Upload ein zweites Mal."""
        _db, _task, _ = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)
        monkeypatch.setattr(_script._material, "build", lambda *a, **k: "Material aus Fakten.")

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        assert store.aufgeraeumt is True and store.source == "Material aus Fakten."

    def test_eine_abgebrochene_lesephase_raeumt_nichts_weg(self, umgebung, monkeypatch):
        """Sonst faengt die naechste Etappe ohne Quellen und ohne Fakten von vorn an."""
        _db, _task, _ = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)

        def _zu_spaet(*a, **k):
            raise RunInterrupted

        monkeypatch.setattr(_script._material, "build", _zu_spaet)

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        assert store.aufgeraeumt is False

    def test_die_zweite_etappe_liest_nicht_noch_einmal(self, umgebung, monkeypatch):
        """Steht das Material schon, faellt die ganze Lesephase aus."""
        db, _task, _ = umgebung
        store = _Store(params=_params(), source="Fertiges Material.")
        monkeypatch.setattr(_script, "store", store)

        def _nie(*a, **k):
            raise AssertionError("die Lesephase haette nicht laufen duerfen")

        monkeypatch.setattr(_script._material, "build", _nie)

        _script.run_podcast_script(JOB, UID, "de", 2, 0)

        assert db.schritte() == ["script", "script_done"]

    def test_das_material_wird_in_den_betriebszahlen_vermerkt(self, umgebung, monkeypatch):
        _db, _task, gemeldet = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)
        monkeypatch.setattr(_script._material, "build", lambda *a, **k: "Material aus Fakten.")

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        phase, werte = gemeldet[0]
        assert phase == "material" and werte["zeichen"] == len("Material aus Fakten.")

    def test_ein_leeres_material_laesst_den_auftrag_scheitern(self, umgebung, monkeypatch):
        db, _task, _ = umgebung
        monkeypatch.setattr(_script, "store", _Store(params=_params()))
        monkeypatch.setattr(_script._material, "build", lambda *a, **k: "   ")

        with pytest.raises(RuntimeError):
            _script.run_podcast_script(JOB, UID, "de", 1, 0)
        assert ("failed", None) in db.status

    def test_die_begriffe_werden_am_gebauten_material_gesiebt(self, umgebung, monkeypatch):
        """Nicht an den Rohquellen, sonst stehen Begriffe im Prompt die gar nicht vorkommen."""
        _db, _task, _ = umgebung
        store = _Store(params=_params(glossary={"Regelkreis": "control loop",
                                                "Dampfmaschine": "steam engine"}))
        monkeypatch.setattr(_script, "store", store)
        monkeypatch.setattr(_script._material, "build",
                            lambda *a, **k: "Der Regelkreis haelt den Wert stabil.")

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        assert list(store.params.glossary) == ["Regelkreis"]


class TestEtappenende:
    def test_eine_abgelaufene_uhr_reiht_die_naechste_etappe_ein(self, umgebung, monkeypatch):
        db, task, _ = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)

        def _zu_spaet(*a, **k):
            raise RunInterrupted

        monkeypatch.setattr(_script._material, "build", _zu_spaet)

        _script.run_podcast_script(JOB, UID, "de", 1, 0)

        assert task.aufrufe == [[JOB, UID, "de", 2, 0]]
        # Nichts geschrieben, das Skript kommt erst wenn das Material steht.
        assert store.source == "" and store.script is None

    def test_eine_abgegebene_etappe_tut_gar_nichts(self, umgebung, monkeypatch):
        db, task, _ = umgebung
        store = _Store(params=_params())
        monkeypatch.setattr(_script, "store", store)
        monkeypatch.setattr(_script, "still_mine", lambda job, versuch: False)

        assert _script.run_podcast_script(JOB, UID, "de", 1, 0) == {"lost": True}
        assert db.status == [] and task.aufrufe == []

    def test_ein_abbruch_gibt_den_auftrag_zurueck(self, umgebung, monkeypatch):
        db, _task, _ = umgebung
        monkeypatch.setattr(_script, "store", _Store(params=_params()))

        def _abgebrochen(job):
            raise JobCancelled()

        monkeypatch.setattr(_script, "assert_not_cancelled", _abgebrochen)

        assert _script.run_podcast_script(JOB, UID, "de", 1, 0) == {"cancelled": True}
        assert ("awaiting_user", None) in db.status

    def test_ein_auftrag_ohne_material_scheitert_verstaendlich(self, umgebung, monkeypatch):
        monkeypatch.setattr(_script, "store", _Store(material={}, params=_params()))
        with pytest.raises(RuntimeError, match="ohne Material"):
            _script.run_podcast_script(JOB, UID, "de", 1, 0)
