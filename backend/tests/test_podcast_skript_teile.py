"""Prüft die Skriptaufgabe: erst ein Plan mit Stellen, dann jeder Teil aus seinem Original."""

import json

from src.features.podcast.schemas import Person, PodcastParams
from src.services import json_llm
from src.services import text_map as tm
from src.services.source_reading import Piece, Source
from src.tasks.podcast_tasks import _script


def _params(length="long"):
    personen = [Person(name="Ana", role="host", voice_id="v0"),
                Person(name="Ben", role="expert", voice_id="v1")]
    return PodcastParams(language="de", persons=personen, length=length)


def _karte():
    text = "".join(f"Satz {i} ueber das Thema. " for i in range(40))
    schritt = len(text) // 8
    stuecke = [Piece(seite=1 + i // 2, von=i * schritt, bis=(i + 1) * schritt) for i in range(8)]
    return tm.Karte([Source(dateiname="a.pdf", fassung="x", text=text, seiten=4, stuecke=stuecke)])


def _zeilen(n, start=0):
    return json.dumps({"lines": [{"speaker": (start + i) % 2, "text": f"Beitrag {start + i}"}
                                 for i in range(n)]})


class _Llm:
    def __init__(self, antworten):
        self.antworten = list(antworten)
        self.gesendet = []

    def __call__(self, llm, nachrichten, endpoint="tool"):
        self.gesendet.append(nachrichten)
        inhalt = self.antworten.pop(0)
        return type("R", (), {"choices": [type("C", (), {
            "message": type("M", (), {"content": inhalt})()})()]})()


def _lauf(monkeypatch, antworten, params):
    fake = _Llm(antworten)
    monkeypatch.setattr(json_llm, "call_json_llm", fake)
    monkeypatch.setattr(_script, "assert_not_cancelled", lambda job: None)
    fortschritt = []
    monkeypatch.setattr(_script.db, "update_job_status",
                        lambda job, status, progress=None, error_message=None: fortschritt.append(progress))
    karte = _karte()
    g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    zeilen = _script._schreiben(object(), karte, g, params, "j" * 32)
    return zeilen, fake, fortschritt


def test_eine_lange_folge_wird_in_drei_teilen_geschrieben(monkeypatch):
    plan = json.dumps({"parts": [{"title": t, "gist": "g", "refs": r}
                                 for t, r in (("A", [1, 2]), ("B", ["4-5"]), ("C", [8]))]})
    zeilen, fake, fortschritt = _lauf(
        monkeypatch, [plan, _zeilen(14), _zeilen(13, 14), _zeilen(13, 27)], _params())
    assert len(zeilen) == 40
    assert len(fake.gesendet) == 4
    assert [f["part"] for f in fortschritt] == [0, 1, 2]


def test_jeder_teil_bekommt_seine_stellen_aus_dem_original(monkeypatch):
    plan = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]},
                                 {"title": "B", "gist": "g", "refs": [8]}]})
    _, fake, _ = _lauf(monkeypatch, [plan, _zeilen(10), _zeilen(10, 10)], _params("medium"))
    erster, zweiter = fake.gesendet[1][1]["content"], fake.gesendet[2][1]["content"]
    assert "Satz 0 " in erster and "Satz 39" not in erster
    assert "Satz 39" in zweiter and "Satz 0 " not in zweiter


def test_was_der_plan_nicht_nennt_geht_an_den_naechsten_teil(monkeypatch):
    """Stelle 1 und 8 genannt, die sechs dazwischen verteilen sich auf beide Teile."""
    plan = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]},
                                 {"title": "B", "gist": "g", "refs": [8]}]})
    _, fake, _ = _lauf(monkeypatch, [plan, _zeilen(10), _zeilen(10, 10)], _params("medium"))
    beide = fake.gesendet[1][1]["content"] + fake.gesendet[2][1]["content"]
    assert all(f"Satz {i} " in beide for i in range(40))


def test_ein_spaeterer_teil_sieht_das_zuletzt_gesagte(monkeypatch):
    plan = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]},
                                 {"title": "B", "gist": "g", "refs": [8]}]})
    _, fake, _ = _lauf(monkeypatch, [plan, _zeilen(10), _zeilen(10, 10)], _params("medium"))
    zweiter = fake.gesendet[2][1]["content"]
    assert "Ben: Beitrag 9" in zweiter and "Beitrag 5" not in zweiter


def test_ein_unbrauchbarer_plan_wird_einmal_wiederholt(monkeypatch):
    plan = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]}]})
    zeilen, fake, _ = _lauf(monkeypatch, ["kein json", plan, _zeilen(10)], _params("short"))
    assert len(zeilen) == 10 and len(fake.gesendet) == 3


def _zwei_dateien():
    text = "Erster Text ueber Gleichbehandlung. " * 10
    stuecke = [Piece(seite=1, von=0, bis=len(text))]
    return tm.Karte([Source(dateiname=n, fassung="x", text=text, seiten=1, stuecke=stuecke)
                     for n in ("agg.pdf", "amg.pdf")])


def test_ein_plan_ohne_eine_datei_wird_mit_hinweis_wiederholt(monkeypatch):
    nur_eine = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]}]})
    beide = json.dumps({"parts": [{"title": "A", "gist": "g", "refs": [1]},
                                  {"title": "B", "gist": "g", "refs": [2]}]})
    fake = _Llm([nur_eine, beide, _zeilen(10), _zeilen(10, 10)])
    monkeypatch.setattr(json_llm, "call_json_llm", fake)
    monkeypatch.setattr(_script, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_script.db, "update_job_status", lambda *a, **k: None)
    karte = _zwei_dateien()
    g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    zeilen = _script._schreiben(object(), karte, g, _params("medium"), "j" * 32)
    assert len(zeilen) == 20
    assert "far too little room" in fake.gesendet[1][1]["content"].casefold()
    assert "amg.pdf (50 % of the material)" in fake.gesendet[1][1]["content"]
    assert "amg.pdf" in fake.gesendet[3][1]["content"]
