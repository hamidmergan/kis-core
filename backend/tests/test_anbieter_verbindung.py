"""Jeder Aufruf an einen Anbieter nimmt einen Platz und geht an den Rückfall, wenn die Erste Wahl nicht antwortet."""

import asyncio
import json

import httpx
import pytest

from src.services import provider_slots, provider_transport as pt


class _Redis:
    """Genug Redis für Plätze und Sperrvermerke, mit einer einstellbaren Uhr."""

    def __init__(self, uhr):
        self.uhr = uhr
        self.sets: dict[str, dict[str, float]] = {}
        self.keys: dict[str, float] = {}

    def zremrangebyscore(self, key, lo, hi):
        s = self.sets.setdefault(key, {})
        for k in [k for k, v in s.items() if v <= hi]:
            del s[k]

    def zcard(self, key):
        return len(self.sets.get(key, {}))

    def zadd(self, key, mapping, nx=False, xx=False):
        s = self.sets.setdefault(key, {})
        for k, v in mapping.items():
            if not ((nx and k in s) or (xx and k not in s)):
                s[k] = v

    def zrem(self, key, *members):
        for m in members:
            self.sets.get(key, {}).pop(m, None)

    def zrank(self, key, member):
        s = self.sets.get(key, {})
        return sorted(s, key=lambda k: (s[k], k)).index(member) if member in s else None

    def zrangebyscore(self, key, lo, hi):
        return [k for k, v in self.sets.get(key, {}).items() if v <= hi]

    def set(self, key, value, ex=None):
        self.keys[key] = self.uhr["t"] + (ex or 0)

    def exists(self, key):
        return int(self.keys.get(key, 0) > self.uhr["t"])

    def ttl(self, key):
        return self.keys[key] - self.uhr["t"]


@pytest.fixture
def uhr(monkeypatch):
    stand = {"t": 1000.0}
    monkeypatch.setattr(provider_slots.time, "time", lambda: stand["t"])
    monkeypatch.setattr(provider_slots.time, "sleep", lambda s: stand.__setitem__("t", stand["t"] + s))
    monkeypatch.setattr(pt.time, "time", lambda: stand["t"])
    return stand


@pytest.fixture
def redis(uhr, monkeypatch):
    r = _Redis(uhr)
    monkeypatch.setattr(pt, "_redis", lambda: r)
    monkeypatch.setattr(provider_slots, "_redis", lambda: r)
    return r


def _ziel(pid, root, model, caps=None, key="k"):
    return pt.Target(provider_id=pid, name=f"p{pid}", root=root, api_key=f"{key}{pid}", model=model,
                     caps=caps or {})


ERSTE = _ziel(1, "https://hpc.example", "gemma-hpc")
RUECK = _ziel(2, "https://mylab.example", "chat-fast")


DRITTE = _ziel(3, "https://gwdg.example", "gemma-gwdg")


def _client(handler, primary=ERSTE, fallback=RUECK, bucket="llm", extras=()):
    inner = httpx.MockTransport(handler)
    return httpx.Client(transport=pt.ProviderTransport(primary, fallback, bucket, extras=extras, inner=inner))


def _chat(client, text="Hallo"):
    return client.post(f"{client._transport._door.primary.root}/v1/chat/completions",
                       json={"model": ERSTE.model, "messages": [{"role": "user", "content": text}]},
                       headers={"Authorization": f"Bearer {ERSTE.api_key}"})


def test_die_erste_wahl_antwortet_und_niemand_sonst_wird_gefragt(redis):
    gesehen = []

    def handler(req):
        gesehen.append(str(req.url))
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).status_code == 200
    assert gesehen == ["https://hpc.example/v1/chat/completions"]


def test_nicht_erreichbar_geht_derselbe_aufruf_an_den_rueckfall(redis):
    gesehen = []

    def handler(req):
        gesehen.append(req)
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("Connection refused", request=req)
        return httpx.Response(200, json={"ok": 1})

    antwort = _chat(_client(handler), "Frage an Francis")
    assert antwort.json() == {"ok": 1}
    rueck = gesehen[-1]
    assert str(rueck.url) == "https://mylab.example/v1/chat/completions"
    assert rueck.headers["authorization"] == "Bearer k2"
    koerper = json.loads(rueck.content)
    assert koerper["model"] == "chat-fast"
    assert koerper["messages"][0]["content"] == "Frage an Francis"


def test_ablehnung_wegen_grenze_sperrt_die_erste_wahl_bis_zum_ende_der_sperre(redis):
    def handler(req):
        if req.url.host == "hpc.example":
            return httpx.Response(429, headers={"ratelimit-reset": "50"}, json={"error": "limit"})
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).status_code == 200
    assert redis.exists("kis:provider-down:1:llm")
    assert redis.ttl("kis:provider-down:1:llm") == 50


