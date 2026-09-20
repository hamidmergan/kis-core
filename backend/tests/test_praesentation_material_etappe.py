"""Die Materialetappe: Fakten in der Aufgabe, Etappen gegen die Uhr, Rueckfallebene."""

import json

import pytest

from tests.podcast_helpers import FakeAsyncClient, fakten_antwort

from src.features.praesentation.schemas import PraesentationParams
from src.services.facts import RunInterrupted
from src.tasks._stage import StageClock, StageContinue, StageLost
from src.tasks.praesentation_tasks import _material, _outline

UID = 7
JOB = "f" * 32


class _Ablage:
    """Der Auftragsordner im Arbeitsspeicher, er merkt sich auch das Aufraeumen."""

    def __init__(self, quellen=None):
        self.dateien: dict[str, bytes] = {}
        self.geloescht: list[str] = []
        if quellen is not None:
            self.dateien["material.json"] = json.dumps(
                {"sources": quellen, "workspace_id": None, "source_uuids": []}).encode()

    def save_job_file(self, user_id, job_uuid, name, data):
        self.dateien[name] = data
        return f"users/{user_id}/jobs/{job_uuid}/{name}"

    def get_job_file(self, user_id, job_uuid, name):
        try:
            return self.dateien[name]
        except KeyError as e:
            raise FileNotFoundError(name) from e

    def job_file_exists(self, user_id, job_uuid, name):
        return name in self.dateien

    def delete_job_file(self, user_id, job_uuid, name):
        self.geloescht.append(name)
        self.dateien.pop(name, None)


def _quelle(nr: int, text: str = "Inhalt der Quelle.") -> dict:
    return {"source_id": f"doc_{nr:02d}", "filename": f"{nr}.pdf", "content": text}


