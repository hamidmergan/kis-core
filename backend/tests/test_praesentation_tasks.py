"""The tasks: outline in one call, build in stages, finished pictures stay."""

import json
import threading
import time
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


class _Quellen:
    """The sources of a run as they would come from sources.json."""

    def load_sources(self, u, j):
        from src.services.source_reading import Piece, Source

        return [Source(dateiname="a.pdf", fassung="x", text="Quelle", seiten=1,
                       stuecke=[Piece(seite=1, von=0, bis=6)])]

    def as_block(self, quellen):
        return "Quelle"


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
        self.grundlage = None

    load_params = lambda self, u, j: self.params
    load_template = lambda self, u, j: b"vorlage"
    load_template_meta = lambda self, u, j: self.analyse
    load_outline = lambda self, u, j: self.outline
    load_slides = lambda self, u, j: list(self.slides)
    load_map = lambda self, u, j: self.grundlage
    save_map = lambda self, u, j, d: setattr(self, "grundlage", d)

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
    """Canned answers, a slide answer goes to the call that asks for its first slide."""

    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.sperre = threading.Lock()
        self.gleichzeitig = self.hoechstens = 0

    def _passende(self, nachrichten) -> str:
        text = nachrichten[-1]["content"]
        for i, a in enumerate(self.antworten):
            try:
                erste = json.loads(a)["slides"][0]["id"]
            except (ValueError, KeyError, IndexError, TypeError):
                continue
            if f"SLIDE {erste} " in text:
                return self.antworten.pop(i)
        return self.antworten.pop(0)

    def __call__(self, llm, nachrichten, endpoint="tool"):
        with self.sperre:
            self.gleichzeitig += 1
            self.hoechstens = max(self.hoechstens, self.gleichzeitig)
            inhalt = self._passende(nachrichten)
        time.sleep(0.01)
        with self.sperre:
            self.gleichzeitig -= 1
        class _R:
            pass
        r = _R()
        r.choices = [type("C", (), {"message": type("M", (), {"content": inhalt})()})()]
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
        umgebung.setattr(_outline, "quellen", _Quellen())
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
        umgebung.setattr(_outline, "quellen", _Quellen())
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", _Llm(["Quatsch", _outline_antwort(5)]))
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert len(st.outline.rows) == 5

    def _zwei_dateien(self):
        from src.services.source_reading import Piece, Source

        class _Zwei(_Quellen):
            def load_sources(self, u, j):
                return [Source(dateiname=n, fassung="x", text="Text", seiten=1,
                               stuecke=[Piece(seite=1, von=0, bis=4)]) for n in ("a.pdf", "b.pdf")]
        return _Zwei()

    def _mit_refs(self, *refs):
        rollen = ["deckblatt"] + ["text"] * len(refs) + ["abschluss"]
        eintraege = [[]] + [list(r) for r in refs] + [[]]
        return json.dumps({"title": "Deck", "slides": [
            {"role": r, "title": f"T{i}", "gist": "g", "refs": e}
            for i, (r, e) in enumerate(zip(rollen, eintraege))]})

    def test_eine_ausgelassene_datei_wird_einmal_nachgefordert(self, umgebung):
        st, db = _Store(None), _Db()
        llm = _Llm([self._mit_refs([1], [1]), self._mit_refs([1], [2])])
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", self._zwei_dateien())
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", llm)
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert [r.stellen for r in st.outline.rows[1:-1]] == [[1], [2]]
        assert llm.antworten == []

    def test_bleibt_die_luecke_gilt_der_bessere_versuch(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", self._zwei_dateien())
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm",
                         _Llm([self._mit_refs([1], [1]), "Quatsch"]))
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert [r.stellen for r in st.outline.rows[1:-1]] == [[1], [1]]

    def test_eine_unausgewogene_gliederung_wird_einmal_nachgefordert(self, umgebung):
        st, db = _Store(None), _Db()
        schief = self._mit_refs([1], [1], [1], [1], [1], [2])
        ausgewogen = self._mit_refs([1], [1], [2], [2])
        llm = _Llm([schief, ausgewogen])
        gesehen = []
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", self._zwei_dateien())
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", lambda l, n, endpoint="": gesehen.append(n) or llm(l, n))
        _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert [r.stellen for r in st.outline.rows[1:-1]] == [[1], [1], [2], [2]]
        assert "UNBALANCED" in gesehen[1][1]["content"] and "a.pdf: 5 slides instead of 3" in gesehen[1][1]["content"]
        assert "a.pdf: 3, b.pdf: 2" in gesehen[0][0]["content"]

    def test_zweimal_unbrauchbar_ist_fehlgeschlagen(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", _Quellen())
        umgebung.setattr(_outline, "db", db)
        umgebung.setattr(_outline, "call_json_llm", _Llm(["Quatsch", "Nochmal Quatsch"]))
        gemeldet = []
        umgebung.setattr(_outline, "attempt_failed", lambda job, msg, busy=False, **k: gemeldet.append(busy))
        with pytest.raises(RuntimeError):
            _outline.run_praesentation_outline.run(JOB, UID, "de")
        # An unusable answer is no overload, the recovery path lets it fail as before.
        assert gemeldet == [False]

    def test_eine_ueberlastete_ki_laesst_die_gliederung_warten(self, umgebung):
        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", _Quellen())
        umgebung.setattr(_outline, "db", db)

        def zu_langsam(*a, **k):
            raise RuntimeError("Request timed out.")

        umgebung.setattr(_outline, "call_json_llm", zu_langsam)
        gemeldet = []
        umgebung.setattr(_outline, "attempt_failed", lambda job, msg, busy=False, **k: gemeldet.append(busy))
        with pytest.raises(RuntimeError):
            _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert gemeldet == [True]

    def test_beim_warten_steht_der_hinweis_auf_die_ueberlastete_ki(self, umgebung):
        """Run 14: the waiting outline showed its error text although it continued by itself."""
        from src.i18n import t

        st, db = _Store(None), _Db()
        umgebung.setattr(_outline, "store", st)
        umgebung.setattr(_outline, "quellen", _Quellen())
        umgebung.setattr(_outline, "db", db)

        def zu_langsam(*a, **k):
            raise RuntimeError("Request timed out.")

        umgebung.setattr(_outline, "call_json_llm", zu_langsam)
        texte = []
        umgebung.setattr(_outline, "attempt_failed", lambda job, msg, busy=False, **k: texte.append(msg))
        with pytest.raises(RuntimeError):
            _outline.run_praesentation_outline.run(JOB, UID, "de")
        assert texte == [t("job.upstreamBusy", "de")]


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
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _merken)
        _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, {"text": ["s2"], "bild": []})
        assert "Nur die Stelle zur Kühlung" in gesehen[0]
        assert "Quelle" not in gesehen[0], "der Schnappschuss darf das eigene Material nicht verdraengen"

    def test_erster_bau_fragt_nicht_nach_eigenem_material(self, umgebung):
        """Nothing is forced, so no slide can have its own material and no storage read is worth it."""
        st, db = _Store(_gliederung(3)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build.bau, "baue", lambda *a, **k: (gesehen.append(a[5]), b"deck")[1])
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"], "So spreche ich dazu.")]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert gesehen == [True]

    def test_die_datei_traegt_das_datum_des_baus(self, umgebung):
        st, db = _Store(_gliederung(3)), _Db()
        gesehen = []
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build.bau, "baue", lambda *a, **k: (gesehen.append(k.get("datum")), b"deck")[1])
        umgebung.setattr(_build.bau, "datum_text", lambda sprache: f"heute {sprache}")
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"])]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert gesehen == ["heute de"]

    def test_der_name_kommt_aufs_deckblatt(self, umgebung):
        st, db = _Store(_gliederung(3)), _Db()
        st.params = PraesentationParams(presenter="Erika Muster")
        gesehen = []
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build.bau, "baue", lambda *a, **k: (gesehen.append(k.get("vortragend")), b"deck")[1])
        umgebung.setattr(_build, "call_json_llm", _Llm([_folien_antwort(["s1", "s2", "s3"])]))
        umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert gesehen == ["Erika Muster"]

    def test_etappe_laeuft_aus_und_reiht_sich_neu_ein(self, umgebung):
        st, db = _Store(_gliederung(16)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm([
            _folien_antwort([f"s{i}" for i in range(a, a + 5)]) for a in (1, 6, 11)]))
        umgebung.setattr(_build, "StageClock", lambda: StageClock(seconds=0))
        eingereiht = []
        umgebung.setattr(_build, "continue_stage", lambda task, args, job: eingereiht.append(args))
        _build.run_praesentation_build.run(JOB, UID, "de")
        assert eingereiht == [[JOB, UID, "de", 2, 0, None, False]]
        # The first wave of batches is kept, the last batch waits for the next stage.
        assert [s.id for s in st.slides] == [f"s{i}" for i in range(1, 16)]

    def test_etappe_im_bilderteil_reiht_sich_neu_ein(self, umgebung):
        """A clock that runs out mid-picture re-queues the same wishes, an already-drawn picture stays untouched."""
        alt = [Slide(id="s1", role="deckblatt", layout=0, title="A", images=[ImageSpec(prompt="x")]),
               Slide(id="s2", role="text", layout=1, title="B", body=Body(items=["a"])),
               Slide(id="s3", role="abschluss", layout=0, title="E", images=[ImageSpec(prompt="y")])]
        st, db = _Store(_gliederung(3), alt), _Db()
        st.bilder[("s1", 0)] = b"schon-da"
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
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
        assert len(erzeugt) == 1 and "Subject: y " in erzeugt[0]
        assert st.bilder[("s1", 0)] == b"schon-da" and ("s3", 0) in st.bilder
        assert db.status[-1] == ("success", {"step": "done", "final": True})

    def test_fehlendes_bild_bricht_den_bau_nicht_ab(self, umgebung):
        st, db = _Store(_gliederung(5)), _Db()
        umgebung.setattr(_build, "store", st)
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
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
        umgebung.setattr(_build, "quellen", _Quellen())
        umgebung.setattr(_build, "db", db)
        umgebung.setattr(_build, "call_json_llm", _Llm(["Quatsch", "Quatsch", "Quatsch"]))
        gemeldet = []
        umgebung.setattr(_build, "attempt_failed", lambda job, msg, **k: gemeldet.append(msg))
        with pytest.raises(RuntimeError):
            _build.run_praesentation_build.run(JOB, UID, "de")
        assert gemeldet