def test_serverfehler_geht_an_den_rueckfall(redis):
    def handler(req):
        if req.url.host == "hpc.example":
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).status_code == 200


def test_ein_echter_fehler_der_anfrage_wechselt_nicht(redis):
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(400, json={"error": "zu lang"})

    assert _chat(_client(handler)).status_code == 400
    assert gesehen == ["hpc.example"]


def test_ohne_rueckfall_bleibt_alles_wie_heute(redis):
    def handler(req):
        raise httpx.ConnectError("Connection refused", request=req)

    with pytest.raises(httpx.ConnectError):
        _chat(_client(handler, fallback=None))


def test_eine_gesperrte_erste_wahl_wird_uebersprungen(redis):
    redis.set("kis:provider-down:1:llm", "x", ex=60)
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    _chat(_client(handler))
    assert gesehen == ["mylab.example"]


def test_nach_der_sperre_kommt_die_erste_wahl_wieder_dran(redis, uhr):
    redis.set("kis:provider-down:1:llm", "x", ex=60)
    uhr["t"] += 61
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    _chat(_client(handler))
    assert gesehen == ["hpc.example"]


def test_sind_beide_gesperrt_wird_trotzdem_zuerst_die_erste_wahl_gefragt(redis):
    redis.set("kis:provider-down:1:llm", "x", ex=60)
    redis.set("kis:provider-down:2:llm", "x", ex=60)
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    _chat(_client(handler))
    assert gesehen == ["hpc.example"]


def test_ein_gesperrter_rueckfall_bleibt_als_letzter_versuch_stehen(redis):
    """Lauf 15 Teil 2: myLab lief einmal in eine Lesezeit, danach fragten Aufrufe nur noch die tote Erste Wahl."""
    redis.set("kis:provider-down:2:llm", "ReadTimeout", ex=60)
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("Connection refused", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).json() == {"ok": 1}
    assert gesehen == ["hpc.example", "mylab.example"]


def test_ist_auch_der_rueckfall_tot_fragt_die_tuer_den_naechsten_aus_der_liste(redis):
    """Nutzerentscheid 29.09.2026: danach kommt jeder weitere Anbieter, dem der Admin ein Modell gegeben hat."""
    gesehen = []

    def handler(req):
        gesehen.append(req)
        if req.url.host != "gwdg.example":
            raise httpx.ConnectError("Connection refused", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler, extras=[DRITTE])).json() == {"ok": 1}
    assert [r.url.host for r in gesehen] == ["hpc.example", "mylab.example", "gwdg.example"]
    assert gesehen[-1].headers["authorization"] == "Bearer k3"
    assert json.loads(gesehen[-1].content)["model"] == "gemma-gwdg"
    assert redis.exists("kis:provider-down:1:llm") and redis.exists("kis:provider-down:2:llm")


def test_sind_erste_wahl_und_rueckfall_gesperrt_kommt_der_naechste_zuerst_dran(redis):
    redis.set("kis:provider-down:1:llm", "x", ex=60)
    redis.set("kis:provider-down:2:llm", "x", ex=60)
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    _chat(_client(handler, extras=[DRITTE]))
    assert gesehen == ["gwdg.example"]


def test_eine_zu_langsame_antwort_sperrt_einen_anbieter_der_noch_antwortet_nicht(redis, monkeypatch):
    """Lauf 18: zwei langsame Antworten von gemma schickten je 60 s lang alle Aufrufe zu myLab, das dann überlief."""
    monkeypatch.setattr(pt, "_answers", lambda target: True)
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        if req.url.host == "hpc.example":
            raise httpx.ReadTimeout("zu langsam", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).json() == {"ok": 1}
    assert gesehen == ["hpc.example", "mylab.example"]
    assert not redis.exists("kis:provider-down:1:llm")


def test_eine_abgerissene_verbindung_sperrt_einen_anbieter_der_noch_antwortet_nicht(redis, monkeypatch):
    """Tag-Simulation 29.09.: eine alte Verbindung zu gemma riss ab, KIS schickte 60 s lang alles zu myLab."""
    monkeypatch.setattr(pt, "_answers", lambda target: True)

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).json() == {"ok": 1}
    assert not redis.exists("kis:provider-down:1:llm")


def test_eine_abgelehnte_verbindung_sperrt_ohne_probe(redis, monkeypatch):
    gefragt = []
    monkeypatch.setattr(pt, "_answers", lambda target: gefragt.append(target) or True)

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("Connection refused", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).json() == {"ok": 1}
    assert redis.exists("kis:provider-down:1:llm") and gefragt == []


def test_eine_zu_langsame_antwort_sperrt_einen_stummen_anbieter(redis, monkeypatch):
    monkeypatch.setattr(pt, "_answers", lambda target: False)

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.ReadTimeout("zu langsam", request=req)
        return httpx.Response(200, json={"ok": 1})

    assert _chat(_client(handler)).json() == {"ok": 1}
    assert redis.exists("kis:provider-down:1:llm")


