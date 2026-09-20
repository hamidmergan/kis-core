"""The tasks: outline in one call, build in stages, finished pictures stay."""

import json
from contextlib import contextmanager

import pytest

from src.features.praesentation.schemas import Body, ImageSpec, Outline, OutlineRow, PraesentationParams, Slide
from src.features.praesentation.vorlage import Analyse, Feld, Layout
from src.tasks._stage import StageClock
from src.tasks.praesentation_tasks import _build, _outline

UID = 7
JOB = "f" * 32


def _analyse():
    deck = Layout(0, "Titel", "deckblatt", [Feld(0, "ueberschrift", "TITLE", 0, 0, 100, 10, 44),
                                          Feld(21, "bild", "PICTURE", 0, 0, 400, 100)])
    text = Layout(1, "Text", "text", [Feld(0, "ueberschrift", "BODY", 0, 0, 100, 10, 32),
                                     Feld(2, "fliesstext", "OBJECT", 0, 0, 900000, 900000, 16, True, 100)])
    return Analyse(breite=1, hoehe=1, typeface="Arial", layouts=[deck, text],
                   rollen={"deckblatt": [0], "text": [1], "abschluss": [0]})


class _Store:
    def __init__(self, outline, slides=None):
        self.params = PraesentationParams(style_text="STYLE")
        self.outline = outline
        self.slides = slides or []
        self.bilder = {}
        self.deck = None
        self.previews = {}
        self.analyse = _analyse()
        self.slide_sources = {}
        self.gelesene_quellen = []
        self.pool = []

    load_params = lambda self, u, j: self.params
    load_source = lambda self, u, j: "Quelle"
    load_template = lambda self, u, j: b"vorlage"
    load_template_meta = lambda self, u, j: self.analyse
    load_outline = lambda self, u, j: self.outline
    load_slides = lambda self, u, j: list(self.slides)
    load_pool = lambda self, u, j: list(self.pool)

    def save_outline(self, u, j, o): self.outline = o
    save_user_outline = save_outline
    def save_slides(self, u, j, s): self.slides = list(s)
    save_user_slides = save_slides
    def has_image(self, u, j, sid, slot): return (sid, slot) in self.bilder
    def save_image(self, u, j, sid, slot, data): self.bilder[(sid, slot)] = data
    def get_image(self, u, j, sid, slot): return self.bilder.get((sid, slot))

    def save_deck(self, u, j, data):
        self.deck = data
        self.deck_path = f"stored/{u}/{j}/deck.pptx"
        return self.deck_path

    def save_preview(self, u, j, sid, data): self.previews[sid] = data

    def load_slide_source(self, u, j, sid):
        self.gelesene_quellen.append(sid)
        return self.slide_sources.get(sid, "")


class _Db:
    def __init__(self):
        self.status = []
        self.claim = ("running", 0)

    def update_job_status(self, job_uuid, status, progress=None, error_message=None):
        self.status.append((status, progress))

    def reset_job_to_awaiting(self, job_uuid): self.status.append(("awaiting_user", None))
    def set_job_celery_task_id(self, job_uuid, task_id): pass
    def job_claim(self, job_uuid): return self.claim
    def touch_job_heartbeat(self, job_uuid): pass


class _Llm:
    def __init__(self, antworten): self.antworten = list(antworten)

    def __call__(self, llm, nachrichten, endpoint="tool"):
        class _R:
            pass
        r = _R()
        r.choices = [type("C", (), {"message": type("M", (), {"content": self.antworten.pop(0)})()})()]
        return r


@pytest.fixture
def umgebung(monkeypatch):
    @contextmanager
    def leer(*a, **k):
        yield {}

    for modul in (_outline, _build):
        monkeypatch.setattr(modul, "job_heartbeat", leer)
        monkeypatch.setattr(modul, "assert_not_cancelled", lambda job: None)
        monkeypatch.setattr(modul.feature_router, "resolve", lambda f: object())
        monkeypatch.setattr(modul.feature_router, "make_llm_client", lambda b: object())
    gestartet: list[list] = []
    monkeypatch.setattr(_outline.run_praesentation_build, "apply_async",
                        lambda args: gestartet.append(list(args)) or type("T", (), {"id": "celery-1"})())
    monkeypatch.gestartet = gestartet
    for modul in (_outline, _build):
        monkeypatch.setattr(modul, "still_mine", lambda job, token: True)
    monkeypatch.setattr(_build.vorschau, "render", lambda deck, dpi=80: [b"p"] * 99)
    monkeypatch.setattr(_build.bau, "baue", lambda *a, **k: b"deck")
    monkeypatch.setattr(_build.teilung, "teile_ueberlauf", lambda slides, a: slides)
    monkeypatch.setattr(_build, "save_result_and_evict", lambda uid, job, pfad, name: None)
    return monkeypatch


