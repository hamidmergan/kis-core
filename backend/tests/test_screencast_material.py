"""Extra material for the screencast scripts: stored per job, assigned per slide, read by the prompt."""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.services import sources as quellen
from src.services import text_map as tm
from src.services.screencast import material
from src.services.source_reading import from_text

UUID = "b" * 32
STOFF = ("Die Wasserfallmethode plant alle Phasen vorab. " * 20
         + "\n\n" + "Scrum arbeitet in Sprints von zwei Wochen. " * 20)


def _antwort(inhalt: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))])


def test_parse_nimmt_nur_gefragte_folien():
    karte = tm.Karte([from_text("a.txt", STOFF)])
    g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    roh = json.dumps({"slides": [{"slide": 1, "refs": [1]}, {"slide": 9, "refs": [1]}, {"slide": "x"}]})
    assert material.parse(roh, g, karte, {1, 2}) == {1: [1]}


def test_parse_rueckt_an_die_abgeschriebenen_anfangsworte():
    stoff = "Die Wasserfallmethode plant alle Phasen vorab. " * 60 + "\n\nKanban begrenzt die Arbeit, die gleichzeitig laeuft."
    karte = tm.Karte([from_text("a.txt", stoff)])
    g = tm.Grundlage(material=karte.block(), modus=tm.STELLEN, themen=[])
    roh = json.dumps({"slides": [{"slide": 1, "refs": ["SZ1"], "start": "Kanban begrenzt die Arbeit, die gleichzeitig laeuft"}]})
    assert len(karte) >= 3
    assert material.parse(roh, g, karte, {1}) == {1: [len(karte)]}


def test_ohne_material_keine_zuordnung(lokal):
    assert material.material_je_folie(1, UUID, ["Folie"], llm=object()) is None


def test_jede_folie_bekommt_ihre_stellen(lokal):
    quellen.save_sources(1, UUID, [from_text("skript.txt", STOFF)])
    karte = tm.Karte(quellen.load_sources(1, UUID))
    letzte = len(karte)
    gefragt = []

    def llm_antwort(llm, nachrichten, endpoint="tool"):
        gefragt.append(nachrichten)
        return _antwort(json.dumps({"slides": [{"slide": 1, "refs": [letzte]}, {"slide": 2, "refs": []}]}))

    with patch("src.services.json_llm.call_json_llm", llm_antwort), \
         patch.object(material, "_fenster", return_value=0):
        stoff = material.material_je_folie(1, UUID, ["Scrum", "Danke"], llm=object())

    assert len(gefragt) == 1
    assert "[Slide 1] Scrum" in gefragt[0][1]["content"]
    assert "Scrum" in stoff[0] and "[skript.txt, S. 1]" in stoff[0]
    assert stoff[1] == ""


def test_verwerfen_loescht_die_zuordnung(lokal):
    quellen.save_sources(1, UUID, [from_text("skript.txt", STOFF)])
    with patch("src.services.json_llm.call_json_llm",
               lambda *a, **k: _antwort('{"slides": [{"slide": 1, "refs": [1]}]}')), \
         patch.object(material, "_fenster", return_value=0):
        material.material_je_folie(1, UUID, ["Folie"], llm=object())
    material.verwerfen(1, UUID)
    assert material.read_job_text(1, UUID, material.FOLIEN_MATERIAL) is None


def test_trennzeichen_im_material_werden_entschaerft():
    assert "|||" not in material._sauber("a ||| b === c")
    assert "===" not in material._sauber("a ||| b === c")


class _Client:
    def __init__(self, antwort: str):
        self.gesendet = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._antwort = antwort

    def _create(self, **kwargs):
        self.gesendet.append(kwargs["messages"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self._antwort))],
                               usage=None)


def _llm(antwort: str):
    from src.services.openai_compat_llm import OpenAICompatLLMClient
    llm = OpenAICompatLLMClient.__new__(OpenAICompatLLMClient)
    llm._client = _Client(antwort)
    llm._model = "test"
    llm._batch_timeout = 10
    llm._extra_body = None
    return llm


def test_prompt_traegt_das_material_der_folie():
    llm = _llm("Skript eins\n|||\nSkript zwei")
    llm._generate_scripts_single_batch(
        ["Scrum", "Kanban"], 0, 1, False, False, None, False, False,
        batch_materials=["Sprints dauern zwei Wochen.", ""])
    system, nutzer = (m["content"] for m in llm._client.gesendet[0])
    assert "[MATERIAL]\nSprints dauern zwei Wochen.\n[END MATERIAL]" in nutzer
    assert nutzer.count("[MATERIAL]") == 1
    assert "neither on the slide nor in its material" in system