def test_auch_asynchron_sperrt_eine_langsame_antwort_nur_einen_stummen_anbieter(redis, monkeypatch):
    monkeypatch.setattr(pt, "_answers", lambda target: True)

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.ReadTimeout("zu langsam", request=req)
        return httpx.Response(200, json={"ok": 1})

    async def los():
        tuer = pt.AsyncProviderTransport(ERSTE, RUECK, "llm", inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=tuer) as client:
            return await client.post(f"{ERSTE.root}/v1/chat/completions",
                                     json={"model": ERSTE.model, "messages": [{"role": "user", "content": "x"}]})

    assert asyncio.run(los()).json() == {"ok": 1}
    assert not redis.exists("kis:provider-down:1:llm")


def test_antworten_alle_nicht_kommt_der_fehler_des_letzten(redis):
    def handler(req):
        raise httpx.ConnectError(f"refused {req.url.host}", request=req)

    with pytest.raises(httpx.ConnectError, match="gwdg.example"):
        _chat(_client(handler, extras=[DRITTE]))


def test_spracherkennung_bekommt_beim_rueckfall_das_modell_des_rueckfalls(redis):
    gesehen = []

    def handler(req):
        gesehen.append(req)
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("refused", request=req)
        return httpx.Response(200, json={"text": "hallo"})

    client = _client(handler, primary=_ziel(1, "https://hpc.example", "whisper-hpc"),
                     fallback=_ziel(2, "https://mylab.example", "whisper-3-large"), bucket="stt")
    client.post("https://hpc.example/v1/audio/transcriptions",
                data={"model": "whisper-hpc", "language": "de"},
                files={"file": ("a.mp3", b"\x00\x01audio", "audio/mpeg")})
    koerper = gesehen[-1].content
    assert b'name="model"\r\n\r\nwhisper-3-large\r\n' in koerper
    assert b"whisper-hpc" not in koerper
    assert b"\x00\x01audio" in koerper


def test_fremde_adressen_laufen_ohne_platz_und_ohne_rueckfall_durch(redis):
    gesehen = []

    def handler(req):
        gesehen.append(str(req.url))
        return httpx.Response(200, content=b"png")

    voll = _ziel(1, "https://hpc.example", "flux", caps={"image": 1})
    client = _client(handler, primary=voll, bucket="image")
    redis.zadd("kis:provider-slots:1:image", {"besetzt": 1000.0})
    assert client.get("https://cdn.example/bild.png").content == b"png"
    assert gesehen == ["https://cdn.example/bild.png"]


def test_die_obergrenze_haelt_und_gibt_den_platz_nach_dem_lesen_zurueck(redis, monkeypatch):
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    eng = _ziel(1, "https://mylab.example", "chat-fast", caps={"llm": 1})
    # A real provider streams its answer, the seat is held until it has been read.
    client = _client(lambda req: httpx.Response(200, stream=httpx.ByteStream(b'{"ok": 1}')),
                     primary=eng, fallback=None)
    anfrage = client.build_request("POST", "https://mylab.example/v1/chat/completions",
                                   json={"model": "chat-fast", "messages": []})
    offen = client.send(anfrage, stream=True)
    with pytest.raises(provider_slots.ProviderFull):
        _chat(client)
    offen.read()
    offen.close()
    assert redis.zcard("kis:provider-slots:1:llm") == 0
    assert _chat(client).status_code == 200


def test_volle_bildplaetze_gehen_nicht_an_den_rueckfall(redis, monkeypatch):
    """Bilder laufen nie über: klein ist nach Sekunden frei, der Rückfall braucht eine halbe Minute."""
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:image", {"besetzt": 1000.0})
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    eng = _ziel(1, "https://hpc.example", "flux", caps={"image": 1})
    with pytest.raises(provider_slots.ProviderFull):
        _client(handler, primary=eng, fallback=_ziel(2, "https://mylab.example", "flux"), bucket="image").post(
            "https://hpc.example/v1/images/generations", json={"model": "flux", "prompt": "x"})
    assert gesehen == []


def _eng(pid=1):
    return _ziel(pid, "https://hpc.example", "gemma-hpc", caps={"llm": 1})


def test_ist_die_erste_wahl_voll_geht_ein_llm_aufruf_sofort_an_den_rueckfall(redis, monkeypatch):
    """Nutzerentscheid 29.09.2026: beim LLM teilen sich erste Wahl und Rückfall die Last, statt zu warten."""
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 60)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    rueck = _ziel(2, "https://mylab.example", "chat-fast", caps={"llm": 10})
    antwort = _chat(_client(handler, primary=_eng(), fallback=rueck))
    antwort.read()
    assert antwort.json() == {"ok": 1}
    assert gesehen == ["mylab.example"]
    assert redis.zcard("kis:provider-slots:2:llm") == 0, "der Platz beim Rückfall geht nach dem Lesen zurück"