def _outline_antwort(n):
    rollen = ["deckblatt"] + ["text"] * (n - 2) + ["abschluss"]
    return json.dumps({"title": "Deck", "subtitle": "", "slides": [
        {"role": r, "title": f"T{i}", "gist": "g"} for i, r in enumerate(rollen)]})


class TestOutline:
    def test_schreibt_gliederung_und_gibt_den_job_zurueck(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", _Llm([_outline_antwort(6)]))
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert len(st.outline.rows) == 6 and st.outline.rows[0].role == "deckblatt"
        # There is no outline step to stop at any more, the slides follow straight away.
        assert umgebung.gestartet == [[JOB, UID, "de", 1, 0, None, False]]
        assert db.status[-1] == ("pending", {"step": "texte", "final": False})

    def test_zweiter_versuch_nach_unbrauchbarer_antwort(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", _Llm(["Quatsch", _outline_antwort(5)]))
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert len(st.outline.rows) == 5

    def test_zweimal_unbrauchbar_ist_fehlgeschlagen(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", _Llm(["Quatsch", "Nochmal Quatsch"]))
        with pytest.raises(RuntimeError):
            _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert db.status[-1][0] == "failed"


def _folien_antwort(ids, notes=""):
    return json.dumps({"slides": [
        {"id": i, "title": f"T {i}", "body": {"kind": "bullets", "items": ["a", "b"]},
         "images": [{"prompt": "a lab"}], "notes": notes} for i in ids]})


# Named differently from the imported `_outline` submodule, or it would shadow it at module scope.
def _gliederung(n):
    rollen = ["deckblatt"] + ["text"] * (n - 2) + ["abschluss"]
    return Outline(title="Deck", rows=[OutlineRow(id=f"s{i + 1}", role=r, title=f"T{i}") for i, r in enumerate(rollen)])


class TestBuild:
    def test_texte_in_paketen_bilder_bau_vorschau(self, umgebung):
        st, db = _Store(_gliederung(7)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort([f"s{i}" for i in range(1, 6)]),
                                                        _folien_antwort(["s6", "s7"])]))
        erzeugt = []
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: erzeugt.append((prompt, size)) or b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert [s.id for s in st.slides] == [f"s{i}" for i in range(1, 8)]
        assert st.slides[1].layout == 1 and st.slides[0].layout == 0
        # only the cover and the closing slide have an image field in this template
        assert sorted(st.bilder) == [("s1", 0), ("s7", 0)]
        # The stub field is a few EMU wide, so the long side lands on its floor and the short one on its minimum.
        assert erzeugt[0][0].startswith("STYLE Subject:") and erzeugt[0][1] == "768x256"
        assert st.deck == b"deck" and set(st.previews) == {f"s{i}" for i in range(1, 8)}
        assert db.status[-1] == ("awaiting_user", {"step": "slides_done", "final": False})
        schritte = [p["step"] for s, p in db.status if p]
        assert schritte[:1] == ["texte"] and "bilder" in schritte and "bau" in schritte

    def test_vorhandene_texte_und_bilder_bleiben(self, umgebung):
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="Alt", images=[ImageSpec(prompt="x")]),
               Slide(id="s2", role="text", layout=1, title="Alt2", body=Body(items=["x"]))]
        st, db = _Store(_gliederung(5), alt), _Db()
        st.bilder[("s1", 0)] = b"alt"
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s3", "s4", "s5"])]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"neu")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert st.slides[0].title == "Alt" and st.bilder[("s1", 0)] == b"alt"
        assert st.bilder[("s5", 0)] == b"neu"

    def test_nur_erzwingt_text_und_bild_neu(self, umgebung):
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="Alt", images=[ImageSpec(prompt="x")]),
               Slide(id="s2", role="text", layout=1, title="Alt2", body=Body(items=["x"])),
               Slide(id="s3", role="abschluss", layout=0, title="Ende", images=[ImageSpec(prompt="y")])]
        st, db = _Store(_gliederung(3), alt), _Db()
        st.bilder[("s1", 0)] = b"alt"
        st.bilder[("s3", 0)] = b"alt3"
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s2"])]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"neu")
        _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, {"text": ["s2"], "bild": ["s1"]})
        assert st.slides[1].title == "T s2" and st.bilder[("s1", 0)] == b"neu" and st.bilder[("s3", 0)] == b"alt3"

    def test_folie_mit_eigenem_material_bekommt_ihres_statt_des_schnappschusses(self, umgebung):
        """A slide added later was given its own searched material, the run's snapshot must not replace it."""
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="A", images=[ImageSpec(prompt="x")]),
               Slide(id="s2", role="text", layout=1, title=""),
               Slide(id="s3", role="abschluss", layout=0, title="Ende", images=[ImageSpec(prompt="y")])]
        st, db = _Store(_gliederung(3), alt), _Db()
        st.slide_sources["s2"] = "Nur die Stelle zur Kühlung"
        st.bilder[("s1", 0)] = st.bilder[("s3", 0)] = b"alt"
        gesehen = []
        llm = _Llm([_folien_antwort(["s2"])])

        def _merken(client, nachrichten, endpoint="tool"):
            gesehen.append(nachrichten[1]["content"])
            return llm(client, nachrichten, endpoint)

        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _merken)
        _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, {"text": ["s2"], "bild": []})
        assert "Nur die Stelle zur Kühlung" in gesehen[0]
        assert "Quelle" not in gesehen[0], "der Schnappschuss darf das eigene Material nicht verdraengen"

    def test_erster_bau_fragt_nicht_nach_eigenem_material(self, umgebung):
        """Nothing is forced, so no slide can have its own material and no storage read is worth it."""
        st, db = _Store(_gliederung(3)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"])]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert st.gelesene_quellen == []

    def test_abgewaehlte_notizen_kommen_nicht_in_die_datei(self, umgebung):
        st, db = _Store(_gliederung(3)), _Db()
        st.params = PraesentationParams(style_text="STYLE", notes=True, notes_include=False)
        gesehen = []
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build.bau, "baue", lambda *a, **k: (gesehen.append(a[5]), b"deck")[1])
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"], "So spreche ich dazu.")]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert gesehen == [False]

    def test_gewollte_notizen_gehen_in_die_datei(self, umgebung):
        st, db = _Store(_gliederung(3)), _Db()
        st.params = PraesentationParams(style_text="STYLE", notes=True)
        gesehen = []
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build.bau, "baue", lambda *a, **k: (gesehen.append(a[5]), b"deck")[1])
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"], "So spreche ich dazu.")]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert gesehen == [True]

    def test_etappe_laeuft_aus_und_reiht_sich_neu_ein(self, umgebung):
        st, db = _Store(_gliederung(6)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort([f"s{i}" for i in range(1, 6)])]))
        umgebung.setattr(_build, "StageClock", lambda: StageClock(seconds=0))
        eingereiht = []
        umgebung.setattr(_build, "continue_stage", lambda task, args, job: eingereiht.append(args))
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert eingereiht == [[JOB, UID, "de", 2, 0, None, False]]
        assert [s.id for s in st.slides] == [f"s{i}" for i in range(1, 6)]  # the first batch is kept

    def test_etappe_im_bilderteil_reiht_sich_neu_ein(self, umgebung):
        """A clock that runs out mid-picture re-queues the same wishes, an already-drawn picture stays untouched."""
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="A", images=[ImageSpec(prompt="x")]),
               Slide(id="s2", role="text", layout=1, title="B", body=Body(items=["a"])),
               Slide(id="s3", role="abschluss", layout=0, title="E", images=[ImageSpec(prompt="y")])]
        st, db = _Store(_gliederung(3), alt), _Db()
        st.bilder[("s1", 0)] = b"schon-da"
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "StageClock", lambda: StageClock(seconds=0))
        erzeugt = []
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: erzeugt.append(prompt) or b"png")
        eingereiht = []
        umgebung.setattr(_build, "continue_stage", lambda task, args, job: eingereiht.append(args))
        nur = {"text": [], "bild": ["s3"]}

        _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, nur, True)
        # The clock is over before the first picture starts, so the stage re-queues itself with the same wishes.
        assert eingereiht == [[JOB, UID, "de", 2, 0, nur, True]]
        assert erzeugt == [] and st.bilder[("s1", 0)] == b"schon-da" and ("s3", 0) not in st.bilder

        # The next stage has time again, only the still-missing picture is drawn.
        umgebung.setattr(_build, "StageClock", StageClock)
        _build.run_praesentation_build.run(JOB, UID, "de", 2, 0, nur, True)
        assert len(erzeugt) == 1 and erzeugt[0].endswith("y")
        assert st.bilder[("s1", 0)] == b"schon-da" and ("s3", 0) in st.bilder
        assert db.status[-1] == ("success", {"step": "done", "final": True})

    def test_fehlendes_bild_bricht_den_bau_nicht_ab(self, umgebung):
        st, db = _Store(_gliederung(5)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort([f"s{i}" for i in range(1, 6)])]))

        def kaputt(prompt, size):
            raise RuntimeError("Anbieter weg")

        umgebung.setattr(_build.bild, "erzeuge", kaputt)
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert st.deck == b"deck" and st.bilder == {}
        assert db.status[-1][0] == "awaiting_user"

    def test_final_setzt_erfolg_und_ergebnis(self, umgebung):
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="A"),
               Slide(id="s2", role="abschluss", layout=0, title="E")]
        st, db = _Store(Outline(title="Mein Deck", rows=[OutlineRow(id="s1", role="deckblatt", title="A"),
                                                          OutlineRow(id="s2", role="abschluss", title="E")]), alt), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        ergebnisse = []
        umgebung.setattr(_build, "save_result_and_evict",
                         lambda uid, job, pfad, name: ergebnisse.append((uid, job, pfad, name)))
        _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, None, True)
        assert db.status[-1] == ("success", {"step": "done", "final": True})
        # The exact path store.save_deck returned, not a hand-built S3 key.
        assert ergebnisse == [(UID, JOB, st.deck_path, "Mein Deck.pptx")]

    def test_fehler_geht_in_die_anlaufbahn(self, umgebung):
        st, db = _Store(_gliederung(5)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm(["Quatsch", "Quatsch", "Quatsch"]))
        gemeldet = []
        umgebung.setattr(_build, "attempt_failed", lambda job, msg: gemeldet.append(msg))
        with pytest.raises(RuntimeError):
            _build.run_praesentation_build.run(JOB, UID, "de")
        assert gemeldet