def test_prompt_ohne_material_bleibt_streng():
    llm = _llm("Skript eins")
    llm._generate_scripts_single_batch(["Scrum"], 0, 1, False, False, None, False, False)
    system, nutzer = (m["content"] for m in llm._client.gesendet[0])
    assert "[MATERIAL]" not in nutzer
    assert "Do NOT add any new information." in system


@pytest.fixture
def client(lokal):
    from src.app import app
    from src.dependencies import get_current_user
    from src.dependencies_rbac import get_user_permissions
    from src.permissions import resolve_user_permissions
    from src.security.auth import verify_auth

    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "email": "a@b.de", "role": "user"}
    app.dependency_overrides[get_user_permissions] = lambda: resolve_user_permissions("admin", None, True)
    jobs = {UUID: {"job_uuid": UUID, "user_id": 1}, "c" * 32: {"job_uuid": "c" * 32, "user_id": 2}}
    with patch("src.routes.screencast.einstellungen.get_job", jobs.get):
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_material_hochladen_lesen_entfernen(client):
    r = client.post(f"/screencast/{UUID}/material", data={"mode": "files"},
                    files=[("files", ("notizen.txt", STOFF.encode(), "text/plain"))])
    assert r.status_code == 200, r.text
    assert r.json() == {"files": ["notizen.txt"], "chars": len(quellen.load_sources(1, UUID)[0].text)}
    assert client.get(f"/screencast/{UUID}/material").json()["files"] == ["notizen.txt"]

    assert client.delete(f"/screencast/{UUID}/material").json() == {"files": [], "chars": 0}
    assert quellen.load_sources(1, UUID) == []


def test_hoechstens_zehn_dateien(client):
    dateien = [("files", (f"d{i}.txt", b"Inhalt der Datei.", "text/plain")) for i in range(11)]
    r = client.post(f"/screencast/{UUID}/material", data={"mode": "files"}, files=dateien)
    assert r.status_code == 422
    assert "10" in r.json()["detail"]


def test_zu_viel_material_wird_abgewiesen(client):
    with patch.object(quellen, "MAX_TOTAL_CHARS", 100):
        r = client.post(f"/screencast/{UUID}/material", data={"mode": "files"},
                        files=[("files", ("gross.txt", STOFF.encode(), "text/plain"))])
    assert r.status_code == 422
    assert "Zeichen" in r.json()["detail"] or "characters" in r.json()["detail"]


def test_fremder_auftrag_gibt_404(client):
    assert client.get(f"/screencast/{'c' * 32}/material").status_code == 404


def test_messen_zaehlt_eine_datei(client):
    r = client.post("/screencast/measure", files={"file": ("notizen.txt", STOFF.encode(), "text/plain")})
    assert r.status_code == 200
    assert r.json()["chars"] > 0


def test_skripte_bekommen_das_material(client):
    gesehen = {}

    async def erzeugen(texte, llm, **kwargs):
        gesehen.update(kwargs)
        return ["s"] * len(texte)

    @contextmanager
    def messe(*a, **k):
        yield {}

    with patch("src.routes.screencast.scripts.db.get_job", lambda u: {"user_id": 1}), \
         patch("src.routes.screencast.scripts.get_job_file", lambda *a: b"x"), \
         patch("src.routes.screencast.scripts.vertonung_verwerfen", lambda *a: None), \
         patch("src.routes.screencast.scripts.db.set_generating_scripts_flag", lambda *a: None), \
         patch("src.routes.screencast.scripts.messe", messe), \
         patch("src.routes.screencast.scripts.save_job_file", lambda *a: None), \
         patch("src.routes.screencast.scripts._merke_skriptsprache", lambda *a: None), \
         patch("src.routes.screencast.scripts.get_llm_client", lambda: object()), \
         patch("src.routes.screencast.scripts.generate_all_scripts", erzeugen), \
         patch("src.routes.screencast.scripts.zusatzmaterial.material_je_folie",
               lambda uid, uuid, texte: ["Stoff 1", ""]):
        r = client.post("/screencast/generate-scripts",
                        json={"slide_texts": ["A", "B"], "translate_job_uuid": UUID})
    assert r.status_code == 200, r.text
    assert gesehen["materials"] == ["Stoff 1", ""]


def test_schritt6_kennt_die_sprache_vom_start(client):
    from src.routes.screencast._shared import merke_skriptsprache
    merke_skriptsprache(1, UUID, "DE")
    assert client.get(f"/screencast/{UUID}/vertonungs-stand").json()["sprache"] == "DE"


def test_schritt6_faellt_auf_die_uebersetzungssprache_zurueck(client):
    from src.storage import save_job_file
    save_job_file(1, UUID, "queue_params.json", json.dumps({"target_lang": "EN-US"}).encode())
    assert client.get(f"/screencast/{UUID}/vertonungs-stand").json()["sprache"] == "EN-US"