def test_sind_beide_voll_wartet_der_aufruf_bei_der_ersten_wahl(redis, monkeypatch):
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    redis.zadd("kis:provider-slots:2:llm", {"besetzt": 1000.0})
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    rueck = _ziel(2, "https://mylab.example", "chat-fast", caps={"llm": 1})
    with pytest.raises(provider_slots.ProviderFull) as fehler:
        _chat(_client(handler, primary=_eng(), fallback=rueck))
    assert fehler.value.provider == "1:llm"
    assert gesehen == []


def test_der_ueberlauf_reicht_bis_zu_weiteren_anbietern_aus_der_liste_durch(redis, monkeypatch):
    """Nutzerentscheid 29.09.2026: sind erste Wahl und Rückfall voll, übernimmt der nächste freie aus der Liste."""
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 60)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    redis.zadd("kis:provider-slots:2:llm", {"besetzt": 1000.0})
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    rueck = _ziel(2, "https://mylab.example", "chat-fast", caps={"llm": 1})
    dritte = _ziel(3, "https://gwdg.example", "gemma-gwdg", caps={"llm": 4})
    assert _chat(_client(handler, primary=_eng(), fallback=rueck, extras=[dritte])).json() == {"ok": 1}
    assert gesehen == ["gwdg.example"]


def test_ein_gesperrter_rueckfall_nimmt_keinen_ueberlauf(redis, monkeypatch):
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    redis.set("kis:provider-down:2:llm", "x", ex=60)

    def handler(req):
        return httpx.Response(200, json={"ok": 1})

    with pytest.raises(provider_slots.ProviderFull):
        _chat(_client(handler, primary=_eng(), fallback=_ziel(2, "https://mylab.example", "chat-fast")))


def test_auch_asynchron_geht_ein_voller_llm_aufruf_an_den_rueckfall(redis, monkeypatch):
    # The test clock stands still while the loop sleeps, so no wait at all: only the overflow gets it through.
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    gesehen = []

    def handler(req):
        gesehen.append(req.url.host)
        return httpx.Response(200, json={"ok": 1})

    async def los():
        tuer = pt.AsyncProviderTransport(_eng(), _ziel(2, "https://mylab.example", "chat-fast", caps={"llm": 10}),
                                         "llm", inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=tuer) as client:
            return await client.post("https://hpc.example/v1/chat/completions",
                                     json={"model": "gemma-hpc", "messages": [{"role": "user", "content": "x"}]})

    assert asyncio.run(los()).json() == {"ok": 1}
    assert gesehen == ["mylab.example"]


def test_der_chat_von_francis_nimmt_keinen_platz(redis, monkeypatch):
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    eng = _ziel(1, "https://hpc.example", "gemma-hpc", caps={"llm": 1})
    client = _client(lambda req: httpx.Response(200, json={"ok": 1}), primary=eng)
    with pt.seat_exempt():
        assert _chat(client).status_code == 200


def test_viel_material_bekommt_nur_ein_fuenftel_der_plaetze(redis, monkeypatch):
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    eng = _ziel(1, "https://mylab.example", "chat-fast", caps={"llm": 10})
    client = _client(lambda req: httpx.Response(200, stream=httpx.ByteStream(b'{"ok": 1}')),
                     primary=eng, fallback=None)
    gross = "x" * 100_000
    offen = []
    for _ in range(2):
        anfrage = client.build_request("POST", "https://mylab.example/v1/chat/completions",
                                       json={"model": "chat-fast", "messages": [{"role": "user", "content": gross}]})
        offen.append(client.send(anfrage, stream=True))
    with pytest.raises(provider_slots.ProviderFull):
        _chat(client, gross)
    assert _chat(client, "kurz").status_code == 200
    for antwort in offen:
        antwort.close()


def test_auch_der_asynchrone_weg_faellt_zurueck(redis):
    async def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("refused", request=req)
        return httpx.Response(200, json={"ok": 1})

    async def lauf():
        transport = pt.AsyncProviderTransport(ERSTE, RUECK, "llm", inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=transport) as client:
            antwort = await client.post("https://hpc.example/v1/chat/completions",
                                        json={"model": ERSTE.model, "messages": []})
            return antwort.json()

    assert asyncio.run(lauf()) == {"ok": 1}


def test_die_verbindung_zur_ersten_wahl_gibt_nach_zehn_sekunden_auf(redis):
    """Ein HPC-Job in der Warteschlange soll den Aufruf nicht zwei Minuten aufhalten."""
    gesehen = []

    def handler(req):
        gesehen.append(req.extensions["timeout"]["connect"])
        return httpx.Response(200, json={"ok": 1})

    client = _client(handler)
    client.post("https://hpc.example/v1/chat/completions", json={"model": "x"}, timeout=120)
    assert gesehen == [10.0]


