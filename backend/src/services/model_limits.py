"""Was ein Modell vertraegt: einmal messen, merken, danach nur noch rechnen.

Bis 2026-08-14 stand die Kontextgroesse als feste Zeichenzahl in zwei Admin-Feldern.
Das ging schief, sobald jemand ein Modell mit kleinerem Fenster eintrug: der Anbieter
lehnte die Anfrage mit HTTP 400 ab und der Chat zeigte einen Fehler. Gemessen an
16 Modellen reichen die Fenster von 20.080 bis 1.048.576 Token, ein einziger fester
Wert kann also gar nicht fuer alle stimmen.

Drei Dinge werden je Anbieter und Modell EINMAL gemessen und weggeschrieben:

* die Fenstergroesse in Token
* ob das Modell vor der Antwort denkt
* welcher Schalter dieses Denken abstellt

Warum ueberhaupt Schalter gemessen werden, obwohl Denken ueberall aus sein soll:
Manche Anbieter ignorieren unbekannte Felder stillschweigend (alle fuenf probierten Schalter kamen
mit HTTP 200 zurueck, nur zwei wirkten), andere Anbieter lehnen sie mit einem Fehler ab.
``reasoning_effort: "none"`` ist bei OpenAI kein gueltiger Wert. Beide Schalter blind
mitzuschicken zerlegt also genau die Anbieter, fuer die dieses Modul gedacht ist.
Erkannt wird deshalb an der WIRKUNG, nicht am Fehler.

Verraet ein Anbieter seine Grenze nicht (zwei der 16 gemessenen Modelle tun das nicht), bleibt
das Fenster ``unbekannt`` und es wird KEINE Zahl erfunden: dann deckelt nichts und allein die
Einstellung im Admin entscheidet. Trifft spaeter eine echte Absage ein, liest
:func:`learn_from_error` die Zahl heraus und traegt sie als ``gelernt`` nach.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger


# ── Stellschrauben ──────────────────────────────────────────────────────────

# Verraet ein Anbieter sein Fenster nicht, wird KEINE Zahl erfunden: 0 heisst
# unbekannt, und dann entscheidet allein die Einstellung im Admin.
UNBEKANNTES_FENSTER = 0

# Gemessen wurden 3,3 (dichter KIS-Kontext mit Seitenmarken und Kennungen) bis 6,2
# (deutscher Fliesstext) Zeichen je Token. Gerechnet wird mit dem dichten Fall, sonst
# passt der Kontext im schlechtesten Fall nicht mehr ins Fenster.
CHARS_PER_TOKEN = 3.0

# Anteil des Fensters, der an den abgerufenen Kontext geht. Der Rest traegt System-
# anweisung, Frage, Gespraechsverlauf und die Antwort selbst.
CHAT_SHARE = 0.60
# Ein Werkzeug packt ein ganzes Dokument in EINEN Aufruf, ohne Verlauf und ohne lange
# Antwort, und darf deshalb mehr vom Fenster belegen.
TOOL_SHARE = 0.75
# Eine gezielte Frage braucht nur die passenden Stellen, und zu viel Beiwerk laesst
# das Modell die Antwort uebersehen.
SPECIFIC_SHARE = 0.20


# Auch ein winziges Fenster muss noch eine Anfrage zulassen.
MIN_CONTEXT_CHARS = 2000

# Obergrenze fuer kurze Hilfsaufrufe (Absichtserkennung, Titel, Notizen, Urteile).
# Vorher standen dort 80 bis 300 Token. Gemessen an qwen3.6-35b-a3b kostet schon eine
# winzige JSON-Antwort 369 Token, sobald das Modell denkt: das Denken frisst den Platz
# auf und der Inhalt kommt LEER zurueck, was wie ein kaputtes Modell aussieht. Denken ist
# jetzt zwar abgeschaltet, aber nicht jedes Modell laesst sich abschalten. Die Grenze ist
# nur eine Obergrenze, ein Modell ohne Denken hoert vorher von selbst auf und zahlt nichts.
PRECALL_MAX_TOKENS = 1000

# Obergrenze fuer die Chat-Antwort, aus 5670 gemessenen Antworten gewaehlt: p99 liegt bei
# 2.870 Token, oberhalb von 8192 lag genau eine und die war eine Wiederholungsschleife.
CHAT_MAX_OUTPUT_TOKENS = 8192

# Merkmale, die ueber /chat/completions laufen und deshalb vermessbar sind. Eine
# Einbettungs- oder Whisper-Route kennt gar keine Chat-Anfrage.
CHAT_LIKE_FEATURES = frozenset({"chat", "vision", "ocr", "doc_translate", "transcript_translate"})

QUELLE_GEMESSEN = "gemessen"
QUELLE_UNBEKANNT = "unbekannt"
QUELLE_GELERNT = "gelernt"

# Die Sonde: eine absichtlich unmoegliche Anfrage. Der Anbieter lehnt sie ab, bevor er
# rechnet, und nennt dabei sein Fenster. Kostet kein Token und keine Rechenzeit.
_PROBE_MAX_TOKENS = 99_999_999
_PROBE_FRAGE = "Antworte nur mit: ok"
# Platz genug, dass ein denkendes Modell sein Denken auch wirklich zeigt. Mit 300 Token
# frisst das Denken den Platz auf und die Antwort kommt leer zurueck, was frueher wie
# ein kaputtes Modell aussah.
_PROBE_ANTWORT_TOKENS = 400

# Die Schalter, die Denken abstellen, in der Reihenfolge, in der sie probiert werden.
THINK_OFF_SWITCHES: dict[str, dict] = {
    # vLLM / Qwen / GLM: geht ueber die Chat-Vorlage
    "chat_template_kwargs": {"chat_template_kwargs": {"enable_thinking": False}},
    # OpenAI-naher Wortlaut, den viele Anbieter ebenfalls verstehen
    "reasoning_effort_none": {"reasoning_effort": "none"},
}
_SWITCH_ORDER = ("chat_template_kwargs", "reasoning_effort_none")


@dataclass
class ModelProfile:
    """Was ueber ein Modell bekannt ist. ``think_off`` ist leer, wenn das Modell
    nicht denkt oder sich sein Denken nicht abstellen laesst."""

    window_tokens: int
    source: str
    thinks: bool
    think_off: str

    @property
    def measured(self) -> bool:
        return self.window_tokens > 0 and self.source != QUELLE_UNBEKANNT


# ── Fenstergroesse aus einer Absage lesen ───────────────────────────────────

# Nur Muster, die das FENSTER nennen. Die Groesse der abgelehnten Anfrage steht in
# derselben Meldung und darf auf keinen Fall mitgelesen werden, sonst merkt sich KIS
# genau den Wert, an dem es gerade gescheitert ist.
_WINDOW_PATTERNS = (
    r"max_model_len=max_total_tokens=(\d+)",
    r"max_model_len=(\d+)",
    r"maximum context length is (\d+)",
    r"context length of (\d+)",
    r"context window of (\d+)",
)


def parse_window(text: str | None) -> int | None:
    """Die Fenstergroesse in Token aus einer Anbieter-Absage, oder ``None``.

    Nennt eine Meldung mehrere Zahlen, gilt die kleinste. Wer die groessere nimmt,
    baut sich denselben Fehler wieder ein.
    """
    if not text:
        return None
    treffer: list[int] = []
    for muster in _WINDOW_PATTERNS:
        treffer += [int(m) for m in re.findall(muster, str(text))]
    sinnvoll = [t for t in treffer if t > 0]
    return min(sinnvoll) if sinnvoll else None


# ── Token in Zeichen ────────────────────────────────────────────────────────

def context_chars(window_tokens: int, share: float) -> int:
    """Zeichenbudget fuer ein Fenster dieser Groesse.

    Bewusst vorsichtig gerechnet (siehe :data:`CHARS_PER_TOKEN`) und nach unten
    begrenzt, damit auch ein winziges Fenster noch eine Anfrage zulaesst.
    """
    roh = int(max(0, window_tokens) * share * CHARS_PER_TOKEN)
    return max(MIN_CONTEXT_CHARS, roh)


def think_off_body(profile: ModelProfile | None) -> dict:
    """Die Zusatzangabe, die das Denken dieses Modells abstellt.

    Leer, wenn das Modell nicht denkt oder kein Schalter gewirkt hat. Etwas
    Wirkungsloses mitzuschicken bringt nichts und kostet bei strengen Anbietern
    die ganze Anfrage.
    """
    if profile is None or not profile.thinks or not profile.think_off:
        return {}
    return dict(THINK_OFF_SWITCHES.get(profile.think_off) or {})


# ── Messen ──────────────────────────────────────────────────────────────────

def measure_with(call) -> ModelProfile:
    """Ein Modell vermessen. ``call(**kwargs)`` schickt eine Chat-Anfrage.

    Drei winzige Aufrufe, zusammen billiger als eine einzige echte Chatanfrage:
    die Sonde fuer das Fenster, eine Miniaturfrage fuer das Denkverhalten, und nur
    bei einem Denker je eine Runde pro Schalter.
    """
    window, quelle = _measure_window(call)
    thinks = _measure_thinking(call)
    think_off = _measure_switch(call) if thinks else ""
    return ModelProfile(window_tokens=window, source=quelle, thinks=thinks, think_off=think_off)


def _measure_window(call) -> tuple[int, str]:
    """Fenstergroesse per Sonde, oder unbekannt. Geraten wird nie."""
    try:
        call(messages=[{"role": "user", "content": "hi"}], max_tokens=_PROBE_MAX_TOKENS)
    except Exception as e:  # noqa: BLE001 — die Absage IST das Messergebnis
        fenster = parse_window(str(e))
        if fenster:
            return fenster, QUELLE_GEMESSEN
        logger.debug("Sonde abgelehnt, aber ohne Zahl: {}", str(e)[:200])
    return UNBEKANNTES_FENSTER, QUELLE_UNBEKANNT


def _measure_thinking(call) -> bool:
    """Denkt das Modell vor der Antwort?"""
    try:
        antwort = call(
            messages=[{"role": "user", "content": _PROBE_FRAGE}],
            max_tokens=_PROBE_ANTWORT_TOKENS,
            temperature=0.0,
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("Denkprobe fehlgeschlagen, gilt als nicht denkend: {}", str(e)[:200])
        return False
    return _thought(antwort)


def _measure_switch(call) -> str:
    """Welcher Schalter das Denken abstellt, oder leer.

    Ein Schalter, den der Anbieter mit einem Fehler ablehnt, wird uebersprungen.
    Ein Schalter, den er stillschweigend ignoriert, faellt durch, weil weiter
    gedacht wird.
    """
    for name in _SWITCH_ORDER:
        try:
            antwort = call(
                messages=[{"role": "user", "content": _PROBE_FRAGE}],
                max_tokens=_PROBE_ANTWORT_TOKENS,
                temperature=0.0,
                extra_body=dict(THINK_OFF_SWITCHES[name]),
            )
        except Exception as e:  # noqa: BLE001 — abgelehnt heisst nur: naechster Schalter
            logger.debug("Schalter {} abgelehnt: {}", name, str(e)[:150])
            continue
        if not _thought(antwort):
            return name
    return ""


# Was in der Mitte einer gekuerzten Nachricht steht, damit das Modell die Luecke sieht
# und nicht so tut, als haette es das ganze Dokument gelesen.
_LUECKE = "\n\n[…]\n\n"


def fit_messages(messages: list[dict], budget_chars: int) -> list[dict]:
    """Nachrichten so kuerzen, dass sie zusammen unter ``budget_chars`` bleiben.

    Gekuerzt wird der laengsten Nachricht die MITTE, so lange bis es passt. Anfang und
    Ende einer Quellensammlung tragen die Antwort, die Mitte ist der billigste Verlust.
    Systemanweisung und Frage sind meist kurz und bleiben dadurch von selbst heil.

    Das Original bleibt unangetastet, damit ein misslungener zweiter Versuch nicht auch
    noch den ersten Stand zerstoert hat.
    """
    kopie = [dict(m) for m in messages or []]
    if not kopie:
        return kopie
    gesamt = sum(len(m.get("content") or "") for m in kopie)
    if gesamt <= budget_chars:
        return kopie

    # Jede Nachricht behaelt mindestens diesen Rest, sonst antwortet das Modell
    # quellenlos statt gar nicht.
    boden = 200
    while gesamt > budget_chars:
        index = max(range(len(kopie)), key=lambda i: len(kopie[i].get("content") or ""))
        inhalt = kopie[index].get("content") or ""
        zuviel = gesamt - budget_chars
        ziel = max(boden, len(inhalt) - zuviel)
        if ziel >= len(inhalt):
            break  # nichts mehr zu holen, alle sind auf dem Boden
        kopie[index]["content"] = _kuerze_mitte(inhalt, ziel)
        neu = sum(len(m.get("content") or "") for m in kopie)
        if neu >= gesamt:
            break
        gesamt = neu
    return kopie


def _kuerze_mitte(text: str, ziel: int) -> str:
    """``text`` auf etwa ``ziel`` Zeichen bringen, indem die Mitte herausfaellt."""
    if ziel >= len(text):
        return text
    nutzbar = max(0, ziel - len(_LUECKE))
    kopf = nutzbar // 2
    fuss = nutzbar - kopf
    if kopf <= 0:
        return text[:max(1, ziel)]
    return text[:kopf] + _LUECKE + (text[-fuss:] if fuss > 0 else "")


def measure_provider_model(base_url: str, api_key: str, model: str) -> ModelProfile:
    """Ein Modell an seinem Anbieter vermessen. Nur hier faellt Netzverkehr an."""
    import httpx
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key or "not-needed",
        base_url=base_url,
        # Kuerzer als im Betrieb: eine Messung haengt an einem Admin-Klick oder an der
        # ersten Nutzeranfrage, und ein lahmer Anbieter darf beides nicht minutenlang
        # aufhalten. Wer nicht rechtzeitig antwortet, gilt als unvermessen.
        timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
        max_retries=0,
    )

    def call(**kwargs):
        return client.chat.completions.create(model=model, **kwargs)

    return measure_with(call)


# ── Speicher davor ──────────────────────────────────────────────────────────

# Schlaegt eine Messung fehl (Anbieter offline, Schluessel falsch), wird sie nicht bei
# jeder Anfrage erneut versucht. Sonst zahlt jeder Nutzer die Zeitgrenze des toten
# Anbieters, und das bei jedem Klick.
_RETRY_AFTER_SEC = 300.0
_failed_at: dict[tuple[int, str], float] = {}


def stored_profile(provider_id: int, model: str) -> ModelProfile | None:
    """Die gemerkte Messung, oder ``None``. Fasst nie das Netz an."""
    if not provider_id or not model:
        return None
    from src import database as db
    try:
        row = db.get_model_limit(provider_id, model)
    except Exception as e:  # noqa: BLE001 — ohne Messung wird eben vorsichtig gerechnet
        logger.debug("Modellvermessung nicht lesbar: {}", e)
        return None
    if not row:
        return None
    return ModelProfile(
        window_tokens=row["window_tokens"],
        source=row["source"],
        thinks=row["thinks"],
        think_off=row["think_off"],
    )


def ensure_profile(provider: dict, model: str) -> ModelProfile:
    """Die Messung dieses Modells, notfalls jetzt nachgeholt und weggeschrieben.

    Ist bereits etwas gemerkt, kostet der Aufruf eine Zeile aus der Datenbank. Sonst
    wird einmal gemessen. Scheitert das Messen, bleibt das Fenster unbekannt und der
    naechste Versuch wartet ein paar Minuten.
    """
    provider_id = (provider or {}).get("id")
    fallback = ModelProfile(UNBEKANNTES_FENSTER, QUELLE_UNBEKANNT, False, "")
    if not provider_id or not model:
        return fallback

    gemerkt = stored_profile(provider_id, model)
    if gemerkt is not None:
        return gemerkt

    import time
    schluessel = (provider_id, model)
    letzter = _failed_at.get(schluessel)
    if letzter is not None and (time.monotonic() - letzter) < _RETRY_AFTER_SEC:
        return fallback

    try:
        profil = measure_provider_model(
            _with_v1(provider.get("base_url") or ""),
            provider.get("api_key") or "",
            model,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Modell {} bei {} nicht vermessbar: {}", model, provider.get("name"), e)
        _failed_at[schluessel] = time.monotonic()
        return fallback

    _failed_at.pop(schluessel, None)
    from src import database as db
    try:
        db.set_model_limit(
            provider_id, model,
            window_tokens=profil.window_tokens,
            source=profil.source,
            thinks=profil.thinks,
            think_off=profil.think_off,
        )
    except Exception as e:  # noqa: BLE001 — gemessen ist gemessen, auch ungespeichert
        logger.warning("Modellvermessung nicht speicherbar: {}", e)
    logger.info(
        "Modell {} vermessen: Fenster {} ({}), denkt={}, Schalter={!r}",
        model, profil.window_tokens, profil.source, profil.thinks, profil.think_off,
    )
    return profil


def remeasure(provider: dict, model: str) -> ModelProfile | None:
    """Neu vermessen und wegschreiben, auch wenn schon etwas gemerkt ist.

    Das ist der Weg aus dem Admin: wer ein Modell eintraegt oder den Testknopf drueckt,
    soll sofort sehen, was es kann. Gibt ``None`` zurueck, wenn nicht gemessen werden
    konnte, dann bleibt der alte Eintrag stehen statt durch einen Ratewert ersetzt zu
    werden.
    """
    provider_id = (provider or {}).get("id")
    if not provider_id or not model:
        return None
    try:
        profil = measure_provider_model(
            _with_v1(provider.get("base_url") or ""),
            provider.get("api_key") or "",
            model,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Modell {} nicht vermessbar: {}", model, e)
        return None

    _failed_at.pop((provider_id, model), None)
    from src import database as db
    try:
        db.set_model_limit(
            provider_id, model,
            window_tokens=profil.window_tokens,
            source=profil.source,
            thinks=profil.thinks,
            think_off=profil.think_off,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Modellvermessung nicht speicherbar: {}", e)
    logger.info(
        "Modell {} neu vermessen: Fenster {} ({}), denkt={}, Schalter={!r}",
        model, profil.window_tokens, profil.source, profil.thinks, profil.think_off,
    )
    return profil


def as_dict(profile: ModelProfile | None) -> dict | None:
    """Fuer die Oberflaeche: die Messung als schlichtes Wortverzeichnis."""
    if profile is None:
        return None
    bekannt = profile.measured
    return {
        "window_tokens": profile.window_tokens,
        "source": profile.source,
        "thinks": profile.thinks,
        "think_off": profile.think_off,
        "context_chars": context_chars(profile.window_tokens, CHAT_SHARE) if bekannt else None,
        "tool_context_chars": context_chars(profile.window_tokens, TOOL_SHARE) if bekannt else None,
    }


def learn_from_error(provider_id: int, model: str, error) -> int | None:
    """Aus einer echten Absage im Betrieb die Fenstergroesse lernen.

    Gibt die gelernte Zahl zurueck, wenn die Meldung eine nennt, sonst ``None``.
    Der Aufrufer kann daraufhin verkleinert nochmal senden, statt dem Nutzer einen
    Fehler zu zeigen.
    """
    fenster = parse_window(str(error))
    if not fenster or not provider_id or not model:
        return None
    from src import database as db
    try:
        db.shrink_model_window(provider_id, model, fenster)
    except Exception as e:  # noqa: BLE001
        logger.debug("Gelerntes Fenster nicht speicherbar: {}", e)
    logger.warning("Modell {} kann nur {} Token, ab jetzt gemerkt", model, fenster)
    return fenster


def profile_for_feature(feature: str = "chat") -> ModelProfile | None:
    """Was ueber das Modell dieses Merkmals bekannt ist, oder ``None``. Nie Netzverkehr.

    ``None`` heisst "nichts bekannt". Die Budgetrechnung darf keine Anfrage aufhalten,
    also ist eine unlesbare Route dasselbe wie ein unvermessenes Modell.
    """
    from src import database as db
    try:
        route = db.get_route(feature) or {}
        provider_id = route.get("provider_id")
        modelle = route.get("provider_models") or {}
        model = modelle.get(str(provider_id)) or route.get("model_name")
    except Exception as e:  # noqa: BLE001
        logger.debug("Route {} nicht lesbar: {}", feature, e)
        return None
    return stored_profile(provider_id, model)


def window_for_feature(feature: str = "chat") -> int:
    """Fenstergroesse des Modells, das dieses Merkmal bedient, oder 0 fuer unbekannt."""
    profil = profile_for_feature(feature)
    return profil.window_tokens if profil else UNBEKANNTES_FENSTER


def cap_for_model(budget_chars: int, share: float, feature: str = "chat") -> int:
    """Ein Admin-Budget auf das kuerzen, was das Modell nachweislich vertraegt.

    Die Zahl im Admin bleibt die Vorgabe. Dieser Deckel greift nur, wenn ueber das
    Modell wirklich etwas bekannt ist: gemessen, im Betrieb gelernt oder von Hand
    eingetragen. Schweigt der Anbieter, wird nichts erfunden und nichts gekuerzt.

    Warum es den Deckel ueberhaupt gibt: am 14.08.2026 am echten Modell geprueft,
    qwen3-omni kann 65.536 Token. Die im Admin stehenden 800.000 Zeichen fuer die
    Werkzeuge lehnt es mit HTTP 400 ab. Die Selbstheilung faengt das ab, aber sie
    repariert nur den einen Aufruf. Ohne diesen Deckel zahlt JEDER weitere Lauf
    denselben Fehlversuch, weil die Einstellung unveraendert dasteht.
    """
    profil = profile_for_feature(feature)
    if profil is None or not profil.measured:
        return budget_chars
    return min(budget_chars, context_chars(profil.window_tokens, share))


def _with_v1(base_url: str) -> str:
    """Manche Anbieter stehen mit ``/v1`` in der Datenbank, manche ohne."""
    url = (base_url or "").rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def _thought(antwort) -> bool:
    """Hat das Modell gedacht?

    Drei Wege, weil jeder Anbieter es anders nennt: ``reasoning``,
    ``reasoning_content`` (vLLM-Standard), oder ``<think>`` mitten im Text. Kommt gar
    kein Inhalt zurueck und der Platz ist aufgebraucht, hat das Denken ihn gefressen,
    was fuer uns dasselbe bedeutet.
    """
    try:
        wahl = antwort.choices[0]
        nachricht = wahl.message
    except (AttributeError, IndexError, TypeError):
        return False
    for feld in ("reasoning", "reasoning_content"):
        if (getattr(nachricht, feld, None) or "").strip():
            return True
    inhalt = getattr(nachricht, "content", None)
    if inhalt and "<think>" in inhalt:
        return True
    return not inhalt and getattr(wahl, "finish_reason", "") == "length"