def test_ein_voller_anbieter_beim_bau_wird_als_voll_gemeldet(umgebung):
    st, db = _Store(_gliederung(5)), _Db()
    umgebung.setattr(_build, "store", st)
    umgebung.setattr(_build, "quellen", _Quellen())
    umgebung.setattr(_build, "db", db)

    def voll(*a, **k):
        raise RuntimeError("Server error '503 Service Unavailable'")

    umgebung.setattr(_build, "call_json_llm", voll)
    gemeldet = []
    umgebung.setattr(_build, "attempt_failed", lambda job, msg, **k: gemeldet.append(k))
    with pytest.raises(RuntimeError):
        _build.run_praesentation_build.run(JOB, UID, "de")
    assert gemeldet == [{"busy": True, "refused": False}]


def test_die_folienpakete_werden_gleichzeitig_geschrieben(umgebung):
    st, db = _Store(_gliederung(15)), _Db()
    umgebung.setattr(_build, "store", st)
    umgebung.setattr(_build, "quellen", _Quellen())
    umgebung.setattr(_build, "db", db)
    llm = _Llm([_folien_antwort([f"s{i}" for i in range(a, a + 5)]) for a in (1, 6, 11)])
    umgebung.setattr(_build, "call_json_llm", llm)
    umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
    _build.run_praesentation_build.run(JOB, UID, "de")
    assert [s.id for s in st.slides] == [f"s{i}" for i in range(1, 16)]
    assert llm.hoechstens == 3