# ─── Welcher Rückfall gilt ─────────────────────────────────────────────────


@pytest.fixture
def anbieter(monkeypatch):
    stand = {
        "route": {"provider_id": 1, "fallback_provider_id": 2,
                  "provider_models": {"1": "gemma-hpc", "2": "chat-fast"}},
        "providers": {
            1: {"id": 1, "name": "HPC", "base_url": "https://hpc.example/v1", "enabled": True,
                "protocol": "openai_compat", "api_key": None},
            2: {"id": 2, "name": "myLab", "base_url": "https://mylab.example", "enabled": True,
                "protocol": "openai_compat", "api_key": "geheim", "concurrency": {"llm": 10}},
        },
    }
    from src import database as db
    monkeypatch.setattr(db, "get_route", lambda feature: stand["route"])
    monkeypatch.setattr(db, "get_provider", lambda pid: stand["providers"].get(pid))
    monkeypatch.setattr(db, "list_providers_with_capability", lambda cap: [
        p for p in stand["providers"].values() if p.get("enabled") and cap in p.get("capabilities", ["chat"])])
    return stand


GWDG = {"id": 3, "name": "GWDG", "base_url": "https://gwdg.example/v1", "enabled": True,
        "protocol": "openai_compat", "api_key": "g", "capabilities": ["chat"]}


def test_weitere_anbieter_kommen_aus_der_liste_im_adminbereich(anbieter):
    anbieter["providers"][3] = dict(GWDG)
    anbieter["route"]["provider_models"]["3"] = "gemma-gwdg"
    ziele = pt.further_targets("chat", skip={1, 2})
    assert [(z.provider_id, z.root, z.model, z.api_key) for z in ziele] == [
        (3, "https://gwdg.example", "gemma-gwdg", "g")]


@pytest.mark.parametrize("aenderung", [
    lambda s: s["route"]["provider_models"].pop("3"),
    lambda s: s["providers"][3].update(enabled=False),
    lambda s: s["providers"][3].update(protocol="deepl"),
    lambda s: s["providers"][3].update(capabilities=["tts"]),
])
def test_ein_unbrauchbarer_weiterer_anbieter_zaehlt_nicht(anbieter, aenderung):
    anbieter["providers"][3] = dict(GWDG)
    anbieter["route"]["provider_models"]["3"] = "gemma-gwdg"
    aenderung(anbieter)
    assert pt.further_targets("chat", skip={1, 2}) == []


def test_uebersetzen_nimmt_weitere_anbieter_mit_llm(anbieter):
    anbieter["providers"][3] = dict(GWDG)
    anbieter["route"]["provider_models"]["3"] = "gemma-gwdg"
    assert [z.provider_id for z in pt.further_targets("doc_translate", skip={1, 2})] == [3]


def test_weitere_einbettungen_nur_mit_demselben_modell(anbieter):
    for p in anbieter["providers"].values():
        p["capabilities"] = ["embedding"]
    anbieter["providers"][3] = {**GWDG, "capabilities": ["embedding"]}
    anbieter["providers"][4] = {**GWDG, "id": 4, "capabilities": ["embedding"]}
    anbieter["route"]["provider_models"].update({"3": "e5-large", "4": "bge-m3"})
    ziele = pt.further_targets("embedding", skip={1, 2}, primary_model="e5-large")
    assert [z.provider_id for z in ziele] == [3]


def test_stimmen_fragen_nie_weitere_anbieter(anbieter):
    anbieter["providers"][3] = {**GWDG, "capabilities": ["tts"]}
    anbieter["route"]["provider_models"]["3"] = "kokoro"
    assert pt.further_targets("tts", skip={1}) == []


def test_mit_rueckfall_stehen_die_weiteren_anbieter_hinter_ihm(anbieter):
    from src.services.feature_router import FeatureBinding

    anbieter["providers"][3] = dict(GWDG)
    anbieter["route"]["provider_models"]["3"] = "gemma-gwdg"
    tuer = pt.transport_for(FeatureBinding(feature="chat", provider=anbieter["providers"][1], model="gemma-hpc"))._door
    assert [t.provider_id for t in tuer.backups] == [2, 3]


def test_ohne_rueckfall_fragt_die_tuer_niemanden_sonst(anbieter):
    """Wer im Admin keinen Rückfall einträgt, will kein Umschalten, auch nicht zu weiteren Anbietern."""
    from src.services.feature_router import FeatureBinding

    anbieter["providers"][3] = dict(GWDG)
    anbieter["route"]["provider_models"]["3"] = "gemma-gwdg"
    anbieter["route"]["fallback_provider_id"] = None
    tuer = pt.transport_for(FeatureBinding(feature="chat", provider=anbieter["providers"][1], model="gemma-hpc"))._door
    assert tuer.backups == []