@pytest.fixture
def ablage(monkeypatch):
    """Ein Auftragsordner mit zwei Rohquellen, verdrahtet in Store und Fakten-Dienst."""
    from src.features.praesentation import store
    from src.services.facts import store as fact_store

    a = _Ablage([_quelle(1), _quelle(2)])
    for name in ("save_job_file", "get_job_file", "job_file_exists", "delete_job_file"):
        monkeypatch.setattr(store, name, getattr(a, name))
    for name in ("save_job_file", "get_job_file", "job_file_exists"):
        monkeypatch.setattr(fact_store, name, getattr(a, name))
    monkeypatch.setattr(fact_store.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(fact_store.db, "touch_job_heartbeat", lambda *a: None)
    return a


@pytest.fixture
def ohne_anbieter(monkeypatch):
    """Kein echter Anbieter und kein Nutzungsprotokoll, die Antworten kommen aus dem Test."""
    monkeypatch.setattr(_material, "log_llm_response", lambda *a, **k: None)
    monkeypatch.setattr(_material, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(_material, "assert_not_cancelled", lambda job: None)
    return monkeypatch


def _mit_antworten(monkeypatch, antworten: dict):
    client = FakeAsyncClient(antworten)
    monkeypatch.setattr(_material, "_llm",
                        lambda: type("L", (), {"_async_client": client, "_model": "m"})())
    return client


def _params(**kw):
    return PraesentationParams(**kw)


class TestMaterialetappe:
    """Fakten sind der erste Weg, die aelteren Wege bleiben darunter stehen."""

    def test_die_fakten_gewinnen_und_der_vorrat_kommt_zurueck(self, ablage, ohne_anbieter):
        _mit_antworten(ohne_anbieter, {
            "1.pdf": [fakten_antwort("Aus der ersten.")],
            "2.pdf": [fakten_antwort("Aus der zweiten.")],
        })
        pool, schnappschuss = _material.build(
            UID, JOB, json.loads(ablage.dateien["material.json"]), _params(), StageClock(), 0)
        assert [f.fact for f in pool] == ["Aus der ersten.", "Aus der zweiten."]
        assert schnappschuss == "", "mit Vorrat braucht es keinen Schnappschuss"

    def test_ohne_fakten_kommt_der_schnappschuss_der_aelteren_wege(self, ablage, ohne_anbieter):
        """Kein Anbieter, keine Fakten. Die Praesentation entsteht trotzdem."""
        def _kein_anbieter():
            raise RuntimeError("kein Anbieter eingerichtet")

        ohne_anbieter.setattr(_material, "_llm", _kein_anbieter)
        pool, schnappschuss = _material.build(
            UID, JOB, json.loads(ablage.dateien["material.json"]), _params(), StageClock(), 0)
        assert pool == []
        assert "Inhalt der Quelle." in schnappschuss

    def test_eine_gerissene_etappe_wird_durchgereicht(self, ablage, ohne_anbieter):
        """Die Uhr gehoert der Aufgabe, hier wird nur gemeldet, dass Zeit fehlt."""
        _mit_antworten(ohne_anbieter, {"1.pdf": [fakten_antwort("Eins.")],
                                       "2.pdf": [fakten_antwort("Zwei.")]})
        abgelaufen = type("Uhr", (), {"over": lambda self: True})()
        with pytest.raises(RunInterrupted):
            _material.build(UID, JOB, json.loads(ablage.dateien["material.json"]),
                            _params(), abgelaufen, 0)

    def test_ein_abgegebener_lauf_schreibt_nichts_mehr(self, ablage, ohne_anbieter):
        _mit_antworten(ohne_anbieter, {"1.pdf": [fakten_antwort("Eins.")],
                                       "2.pdf": [fakten_antwort("Zwei.")]})
        ohne_anbieter.setattr(_material, "still_mine", lambda job, versuch: False)
        with pytest.raises(StageLost):
            _material.build(UID, JOB, json.loads(ablage.dateien["material.json"]),
                            _params(), StageClock(), 0)
        assert "facts.json" not in ablage.dateien


class TestEtappeInDerAufgabe:
    """Was die Aufgabe um die Materialetappe herum tut."""

    @pytest.fixture(autouse=True)
    def _aufgabe(self, monkeypatch):
        monkeypatch.setattr(_outline.db, "update_job_status", lambda *a, **k: None)
        monkeypatch.setattr(_outline.db, "set_job_celery_task_id", lambda *a, **k: None)
        monkeypatch.setattr(_outline, "assert_not_cancelled", lambda job: None)
        monkeypatch.setattr(_outline, "still_mine", lambda job, versuch: True)
        self.eingereiht: list[list] = []
        monkeypatch.setattr(_outline.run_praesentation_build, "apply_async",
                            lambda args: type("T", (), {"id": "c1"})())
        monkeypatch.setattr(_outline, "continue_stage",
                            lambda task, args, job: self.eingereiht.append(list(args)))
        return monkeypatch

    def _params_ablegen(self, ablage):
        from src.features.praesentation import store
        store.save_params(UID, JOB, _params())

    def test_der_vorrat_wird_gesichert_und_die_rohquellen_verschwinden(self, ablage, _aufgabe):
        self._params_ablegen(ablage)
        _aufgabe.setattr(_outline, "_material_bauen",
                         lambda *a: (_vorrat(), ""))
        pool, schnappschuss = _outline._material_phase(JOB, UID, 0, "de")
        assert [f.fact for f in pool] == ["Eine Aussage."]
        assert "material.json" in ablage.geloescht and "facts.json" in ablage.geloescht
        assert "pool.json" in ablage.dateien

    def test_die_rueckfallebene_legt_den_schnappschuss_ab(self, ablage, _aufgabe):
        self._params_ablegen(ablage)
        _aufgabe.setattr(_outline, "_material_bauen", lambda *a: ([], "Der ganze Text."))
        pool, schnappschuss = _outline._material_phase(JOB, UID, 0, "de")
        assert pool == [] and schnappschuss == "Der ganze Text."
        assert ablage.dateien["source.txt"].decode() == "Der ganze Text."
        assert "material.json" in ablage.geloescht

    def test_eine_gerissene_etappe_wird_zur_fortsetzung(self, ablage, _aufgabe):
        self._params_ablegen(ablage)

        def _reisst(*a):
            raise RunInterrupted

        _aufgabe.setattr(_outline, "_material_bauen", _reisst)
        with pytest.raises(StageContinue):
            _outline._material_phase(JOB, UID, 0, "de")
        assert "material.json" not in ablage.geloescht, "die Rohquellen traegt die naechste Etappe"

    def test_ohne_jedes_material_scheitert_der_auftrag(self, ablage, _aufgabe):
        self._params_ablegen(ablage)
        _aufgabe.setattr(_outline, "_material_bauen", lambda *a: ([], "   "))
        with pytest.raises(RuntimeError):
            _outline._material_phase(JOB, UID, 0, "de")

    def test_fertiges_material_wird_nicht_noch_einmal_gebaut(self, ablage, _aufgabe):
        """Nach einem Neustart steht der Vorrat schon da, die Leseaufrufe sind bezahlt."""
        from src.features.praesentation import store

        self._params_ablegen(ablage)
        store.save_pool(UID, JOB, _vorrat())

        def _verboten(*a):
            raise AssertionError("Das Material steht bereits")

        _aufgabe.setattr(_outline, "_material_bauen", _verboten)
        pool, _ = _outline.material_holen(UID, JOB, 0, "de")
        assert [f.fact for f in pool] == ["Eine Aussage."]


def _vorrat():
    from src.services.facts import Fact
    return [Fact(fact_id=1, category="These", fact="Eine Aussage.", citation="Beleg",
                 source_id="doc_01", source_name="1.pdf")]


class TestKetteAmStueck:
    """Von den Rohquellen bis zur Gliederung, ohne dass eine Quelle unterwegs verloren geht."""

    @pytest.fixture(autouse=True)
    def _aufgabe(self, monkeypatch):
        from contextlib import contextmanager

        @contextmanager
        def leer(*a, **k):
            yield {}

        monkeypatch.setattr(_outline, "job_heartbeat", leer)
        monkeypatch.setattr(_outline.db, "update_job_status", lambda *a, **k: None)
        monkeypatch.setattr(_outline.db, "set_job_celery_task_id", lambda *a, **k: None)
        monkeypatch.setattr(_outline, "assert_not_cancelled", lambda job: None)
        monkeypatch.setattr(_outline, "still_mine", lambda job, versuch: True)
        monkeypatch.setattr(_outline.feature_router, "resolve", lambda f: object())
        monkeypatch.setattr(_outline.feature_router, "make_llm_client", lambda b: object())
        monkeypatch.setattr(_outline.run_praesentation_build, "apply_async",
                            lambda args: type("T", (), {"id": "c1"})())
        return monkeypatch

    def _vorlage(self, monkeypatch):
        from src.features.praesentation import store
        from src.features.praesentation.vorlage import Analyse, Feld, Layout

        deck = Layout(0, "Titel", "deckblatt", [Feld(0, "ueberschrift", "TITLE", 0, 0, 100, 10, 44)])
        text = Layout(1, "Text", "text", [
            Feld(0, "ueberschrift", "BODY", 0, 0, 100, 10, 32),
            Feld(2, "fliesstext", "OBJECT", 0, 0, 900000, 900000, 16, True, 100)])
        analyse = Analyse(breite=1, hoehe=1, typeface="Arial", layouts=[deck, text],
                          rollen={"deckblatt": [0], "text": [1], "abschluss": [0]})
        store.save_template_meta(UID, JOB, analyse)
        store.save_params(UID, JOB, _params())

    def test_zehn_quellen_landen_alle_im_vorrat_und_die_gliederung_zeigt_darauf(
            self, ablage, ohne_anbieter, _aufgabe):
        """Der Lauf von vorn bis zur Gliederung, mit zehn Quellen, die alle gross sind."""
        from src.features.praesentation import store

        quellen = [_quelle(n, "X" * 150_000) for n in range(1, 11)]
        ablage.dateien["material.json"] = json.dumps(
            {"sources": quellen, "workspace_id": None, "source_uuids": []}).encode()
        self._vorlage(_aufgabe)
        _mit_antworten(ohne_anbieter, {f"{n}.pdf": [fakten_antwort(f"Aus Quelle {n}.")]
                                       for n in range(1, 11)})

        gesehen = []

        def _gliederung(llm, nachrichten, endpoint="tool"):
            gesehen.append(nachrichten[1]["content"])
            rollen = ["deckblatt"] + ["text"] * 4 + ["abschluss"]
            inhalt = json.dumps({"title": "Deck", "subtitle": "", "slides": [
                {"role": r, "title": f"T{i}", "gist": "g", "fact_ids": [i + 1]}
                for i, r in enumerate(rollen)]})
            return type("R", (), {"choices": [type("C", (), {
                "message": type("M", (), {"content": inhalt})()})()]})()

        _aufgabe.setattr(_outline, "call_json_llm", _gliederung)
        _outline.run_praesentation_outline.run(JOB, UID, "de")

        vorrat = store.load_pool(UID, JOB)
        assert {f.source_name for f in vorrat} == {f"{n}.pdf" for n in range(1, 11)}
        assert "FACTS:" in gesehen[0], "die Gliederung wird aus dem Vorrat geplant"
        outline = store.load_outline(UID, JOB)
        assert [r.fact_ids for r in outline.rows] == [[1], [2], [3], [4], [5], [6]]
        assert "material.json" in ablage.geloescht, "die Rohquellen bleiben nicht liegen"
