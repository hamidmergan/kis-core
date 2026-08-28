"""Measures once what a model can take, remembers it and only computes afterwards."""

from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger


# ── Stellschrauben ──────────────────────────────────────────────────────────

# Without a statement from the provider no number is invented, 0 means unknown.
UNBEKANNTES_FENSTER = 0

# Computed for the dense case, otherwise the context does not fit.
CHARS_PER_TOKEN = 3.0

# Share of the window that goes to the retrieved context.
CHAT_SHARE = 0.60
# A tool may take more of the window, it has no history.
TOOL_SHARE = 0.75
# A specific question only needs the matching spots.
SPECIFIC_SHARE = 0.20


# Even a tiny window must still allow one request.
MIN_CONTEXT_CHARS = 2000

# Obergrenze fuer kurze Hilfsaufrufe, denkende Modelle brauchen Platz.
PRECALL_MAX_TOKENS = 1000

# Ceiling for the chat answer, chosen from 5670 measured answers.
CHAT_MAX_OUTPUT_TOKENS = 8192

# Only features going through /chat/completions can be measured.
CHAT_LIKE_FEATURES = frozenset({"chat", "vision", "ocr", "doc_translate", "transcript_translate"})

QUELLE_GEMESSEN = "gemessen"
QUELLE_UNBEKANNT = "unbekannt"
QUELLE_GELERNT = "gelernt"

# The probe: an impossible request whose refusal names the window.
_PROBE_MAX_TOKENS = 99_999_999
_PROBE_FRAGE = "Antworte nur mit: ok"
# Room enough for a thinking model to show its thinking.
_PROBE_ANTWORT_TOKENS = 400
# Ein grosses Denk-Modell braucht auch fuer diese Winzprobe deutlich laenger als 30s.
_PROBE_READ_TIMEOUT = 120.0

# The switches that turn thinking off, in the order they are tried.
THINK_OFF_SWITCHES: dict[str, dict] = {
    # vLLM / Qwen / GLM: goes through the chat template
    "chat_template_kwargs": {"chat_template_kwargs": {"enable_thinking": False}},
    # OpenAI-style wording that many providers also understand
    "reasoning_effort_none": {"reasoning_effort": "none"},
}
_SWITCH_ORDER = ("chat_template_kwargs", "reasoning_effort_none")


@dataclass
class ModelProfile:
    """What is known about a model, think_off is empty when it does not think."""

    window_tokens: int
    source: str
    thinks: bool
    think_off: str

    @property
    def measured(self) -> bool:
        return self.window_tokens > 0 and self.source != QUELLE_UNBEKANNT


# ── Read the window size from a refusal ─────────────────────────────────────

# Only patterns naming the window, never the size of the rejected request.
_WINDOW_PATTERNS = (
    r"max_model_len=max_total_tokens=(\d+)",
    r"max_model_len=(\d+)",
    r"maximum context length is (\d+)",
    r"context length of (\d+)",
    r"context window of (\d+)",
)


def parse_window(text: str | None) -> int | None:
    """The window size from a provider refusal, the smallest of several numbers."""
    if not text:
        return None
    treffer: list[int] = []
    for muster in _WINDOW_PATTERNS:
        treffer += [int(m) for m in re.findall(muster, str(text))]
    sinnvoll = [t for t in treffer if t > 0]
    return min(sinnvoll) if sinnvoll else None


# ── Token in Zeichen ────────────────────────────────────────────────────────

def context_chars(window_tokens: int, share: float) -> int:
    """Character budget for a window of this size, computed conservatively."""
    roh = int(max(0, window_tokens) * share * CHARS_PER_TOKEN)
    return max(MIN_CONTEXT_CHARS, roh)


def think_off_body(profile: ModelProfile | None) -> dict:
    """The extra argument that turns off this model's thinking, empty otherwise."""
    if profile is None or not profile.thinks or not profile.think_off:
        return {}
    return dict(THINK_OFF_SWITCHES.get(profile.think_off) or {})


# ── Messen ──────────────────────────────────────────────────────────────────

def measure_with(call) -> ModelProfile:
    """Measures a model with three tiny calls."""
    window, quelle = _measure_window(call)
    thinks = _measure_thinking(call)
    think_off = _measure_switch(call) if thinks else ""
    return ModelProfile(window_tokens=window, source=quelle, thinks=thinks, think_off=think_off)