def test_der_rueckfall_kommt_aus_dem_adminbereich(anbieter):
    ziel = pt.fallback_target("chat", primary_id=1)
    assert (ziel.provider_id, ziel.root, ziel.model, ziel.api_key) == (2, "https://mylab.example", "chat-fast", "geheim")
    assert ziel.caps == {"llm": 10}


@pytest.mark.parametrize("aenderung", [
    lambda s: s["route"].update(fallback_provider_id=None),
    lambda s: s["route"].update(fallback_provider_id=1),
    lambda s: s["providers"][2].update(enabled=False),
    lambda s: s["providers"][2].update(protocol="deepl"),
    lambda s: s["route"]["provider_models"].pop("2"),
])
def test_ein_unbrauchbarer_rueckfall_zaehlt_als_keiner(anbieter, aenderung):
    aenderung(anbieter)
    assert pt.fallback_target("chat", primary_id=1) is None


def test_stimmen_fallen_nie_zurueck(anbieter):
    assert pt.fallback_target("tts", primary_id=1) is None


def test_eine_formularwahl_bekommt_den_rueckfall_aus_dem_adminbereich(anbieter):
    """Wählt jemand selbst einen Anbieter, kommt dieser zuerst und danach der Rückfall."""
    from src.services.feature_router import FeatureBinding

    gewaehlt = FeatureBinding(feature="chat", provider={**anbieter["providers"][1], "id": 3}, model="eigen")
    transport = pt.transport_for(gewaehlt)
    assert transport._door.primary.provider_id == 3
    assert transport._door.fallback.provider_id == 2


def test_das_sdk_merkt_vom_rueckfall_nichts(redis):
    """Der ganze Weg über den OpenAI-Client, wie ihn Dienste und Tools benutzen."""
    import httpx2
    from openai import DefaultHttpxClient, OpenAI

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx2.ConnectError("refused", request=req)
        daten = json.loads(req.content)
        return httpx2.Response(200, json={
            "id": "x", "object": "chat.completion", "created": 0, "model": daten["model"],
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "Paris"}}],
        })

    tuer = pt.SdkTransport(ERSTE, RUECK, "llm", inner=httpx2.MockTransport(handler))
    client = OpenAI(api_key="k1", base_url="https://hpc.example/v1", max_retries=0,
                    http_client=DefaultHttpxClient(transport=tuer))
    antwort = client.chat.completions.create(model="gemma-hpc", messages=[{"role": "user", "content": "?"}])
    assert antwort.choices[0].message.content == "Paris"
    assert antwort.model == "chat-fast"


def test_der_gestreamte_chat_faellt_ueber_das_sdk_zurueck(redis):
    import httpx2
    from openai import AsyncOpenAI, DefaultAsyncHttpxClient

    stueck = ('data: {"id":"x","object":"chat.completion.chunk","created":0,"model":"chat-fast",'
              '"choices":[{"index":0,"delta":{"content":"Paris"},"finish_reason":null}]}\n\ndata: [DONE]\n\n')

    async def handler(req):
        if req.url.host == "hpc.example":
            raise httpx2.ConnectError("refused", request=req)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               stream=httpx2.ByteStream(stueck.encode()))

    async def lauf():
        tuer = pt.AsyncSdkTransport(ERSTE, RUECK, "llm", inner=httpx2.MockTransport(handler))
        client = AsyncOpenAI(api_key="k1", base_url="https://hpc.example/v1", max_retries=0,
                             http_client=DefaultAsyncHttpxClient(transport=tuer))
        strom = await client.chat.completions.create(model="gemma-hpc", stream=True,
                                                     messages=[{"role": "user", "content": "?"}])
        return "".join([c.choices[0].delta.content async for c in strom if c.choices])

    assert asyncio.run(lauf()) == "Paris"


def test_die_spracherkennung_faellt_ueber_das_sdk_mit_dem_eigenen_modell_zurueck(redis):
    import httpx2
    from openai import DefaultHttpxClient, OpenAI

    gesehen = []

    def handler(req):
        gesehen.append(req.read())
        if req.url.host == "hpc.example":
            raise httpx2.ConnectError("refused", request=req)
        return httpx2.Response(200, json={"text": "hallo"})

    tuer = pt.SdkTransport(_ziel(1, "https://hpc.example", "whisper-hpc"),
                           _ziel(2, "https://mylab.example", "whisper-3-large"), "stt",
                           inner=httpx2.MockTransport(handler))
    client = OpenAI(api_key="k1", base_url="https://hpc.example/v1", max_retries=0,
                    http_client=DefaultHttpxClient(transport=tuer))
    text = client.audio.transcriptions.create(model="whisper-hpc", file=("a.mp3", b"\x00audio", "audio/mpeg"))
    assert text.text == "hallo"
    assert b"whisper-3-large" in gesehen[-1] and b"whisper-hpc" not in gesehen[-1]


