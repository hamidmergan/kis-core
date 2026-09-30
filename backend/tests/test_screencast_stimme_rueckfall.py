"""Die Vertonung eines Screencasts legt Anbieter und Stimme einmal beim ersten Lauf fest.

Nutzerentscheid 27.09.2026: ist der gewaehlte Anbieter beim Start nicht da, spricht der ganze Lauf mit dem
Rueckfall aus dem Adminbereich. Etappen, Wiederanlauf und Wiederholen behalten die Festlegung, erst ein neuer
Lauf entscheidet neu. Ton einer anderen Stimme kommt nie in dasselbe Video.
"""

import inspect
import json
import threading
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import redis

from src.core.db import pool

from src.services import tts_job_provider as tjp
from src.services.tts_job_provider import VoicePick
from src.tasks._stage import StageContinue
from src.tasks.screencast_tasks import _pipeline, _render, _shared
from src.tasks.screencast_tasks._render import run_screencast_render

UUID = "e" * 32
PIN = {"provider_id": 21, "voice_id": "nova", "voice_label": "Nova", "fallback": True,
       "requested_provider_id": 30, "requested_voice_id": "anna", "lauf": "lauf-1"}
_WARTESCHLANGE = {"dispatch_as": "render", "voice_id": "anna", "provider_id": 30, "voice_label": "Anna",
                  "speed": 0.9, "slide_pause": 1.0, "dpi": 96, "is_admin": False}


@pytest.fixture(autouse=True)
def ohne_datenbank_und_redis(monkeypatch):
    """Kein Test dieser Datei erreicht die echte Datenbank oder Redis."""
    erreicht: list[str] = []

    def keine_datenbank():
        erreicht.append("datenbank")
        raise RuntimeError("echte Datenbank")

    def kein_redis(*a, **k):
        erreicht.append("redis")
        raise RuntimeError("echtes Redis")

    monkeypatch.setattr(pool, "_get_pool", keine_datenbank)
    monkeypatch.setattr(redis, "from_url", kein_redis)
    yield
    # Ein Waechter-Faden der Strecke meldet sich erst nach dem Test.
    for faden in threading.enumerate():
        if faden.name.startswith("cancel-"):
            faden.join(2)
    assert erreicht == []


class _S3Fehler(Exception):
    """Ein Lesefehler des Speichers mit dem Code, den S3 mitschickt."""

    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


@pytest.fixture
def ablage(monkeypatch):
    """Der Auftragsordner im Speicher, geteilt von Aufgabe und Helfern."""
    dateien: dict[str, bytes] = {}

    def hole(user_id, job_uuid, name):
        if name not in dateien:
            raise FileNotFoundError(name)
        return dateien[name]

    def sichere(user_id, job_uuid, name, daten):
        dateien[name] = daten

    for modul in (_render, _shared):
        monkeypatch.setattr(modul, "get_job_file", hole, raising=False)
        monkeypatch.setattr(modul, "save_job_file", sichere, raising=False)
    return dateien


def _lies(ablage, name):
    return json.loads(ablage[name].decode())