class TestNachfassen:
    FORM = {"s2": {"ueberschrift": 6, "zwischentitel": [], "fliesstexte": [120], "bilder": 0, "body_kinds": ["bullets"]}}
    ROWS = [OutlineRow(id="s2", role="text", title="T")]

    @staticmethod
    def _antwort(n):
        return json.dumps({"slides": [{"id": "s2", "title": "T", "body": {"kind": "bullets",
                                                                          "items": [f"p{i}" for i in range(n)]}}]})

    def _erste(self, n):
        from src.features.praesentation import folien
        return folien.parse_answer(self._antwort(n), self.ROWS, self.FORM)

    def test_eine_duenne_folie_wird_einmal_nachgefragt(self, monkeypatch):
        llm = _Llm([self._antwort(5)])
        monkeypatch.setattr(_build, "call_json_llm", llm)
        neu = _build._nachfassen(None, [{"role": "user", "content": "U"}], "A", self._erste(1), self.ROWS,
                                 self.FORM, False, JOB)
        assert len(neu[0].body.items) == 5 and llm.antworten == []

    def test_eine_volle_folie_kostet_keinen_aufruf(self, monkeypatch):
        monkeypatch.setattr(_build, "call_json_llm", lambda *a, **k: pytest.fail("kein zweiter Aufruf"))
        neu = _build._nachfassen(None, [], "A", self._erste(5), self.ROWS, self.FORM, False, JOB)
        assert len(neu[0].body.items) == 5

    def test_eine_duennere_zweite_fassung_verliert(self, monkeypatch):
        monkeypatch.setattr(_build, "call_json_llm", _Llm([self._antwort(1)]))
        neu = _build._nachfassen(None, [], "A", self._erste(2), self.ROWS, self.FORM, False, JOB)
        assert len(neu[0].body.items) == 2

    def test_eine_kaputte_nachfrage_laesst_die_erste_fassung_stehen(self, monkeypatch):
        monkeypatch.setattr(_build, "call_json_llm", _Llm(["Quatsch"]))
        neu = _build._nachfassen(None, [], "A", self._erste(1), self.ROWS, self.FORM, False, JOB)
        assert len(neu[0].body.items) == 1