def test_volle_plaetze_meldet_das_sdk_nach_einmal_warten(redis, monkeypatch):
    """Die Bibliothek fragt sonst zweimal nach, ein Aufruf wartete dann 6 statt 2 Minuten."""
    import httpx2
    from openai import DefaultHttpxClient, OpenAI

    from src.services.upstream_errors import is_upstream_busy

    wartezeiten = []
    echt = provider_slots.claim_ranked

    def claim(*a, **k):
        wartezeiten.append(k["wait_seconds"])
        return echt(*a, **k)

    monkeypatch.setattr(provider_slots, "claim_ranked", claim)
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 0)
    redis.zadd("kis:provider-slots:1:llm", {"besetzt": 1000.0})
    eng = _ziel(1, "https://hpc.example", "gemma-hpc", caps={"llm": 1})
    tuer = pt.SdkTransport(eng, None, "llm", inner=httpx2.MockTransport(lambda req: httpx2.Response(200)))
    client = OpenAI(api_key="k1", base_url="https://hpc.example/v1", max_retries=2,
                    http_client=DefaultHttpxClient(transport=tuer))
    with pytest.raises(provider_slots.ProviderFull) as fehler:
        client.chat.completions.create(model="gemma-hpc", messages=[{"role": "user", "content": "?"}])
    assert len(wartezeiten) == 1
    assert is_upstream_busy(fehler.value)


# ─── Reihenfolge nach Art des Auftrags ────────────────────────────────────


@pytest.mark.parametrize("queue, priority, rank", [
    ("general", 0, 0),      # Übersetzung, Transkript, Bilder
    ("general", None, 0),
    ("general", 9, 2),      # Zusammenfassung, weitere Etappen, Wiederanläufe
    ("long", 9, 2),         # Gliederung, Podcast-Skript, große Übersetzungen
    ("aia", 0, 1),          # Tools
    ("aia_ingest", 0, 1),   # Einlesen von Quellen
    ("tts", 0, 1),
    ("screencast", 0, 1),
    (None, None, 0),        # der Webprozess, eine Person wartet im Browser
])
def test_die_stufe_folgt_der_schlange(queue, priority, rank):
    assert pt.seat_rank_for(queue, priority) == rank


def test_die_tuer_stellt_sich_mit_der_stufe_des_auftrags_an(redis, monkeypatch):
    gesehen = []

    def claim_ranked(key, **k):
        gesehen.append((key, k["rank"]))
        return "t"

    monkeypatch.setattr(provider_slots, "claim_ranked", claim_ranked)
    monkeypatch.setattr(pt, "_rank", 2)
    eng = _ziel(1, "https://mylab.example", "chat-fast", caps={"llm": 10})
    _chat(_client(lambda req: httpx.Response(200, json={"ok": 1}), primary=eng, fallback=None))
    assert gesehen == [("1:llm", 2)]


def test_der_arbeiter_setzt_die_stufe_vor_jedem_auftrag(monkeypatch):
    from src import celery_app as ca

    class _Req:
        delivery_info = {"routing_key": "long", "priority": 9}

    class _Task:
        request = _Req()

    monkeypatch.setattr(pt, "_rank", 0)
    ca.on_task_prerun(task=_Task())
    assert pt._rank == 2


@pytest.mark.parametrize("queue, wait", [
    ("aia", 270),           # Tools warten so lange wie ein Aufruf darf
    ("aia_ingest", None),
    ("general", None),
    ("long", None),
    (None, None),
])
def test_nur_die_tools_warten_laenger_auf_einen_platz(queue, wait):
    assert pt.seat_wait_for(queue) == wait


def test_die_tuer_wartet_so_lange_wie_der_auftrag_es_setzt(redis, monkeypatch):
    """Ein einziger Platz bei Ollama: ein Tool reihte sich nach 120 s neu ein, obwohl der Platz bald frei war."""
    gesehen = []

    def claim_ranked(key, **k):
        gesehen.append(k["wait_seconds"])
        return "t"

    monkeypatch.setattr(provider_slots, "claim_ranked", claim_ranked)
    monkeypatch.setattr(pt, "PROVIDER_SEAT_WAIT_SECONDS", 120)
    eng = _ziel(1, "https://mylab.example", "chat-fast", caps={"llm": 10})
    monkeypatch.setattr(pt, "_seat_wait", 270)
    _chat(_client(lambda req: httpx.Response(200, json={"ok": 1}), primary=eng, fallback=None))
    monkeypatch.setattr(pt, "_seat_wait", None)
    _chat(_client(lambda req: httpx.Response(200, json={"ok": 1}), primary=eng, fallback=None))
    assert gesehen == [270, 120]