@pytest.fixture
def auftrag(monkeypatch, ablage):
    """Die Render-Aufgabe ohne Datenbank und ohne echte Vertonung, der Anbieter 30 ist beim Start weg."""
    ablage["queue_params.json"] = json.dumps(_WARTESCHLANGE).encode()
    aufrufe: dict[str, list] = {"pipeline": [], "etappe": [], "gewaehlt": []}
    monkeypatch.setattr(_render, "still_mine", lambda j, v: True)
    monkeypatch.setattr(_render.db, "get_job", lambda j: {"user_id": 1, "creator_locale": "de"})
    monkeypatch.setattr(_render.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(_render, "_maybe_dispatch_next", lambda j: None)
    monkeypatch.setattr(_render, "continue_stage", lambda task, args, j: aufrufe["etappe"].append(list(args)))

    def pipeline(**kw):
        aufrufe["pipeline"].append(kw)
        raise StageContinue

    monkeypatch.setattr(_render, "_run_render_pipeline", pipeline)

    def waehle(provider_id, stimmen):
        aufrufe["gewaehlt"].append((provider_id, list(stimmen)))
        return VoicePick(21, ("nova",), True)

    monkeypatch.setattr(tjp, "pick", waehle)
    monkeypatch.setattr(tjp, "voice_name", lambda pid, vid: {"nova": "Nova"}.get(vid, vid))
    monkeypatch.setattr(_shared, "_lauf_kennung", lambda: "lauf-1", raising=False)
    return aufrufe


def _starte(provider_id=30, voice_id="anna", voice_label="Anna"):
    run_screencast_render.run(
        UUID, ["Eins.", "Zwei."], voice_id, 0.9, 1.0, "folien.pptx", 96,
        provider_id, voice_label, False, False, None, [], 0,
    )


def test_der_erste_lauf_spricht_ganz_mit_dem_rueckfall(auftrag):
    _starte()
    kw = auftrag["pipeline"][0]
    assert (kw["provider_id"], kw["voice_id"], kw["voice_label"]) == (21, "nova", "Nova")
    assert kw["tts_pin"] == PIN
    assert auftrag["gewaehlt"] == [(30, ["anna"])]


def test_die_festlegung_steht_in_den_warteschlangen_angaben(auftrag, ablage):
    """Wiederanlauf und Warteschlange lesen diese Datei, sie muessen die Festlegung finden."""
    _starte()
    params = _lies(ablage, "queue_params.json")
    assert params["tts_pin"] == PIN
    assert (params["provider_id"], params["voice_id"], params["voice_label"]) == (21, "nova", "Nova")
    assert params["dispatch_as"] == "render"
    assert params["speed"] == 0.9


def test_eine_gemerkte_festlegung_wird_nie_neu_entschieden(auftrag, ablage):
    """Wiederanlauf oder erneute Zustellung nach einem Absturz tragen noch die gewaehlte Stimme."""
    ablage["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "tts_pin": PIN}).encode()
    _starte()
    assert auftrag["gewaehlt"] == []
    kw = auftrag["pipeline"][0]
    assert (kw["provider_id"], kw["voice_id"], kw["voice_label"]) == (21, "nova", "Nova")


def test_ist_der_rueckfall_spaeter_weg_bleibt_es_trotzdem_bei_ihm(auftrag, ablage, monkeypatch):
    ablage["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "tts_pin": PIN}).encode()
    monkeypatch.setattr(tjp, "pick", lambda pid, stimmen: VoicePick(30, ("anna",), False))
    _starte(provider_id=21, voice_id="nova", voice_label="Nova")
    assert auftrag["pipeline"][0]["provider_id"] == 21


def test_die_naechste_etappe_spricht_mit_der_festgelegten_stimme(auftrag):
    _starte()
    args = auftrag["etappe"][0]
    felder = list(inspect.signature(run_screencast_render.run).parameters)
    assert args[felder.index("provider_id")] == 21
    assert args[felder.index("voice_id")] == "nova"
    assert args[felder.index("voice_label")] == "Nova"


def test_ist_der_gewaehlte_da_bleibt_alles_wie_gewaehlt(auftrag, ablage, monkeypatch):
    monkeypatch.setattr(tjp, "pick", lambda pid, stimmen: VoicePick(pid, tuple(stimmen), False))
    _starte()
    kw = auftrag["pipeline"][0]
    assert (kw["provider_id"], kw["voice_id"], kw["voice_label"]) == (30, "anna", "Anna")
    assert kw["tts_pin"]["fallback"] is False
    assert _lies(ablage, "queue_params.json")["tts_pin"]["provider_id"] == 30


def test_ein_lesefehler_der_warteschlangen_angaben_entscheidet_nicht_neu(auftrag, ablage, monkeypatch):
    """Nur eine fehlende Datei heisst ohne Festlegung, sonst spraeche derselbe Lauf mit einer anderen Stimme."""
    vorher = ablage["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "tts_pin": PIN}).encode()

    def hakt(user_id, job_uuid, name):
        raise _S3Fehler("SlowDown")

    monkeypatch.setattr(_shared, "get_job_file", hakt)
    with pytest.raises(_S3Fehler):
        _shared._stimme_festlegen(1, UUID, 30, "anna", "Anna")
    assert auftrag["gewaehlt"] == []
    assert ablage["queue_params.json"] == vorher


def test_eine_im_speicher_fehlende_datei_gilt_als_ohne_festlegung(auftrag, ablage, monkeypatch):
    del ablage["queue_params.json"]

    def fehlt(user_id, job_uuid, name):
        raise _S3Fehler("NoSuchKey")

    monkeypatch.setattr(_shared, "get_job_file", fehlt)
    assert _shared._stimme_festlegen(1, UUID, 30, "anna", "Anna") == PIN
    assert _lies(ablage, "queue_params.json")["tts_pin"] == PIN


def test_die_festlegung_ergaenzt_die_warteschlangen_angaben(auftrag, ablage):
    _shared._stimme_festlegen(1, UUID, 30, "anna", "Anna")
    params = _lies(ablage, "queue_params.json")
    assert params == {**_WARTESCHLANGE, "tts_pin": PIN, "provider_id": 21, "voice_id": "nova", "voice_label": "Nova"}


def test_der_vertonte_stand_nennt_die_wahl_der_person_und_die_gesprochene_stimme(auftrag, ablage, monkeypatch):
    """Schritt 6 vergleicht mit der Wahl der Person, die Strecke mit der Stimme, die wirklich gesprochen hat."""
    monkeypatch.setattr(_render, "_run_render_pipeline", lambda **kw: {"result_path": "x.mp4"})
    monkeypatch.setattr(_render, "load_result_meta", lambda u, j: {})
    monkeypatch.setattr(_render, "save_result_meta", lambda *a: None)
    monkeypatch.setattr(_render, "save_result_and_evict", lambda *a: None)
    monkeypatch.setattr(_render, "clear_render_cache", lambda *a: None)

    @contextmanager
    def ohne_takt(job_uuid):
        yield

    monkeypatch.setattr(_render, "job_heartbeat", ohne_takt)
    _starte()
    stand = _lies(ablage, "vertonter_stand.json")
    assert (stand["provider_id"], stand["voice_id"]) == (30, "anna")
    assert stand["tts_pin"] == PIN


def test_wiederholen_behaelt_die_festgelegte_stimme():
    from src.routes.jobs._retry import _queue_params_from_render

    params = _queue_params_from_render({
        "voice_id": "nova", "speed": 0.9, "slide_pause": 1.0, "dpi": 96,
        "provider_id": 21, "voice_label": "Nova", "tts_pin": PIN,
    })
    assert params["tts_pin"] == PIN
    assert (params["provider_id"], params["voice_id"], params["voice_label"]) == (21, "nova", "Nova")


def test_ein_alter_lauf_ohne_festlegung_entscheidet_beim_wiederholen_neu():
    from src.routes.jobs._retry import _queue_params_from_render

    params = _queue_params_from_render({"voice_id": "anna", "speed": 0.9, "slide_pause": 1.0, "dpi": 96})
    assert params.get("tts_pin") is None


# --- Der Wiederholen-Knopf setzt den laufenden Lauf fort ---

PIN_NEU = {"provider_id": 30, "voice_id": "anna", "voice_label": "Anna", "fallback": False,
           "requested_provider_id": 30, "requested_voice_id": "anna", "lauf": "lauf-2"}
_RENDER_ALT = {"voice_id": "nova", "speed": 0.9, "slide_pause": 1.0, "dpi": 96, "provider_id": 21,
               "voice_label": "Nova", "subtitles": False, "video_folien": [0, 1], "neu_vertonen": [0],
               "tts_pin": PIN}


@pytest.fixture
def wiederholen(monkeypatch):
    """Der Wiederholen-Knopf fuer einen Screencast ohne Datenbank und ohne Warteschlange."""
    from src.routes.jobs import _retry as route
    import src.tasks.screencast_tasks as sc

    dateien: dict[str, bytes] = {"render_scripts.json": b'["Eins.", "Zwei."]'}
    job = {"job_uuid": UUID, "user_id": 1, "tool": "screencast_translate", "status": "failed",
           "progress": "{}", "attempts": 2, "input_path": None, "original_filename": "a.pptx"}

    def lesen(user_id, job_uuid, name):
        if name not in dateien:
            raise FileNotFoundError(name)
        return dateien[name]

    monkeypatch.setattr(route, "get_job_file", lesen)
    monkeypatch.setattr(route, "save_job_file", lambda u, j, name, daten: dateien.__setitem__(name, daten))
    monkeypatch.setattr(route, "enforce_open_jobs", lambda *a: None)
    monkeypatch.setattr(route.db, "get_job", lambda j: job)
    monkeypatch.setattr(route.db, "transition_job_to_queued", lambda *a, **k: True)
    monkeypatch.setattr(route.db, "reset_attempts", lambda j: None)
    monkeypatch.setattr(sc, "dispatch_next_screencast_job_for_user", lambda uid: None)

    def lauf():
        assert route.retry_job(UUID, current_user={"user_id": 1}, locale="de") == {"ok": True}
        return _lies(dateien, "queue_params.json")

    return dateien, lauf


def test_wiederholen_ersetzt_die_festlegung_des_laufenden_laufs_nicht(wiederholen):
    """Die Render-Angaben stammen hier von einem frueheren Lauf mit dem Rueckfall."""
    dateien, lauf = wiederholen
    dateien["render_params.json"] = json.dumps(_RENDER_ALT).encode()
    dateien["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "speed": 1.2, "tts_pin": PIN_NEU}).encode()
    params = lauf()
    assert params["tts_pin"] == PIN_NEU
    assert (params["provider_id"], params["voice_id"], params["voice_label"]) == (30, "anna", "Anna")
    assert params["speed"] == 1.2


def test_wiederholen_desselben_laufs_nimmt_die_render_angaben(wiederholen):
    dateien, lauf = wiederholen
    dateien["render_params.json"] = json.dumps(_RENDER_ALT).encode()
    dateien["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "tts_pin": PIN}).encode()
    params = lauf()
    assert params["tts_pin"] == PIN
    assert params["neu_vertonen"] == [0]


def test_hat_der_neue_lauf_noch_keine_festlegung_gelten_seine_angaben(wiederholen):
    """Er scheiterte vor der Wahl der Stimme, die Render-Angaben mit Festlegung stammen von einem frueheren Lauf."""
    dateien, lauf = wiederholen
    dateien["render_params.json"] = json.dumps(_RENDER_ALT).encode()
    dateien["queue_params.json"] = json.dumps({**_WARTESCHLANGE, "speed": 1.2}).encode()
    params = lauf()
    assert params.get("tts_pin") is None
    assert (params["provider_id"], params["voice_id"], params["speed"]) == (30, "anna", 1.2)


def test_ein_frueherer_lauf_mit_derselben_stimme_liefert_nie_die_angaben(wiederholen):
    """Gleiche Stimme, gleicher Anbieter, aber ein anderer Lauf: Tempo und Folienauswahl gehoeren dem neuen."""
    dateien, lauf = wiederholen
    dateien["render_params.json"] = json.dumps(_RENDER_ALT).encode()
    dateien["queue_params.json"] = json.dumps(
        {**_WARTESCHLANGE, "speed": 1.2, "tts_pin": {**PIN, "lauf": "lauf-2"}}).encode()
    params = lauf()
    assert params["tts_pin"]["lauf"] == "lauf-2"
    assert params["speed"] == 1.2
    assert "neu_vertonen" not in params


def test_ein_alter_auftrag_ganz_ohne_festlegung_nimmt_die_render_angaben(wiederholen):
    """Von vor dem 28.09.2026: keine Seite kennt eine Festlegung, es bleibt wie vorher."""
    dateien, lauf = wiederholen
    ohne = {k: v for k, v in _RENDER_ALT.items() if k != "tts_pin"}
    dateien["render_params.json"] = json.dumps(ohne).encode()
    dateien["queue_params.json"] = json.dumps(_WARTESCHLANGE).encode()
    params = lauf()
    assert params["neu_vertonen"] == [0]
    assert (params["provider_id"], params["voice_id"]) == (21, "nova")


def test_jeder_lauf_bekommt_eine_eigene_kennung(ablage, monkeypatch):
    monkeypatch.setattr(tjp, "pick", lambda pid, stimmen: VoicePick(pid, tuple(stimmen), False))
    kennungen = []
    for _ in range(2):
        ablage["queue_params.json"] = json.dumps(_WARTESCHLANGE).encode()
        kennungen.append(_shared._stimme_festlegen(1, UUID, 30, "anna", "Anna")["lauf"])
    assert all(kennungen) and kennungen[0] != kennungen[1]


# --- Vorrat und alter Ton in der Render-Strecke ---


class _Halt(Exception):
    """Haelt die Strecke genau bei der Vertonung an."""


@pytest.fixture
def strecke(monkeypatch, tmp_path):
    """Die Render-Strecke bis zur Vertonung, alles andere ist ausgebaut."""
    dateien: dict[str, bytes] = {}
    geleert: list[str] = []
    gesehen: dict = {}

    def hole(user_id, job_uuid, name):
        if name not in dateien:
            raise FileNotFoundError(name)
        return dateien[name]

    async def sprechen(scripts, client, tmp, speed, voice_id, **kw):
        gesehen.update(kw, voice_id=voice_id)
        raise _Halt

    @contextmanager
    def messe(user_id, job_uuid, name):
        yield {}

    class _OhneWaechter:
        """Der Abbruch-Waechter fragt sonst das echte Redis."""

        def __init__(self, *a, **k):
            pass

        def start(self):
            pass

    helfer = (tmp_path, None, sprechen, None, None, None, None, None, None, None)
    monkeypatch.setattr(_pipeline, "threading", SimpleNamespace(Event=threading.Event, Thread=_OhneWaechter))
    monkeypatch.setattr(_pipeline, "_get_screencast_helpers", lambda: helfer)
    monkeypatch.setattr(_pipeline, "_get_tts_client", lambda pid, user_id=None: object())
    monkeypatch.setattr(_pipeline, "_assert_not_cancelled", lambda j: None)
    monkeypatch.setattr(_pipeline.db, "get_job", lambda j: {"user_id": 1})
    monkeypatch.setattr(_pipeline.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(_pipeline, "get_job_file", hole, raising=False)
    monkeypatch.setattr(_pipeline, "save_job_file", lambda u, j, name, daten: dateien.__setitem__(name, daten))
    monkeypatch.setattr(_pipeline, "clear_render_cache", lambda u, j: geleert.append(j), raising=False)
    monkeypatch.setattr(_pipeline, "audio_folien_mit_ton", lambda u, j: {0, 1})
    monkeypatch.setattr(_pipeline, "load_result_meta", lambda u, j: {})
    monkeypatch.setattr(_pipeline, "messe", messe)
    monkeypatch.setattr(_pipeline, "anbieter_und_modell", lambda pid, f: {})

    def lauf(**kw):
        angaben = {"voice_id": "nova", "provider_id": 21, "voice_label": "Nova", **kw}
        with pytest.raises(_Halt):
            _pipeline._run_render_pipeline(
                job_uuid=UUID, scripts=["Eins.", "Zwei."], speed=1.0, slide_pause=1.0,
                slide_images_override=[], **angaben,
            )

    return dateien, geleert, gesehen, lauf


def test_vorrat_einer_anderen_stimme_wird_vor_dem_sprechen_verworfen(strecke):
    dateien, geleert, _gesehen, lauf = strecke
    dateien["render_params.json"] = json.dumps({"provider_id": 30, "voice_id": "anna"}).encode()
    lauf()
    assert geleert == [UUID]


def test_vorrat_derselben_stimme_bleibt_fuer_die_naechste_etappe(strecke):
    dateien, geleert, _gesehen, lauf = strecke
    dateien["render_params.json"] = json.dumps({"provider_id": 21, "voice_id": "nova"}).encode()
    lauf()
    assert geleert == []


def test_ein_gewollter_stimmwechsel_laesst_nicht_angehakten_folien_ihre_alte_stimme(strecke):
    """So sagt es Schritt 6: Folien ohne Haken behalten die alte Stimme, die Person hat das gewaehlt."""
    dateien, _geleert, gesehen, lauf = strecke
    dateien["vertonter_stand.json"] = json.dumps({"provider_id": 30, "voice_id": "anna"}).encode()
    lauf(neu_vertonen=[])
    assert gesehen["alter_ton_erlaubt"] == {0, 1}


def test_spricht_jetzt_der_rueckfall_wird_der_alte_ton_der_wahl_ersetzt(strecke):
    """Sonst mischt ein Video die gewaehlte Stimme mit der Ersatzstimme, das hat niemand gewaehlt."""
    dateien, _geleert, gesehen, lauf = strecke
    dateien["vertonter_stand.json"] = json.dumps({"provider_id": 30, "voice_id": "anna"}).encode()
    lauf(neu_vertonen=[], tts_pin=PIN)
    assert gesehen["alter_ton_erlaubt"] == set()


def test_alter_ton_derselben_stimme_darf_bleiben(strecke):
    dateien, _geleert, gesehen, lauf = strecke
    dateien["vertonter_stand.json"] = json.dumps({"provider_id": 21, "voice_id": "nova"}).encode()
    lauf(neu_vertonen=[])
    assert gesehen["alter_ton_erlaubt"] == {0, 1}


def test_alter_ton_des_rueckfalls_bleibt_wenn_wieder_der_rueckfall_spricht(strecke):
    """Der Stand nennt die Wahl der Person, gesprochen hat laut Festlegung der Rueckfall."""
    dateien, _geleert, gesehen, lauf = strecke
    dateien["vertonter_stand.json"] = json.dumps({"provider_id": 30, "voice_id": "anna", "tts_pin": PIN}).encode()
    lauf(neu_vertonen=[])
    assert gesehen["alter_ton_erlaubt"] == {0, 1}


def test_ist_der_gewaehlte_wieder_da_wird_der_ton_des_rueckfalls_ersetzt(strecke):
    dateien, _geleert, gesehen, lauf = strecke
    dateien["vertonter_stand.json"] = json.dumps({"provider_id": 30, "voice_id": "anna", "tts_pin": PIN}).encode()
    lauf(neu_vertonen=[], provider_id=30, voice_id="anna", voice_label="Anna")
    assert gesehen["alter_ton_erlaubt"] == set()


def test_die_render_angaben_tragen_stimmname_und_festlegung(strecke):
    """Der Wiederholen-Knopf baut daraus den Auftrag neu."""
    dateien, _geleert, _gesehen, lauf = strecke
    lauf(tts_pin=PIN)
    params = json.loads(dateien["render_params.json"].decode())
    assert (params["provider_id"], params["voice_id"], params["voice_label"]) == (21, "nova", "Nova")
    assert params["tts_pin"] == PIN


def test_beim_stimmwechsel_verliert_eine_ausgelassene_folie_ihren_alten_ton(tmp_path):
    """Sonst holt ein spaeterer Lauf den Ton der alten Stimme zurueck ins Video."""
    from src.tasks.screencast_tasks._pipeline import _ton_fuer_ablage

    eins, drei = tmp_path / "a.mp3", tmp_path / "c.mp3"
    eins.write_bytes(b"ID3eins")
    drei.write_bytes(b"ID3drei")
    pfade = [eins, tmp_path / "b.mp3", drei]
    assert _ton_fuer_ablage(pfade, [True, False, True], alles_ersetzen=True) == [b"ID3eins", b"", b"ID3drei"]
    assert _ton_fuer_ablage(pfade, [True, False, True], alles_ersetzen=False) == [b"ID3eins", None, b"ID3drei"]


# --- Die Render-Route beginnt einen neuen Lauf ---


def test_neuer_lauf_vergleicht_den_vorrat_mit_der_wahl_der_person():
    """Der Rueckfall stammt nicht von der Person, die Strecke prueft den Vorrat danach selbst."""
    from src.routes.screencast.render import _vorrat_passt_nicht

    alt = json.dumps({**_WARTESCHLANGE, "voice_id": "nova", "provider_id": 21, "tts_pin": PIN}).encode()
    body = SimpleNamespace(voice_id="anna", provider_id=30, target_lang="DE")
    with patch("src.routes.screencast.render.get_job_file", return_value=alt), \
         patch("src.routes.screencast.render.load_result_meta", return_value={"target_lang": "DE"}):
        assert _vorrat_passt_nicht(1, UUID, body) is False


def test_ein_neuer_lauf_traegt_keine_alte_festlegung_mit():
    """Die Route schreibt die Warteschlangen-Angaben neu, die Aufgabe entscheidet dann neu."""
    from src.routes.screencast._models import RenderRequest
    from src.routes.screencast.render import screencast_render

    alt = json.dumps({**_WARTESCHLANGE, "voice_id": "nova", "provider_id": 21, "tts_pin": PIN}).encode()
    job = {"user_id": 1, "job_uuid": UUID, "status": "failed", "original_filename": "a.pptx"}
    body = RenderRequest(scripts=["eins"], translate_job_uuid=UUID, provider_id=30, voice_id="anna")
    modul = "src.routes.screencast.render"
    with patch(f"{modul}.max_screencast_slides", return_value=100), \
         patch(f"{modul}.enforce_open_jobs"), \
         patch(f"{modul}.db.get_job", return_value=job), \
         patch(f"{modul}.job_file_exists", return_value=True), \
         patch(f"{modul}.save_job_file") as sichern, \
         patch(f"{modul}.save_result_meta"), \
         patch(f"{modul}.load_result_meta", return_value={}), \
         patch(f"{modul}.get_job_file", return_value=alt), \
         patch(f"{modul}.clear_render_cache"), \
         patch(f"{modul}.db.transition_job_to_queued", return_value=True), \
         patch(f"{modul}.db.reset_attempts"), \
         patch("src.services.own_tts.access.check_voice_provider"), \
         patch("src.tasks.screencast_tasks.dispatch_next_screencast_job_for_user"):
        antwort = screencast_render(body, current_user={"user_id": 1, "email": "a@b.de", "role": "user"}, locale="de")
    assert antwort == {"job_uuid": UUID}
    params = next(json.loads(c[0][3].decode()) for c in sichern.call_args_list if c[0][2] == "queue_params.json")
    assert "tts_pin" not in params
    assert (params["provider_id"], params["voice_id"]) == (30, "anna")