def test_ein_voller_bildanbieter_holt_das_bild_spaeter_nach(umgebung):
    """No seat at the provider means the picture waits for the next stage instead of missing."""
    from src.services.provider_slots import ProviderFull

    alt = [Slide(id="s1", role="deckblatt", layout=0, title="A", images=[ImageSpec(prompt="x")]),
           Slide(id="s2", role="text", layout=1, title="B", body=Body(items=["a"])),
           Slide(id="s3", role="abschluss", layout=0, title="E", images=[ImageSpec(prompt="y")])]
    st, db = _Store(_gliederung(3), alt), _Db()
    umgebung.setattr(_build, "store", st)
    umgebung.setattr(_build, "quellen", _Quellen())
    umgebung.setattr(_build, "db", db)
    eingereiht = []
    umgebung.setattr(_build, "continue_stage", lambda task, args, job: eingereiht.append(args))

    def voll(prompt, size):
        raise ProviderFull("models.mylab.example/images", 120)

    umgebung.setattr(_build.bild, "erzeuge", voll)
    _build.run_praesentation_build.run(JOB, UID, "de", 1, 0, None, True)
    assert eingereiht == [[JOB, UID, "de", 2, 0, None, True]]
    assert st.bilder == {} and st.deck is None

    umgebung.setattr(_build.bild, "erzeuge", lambda prompt, size: b"png")
    _build.run_praesentation_build.run(JOB, UID, "de", 2, 0, None, True)
    assert set(st.bilder) == {("s1", 0), ("s3", 0)}
    assert db.status[-1] == ("success", {"step": "done", "final": True})