def test_der_arbeiter_setzt_die_wartezeit_vor_jedem_auftrag(monkeypatch):
    from src import celery_app as ca

    class _Req:
        delivery_info = {"routing_key": "aia", "priority": 0}

    class _Task:
        request = _Req()

    monkeypatch.setattr(pt, "_seat_wait", None)
    ca.on_task_prerun(task=_Task())
    assert pt._seat_wait == 270
    _Req.delivery_info = {"routing_key": "general", "priority": 0}
    ca.on_task_prerun(task=_Task())
    assert pt._seat_wait is None


def test_ohne_rueckfall_wird_nichts_vermerkt(redis):
    """Ohne zweite Wahl hilft ein Sperrvermerk niemandem und die Zeile im Protokoll führt in die Irre."""
    def handler(req):
        raise httpx.ConnectTimeout("langsam", request=req)

    with pytest.raises(httpx.ConnectTimeout):
        _chat(_client(handler, fallback=None))
    assert not redis.exists("kis:provider-down:1:llm")


def test_eine_ausgefallene_stimme_hinterlaesst_einen_vermerk_fuer_den_naechsten_auftrag(redis):
    """Stimmen wechseln nie mitten im Auftrag, der nächste Auftrag soll aber gleich beim Rückfall starten."""
    def handler(req):
        raise httpx.ConnectError("refused", request=req)

    with pytest.raises(httpx.ConnectError):
        _chat(_client(handler, fallback=None, bucket="tts"))
    assert redis.exists("kis:provider-down:1:tts")
    assert pt.is_down(1, "tts")
    assert not pt.is_down(1, "llm")


def test_grosse_anfragen_gehen_in_kleinen_stuecken_hinaus(redis):
    """Lauf 15: ein Audiostück ging am Stück hinaus, die Schreibgrenze von 10 s galt dann für alles."""
    stuecke = []

    def handler(req):
        stuecke.extend(len(s) for s in req.stream)
        return httpx.Response(200, json={"text": "ok"})

    client = _client(handler, fallback=None, bucket="stt")
    client.post("https://hpc.example/v1/audio/transcriptions", content=b"x" * 1_000_000,
                headers={"content-type": "application/octet-stream"})
    assert sum(stuecke) == 1_000_000
    assert max(stuecke) <= 64 * 1024


def test_auch_der_rueckfall_geht_in_kleinen_stuecken_hinaus(redis):
    stuecke = []

    def handler(req):
        if req.url.host == "hpc.example":
            raise httpx.ConnectError("refused", request=req)
        stuecke.extend(len(s) for s in req.stream)
        return httpx.Response(200, json={"ok": 1})

    _chat(_client(handler), "y" * 300_000)
    assert max(stuecke) <= 64 * 1024 and sum(stuecke) > 300_000


# ─── Das Protokoll nennt, wer wirklich geantwortet hat ─────────────────────


def _protokoll():
    from loguru import logger

    zeilen: list[str] = []
    return zeilen, logger.add(lambda m: zeilen.append(str(m)), level="INFO")


def _erste_wahl_tot(req):
    if req.url.host == "hpc.example":
        raise httpx.ConnectError("refused", request=req)
    return httpx.Response(200, json={"ok": 1})


def test_das_protokoll_nennt_den_rueckfall_der_geantwortet_hat(redis):
    """Lauf 15: die Zeile des SDK nannte die Adresse der Ersten Wahl, auch wenn myLab geantwortet hatte."""
    from loguru import logger

    zeilen, sink = _protokoll()
    try:
        _chat(_client(_erste_wahl_tot))
    finally:
        logger.remove(sink)
    assert any("p2 hat für p1 geantwortet" in z for z in zeilen)


def test_auch_der_asynchrone_weg_nennt_den_rueckfall(redis):
    from loguru import logger

    async def handler(req):
        return _erste_wahl_tot(req)

    async def lauf():
        transport = pt.AsyncProviderTransport(ERSTE, RUECK, "llm", inner=httpx.MockTransport(handler))
        async with httpx.AsyncClient(transport=transport) as client:
            await client.post("https://hpc.example/v1/chat/completions", json={"model": ERSTE.model, "messages": []})

    zeilen, sink = _protokoll()
    try:
        asyncio.run(lauf())
    finally:
        logger.remove(sink)
    assert any("p2 hat für p1 geantwortet" in z for z in zeilen)


def test_antwortet_die_erste_wahl_bleibt_das_protokoll_still(redis):
    from loguru import logger

    zeilen, sink = _protokoll()
    try:
        _chat(_client(lambda req: httpx.Response(200, json={"ok": 1})))
    finally:
        logger.remove(sink)
    assert not any("geantwortet" in z for z in zeilen)