def _measure_window(call) -> tuple[int, str]:
    """Window size by probe, or unknown, it is never guessed."""
    try:
        call(messages=[{"role": "user", "content": "hi"}], max_tokens=_PROBE_MAX_TOKENS)
    except Exception as e:  # noqa: BLE001 — die Absage IST das Messergebnis
        fenster = parse_window(str(e))
        if fenster:
            return fenster, QUELLE_GEMESSEN
        logger.debug("Sonde abgelehnt, aber ohne Zahl: {}", str(e)[:200])
    return UNBEKANNTES_FENSTER, QUELLE_UNBEKANNT


def _measure_thinking(call) -> bool:
    """Does the model think before answering? Im Zweifel ja, das ist die sichere Seite."""
    try:
        antwort = call(
            messages=[{"role": "user", "content": _PROBE_FRAGE}],
            max_tokens=_PROBE_ANTWORT_TOKENS,
            temperature=0.0,
        )
    except Exception as e:  # noqa: BLE001
        # Eine Zeitueberschreitung auf "Antworte nur mit: ok" IST der Beleg fuers Denken.
        # Ein faelschlich gesetzter Schalter kostet nichts, ein fehlender kostet die Antwort.
        logger.info("Denkprobe fehlgeschlagen, gilt vorsichtshalber als denkend: {}",
                    str(e)[:200])
        return True
    return _thought(antwort)


def _measure_switch(call) -> str:
    """Which switch turns thinking off, recognised by its effect."""
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


# Sits in the middle of a shortened message so the model sees the gap.
_LUECKE = "\n\n[…]\n\n"


def fit_messages(messages: list[dict], budget_chars: int) -> list[dict]:
    """Cuts the middle out of the longest message until everything fits the budget."""
    kopie = [dict(m) for m in messages or []]
    if not kopie:
        return kopie
    gesamt = sum(len(m.get("content") or "") for m in kopie)
    if gesamt <= budget_chars:
        return kopie

    # Every message keeps a remainder, otherwise the model answers without sources.
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
    """Brings ``text`` to about ``ziel`` characters by dropping the middle."""
    if ziel >= len(text):
        return text
    nutzbar = max(0, ziel - len(_LUECKE))
    kopf = nutzbar // 2
    fuss = nutzbar - kopf
    if kopf <= 0:
        return text[:max(1, ziel)]
    return text[:kopf] + _LUECKE + (text[-fuss:] if fuss > 0 else "")


def measure_provider_model(base_url: str, api_key: str, model: str) -> ModelProfile:
    """Measures a model at its provider, only here does network traffic occur."""
    import httpx
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key or "not-needed",
        base_url=base_url,
        # Kuerzer als im Betrieb, aber lang genug, dass ein Denk-Modell die Probe schafft.
        timeout=httpx.Timeout(connect=10.0, read=_PROBE_READ_TIMEOUT, write=10.0, pool=10.0),
        max_retries=0,
    )

    def call(**kwargs):
        return client.chat.completions.create(model=model, **kwargs)

    return measure_with(call)


# ── Speicher davor ──────────────────────────────────────────────────────────

# A failed measurement is not repeated on every request.
_RETRY_AFTER_SEC = 300.0
_failed_at: dict[tuple[int, str], float] = {}


def stored_profile(provider_id: int, model: str) -> ModelProfile | None:
    """The remembered measurement, or ``None``, it never touches the network."""
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
    """The measurement of this model, taken now and stored if need be."""
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
    """Measures again and stores, even when something is already remembered."""
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
    """For the interface: the measurement as a plain dictionary."""
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
    """Learns the window size from a real refusal in operation."""
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
    """What is known about this feature's model, without network traffic."""
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


def cap_for_model(budget_chars: int, share: float, feature: str = "chat") -> int:
    """Trims an admin budget down to what the model provably takes."""
    profil = profile_for_feature(feature)
    if profil is None or not profil.measured:
        return budget_chars
    return min(budget_chars, context_chars(profil.window_tokens, share))


def _with_v1(base_url: str) -> str:
    """Some providers sit in the database with ``/v1``, some without."""
    url = (base_url or "").rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def _thought(antwort) -> bool:
    """Did the model think? Three ways, because every provider names it differently."""
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