class TestBauMitVorrat:
    """Ein Folienpaket sieht nur noch die Fakten seiner Zeilen."""

    def _vorrat(self):
        from src.services.facts import Fact
        return [Fact(fact_id=n, category="These", fact=f"Aussage {n}", citation=f"Beleg {n}",
                     source_id="doc_01", source_name="a.pdf") for n in (1, 2, 3)]

    def _outline(self):
        return Outline(title="Deck", rows=[
            OutlineRow(id="s1", role="deckblatt", title="T1", fact_ids=[1]),
            OutlineRow(id="s2", role="text", title="T2", fact_ids=[2]),
            OutlineRow(id="s3", role="abschluss", title="T3", fact_ids=[3])])

    def _lauf(self, umgebung, pool):
        st, db = _Store(self._outline()), _Db()
        st.pool = pool
        gesehen = []
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "db", db)

        def _ruf(llm, nachrichten, endpoint="tool"):
            gesehen.append(nachrichten[1]["content"])
            ids = [r.id for r in st.outline.rows]
            return _Llm([json.dumps({"slides": [
                {"id": i, "title": f"T{i}", "body": {"kind": "bullets", "items": ["x"]}}
                for i in ids]})])(llm, nachrichten, endpoint)

        umgebung.setattr(_build, "call_json_llm", _ruf)
        umgebung.setattr(_build, "PRAESENTATION_BATCH", 99)
        _build.run_praesentation_build.run(JOB, UID, "de")
        return gesehen

    def test_mit_vorrat_traegt_jede_folie_ihre_eigenen_fakten(self, umgebung):
        gesehen = self._lauf(umgebung, self._vorrat())
        assert "Aussage 1" in gesehen[0] and "Aussage 2" in gesehen[0]
        assert "Quelle" not in gesehen[0], "der gemeinsame Schnappschuss faellt weg"

    def test_ohne_vorrat_bleibt_der_schnappschuss(self, umgebung):
        gesehen = self._lauf(umgebung, [])
        assert gesehen[0].startswith("MATERIAL:\nQuelle")
