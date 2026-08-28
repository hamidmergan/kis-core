"""Small helpers around the answer stream: retry without thinking, usage, trace."""

from typing import Optional

from loguru import logger

from langfuse.decorators import langfuse_context


async def _antwort_ohne_denken(llm, messages: list[dict]) -> str:
    """Holt die Antwort ohne Strom und ohne Denken, jeden Schalter der Reihe nach."""
    import asyncio as _a

    from src.services import model_limits as _ml

    # Der schon aktive Schalter zuerst, danach die anderen. Nie zwei gleichzeitig,
    # das lehnen strenge Anbieter ab.
    _aktiv = getattr(getattr(llm, "_model_profile", None), "think_off", "") or ""
    _reihe = [_aktiv] if _aktiv else []
    _reihe += [n for n in _ml._SWITCH_ORDER if n != _aktiv]

    _grund = {k: v for k, v in (llm._extra_body or {}).items()
              if k not in _ml.THINK_OFF_SWITCHES}

    # Eigene Kopie, damit ein gelerntes Fenster hier auch wirkt.
    _msgs = list(messages)
    # Kleiner als im Strom, ein enges Fenster platzt sonst schon an der Ausgabe.
    _raum = min(_ml.CHAT_MAX_OUTPUT_TOKENS, 2048)

    def _hol(schalter: dict, nachrichten: list[dict]):
        antwort = llm._client.with_options(timeout=180.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=nachrichten,
            temperature=0.3,
            max_tokens=_raum,
            extra_body={**_grund, **schalter} or None,
        )
        nachricht = antwort.choices[0].message
        # Manche Denk-Modelle legen alles ins Denkfeld, dann ist das die Antwort.
        return (nachricht.content
                or getattr(nachricht, "reasoning_content", None)
                or getattr(nachricht, "reasoning", None)
                or "")

    for _name in _reihe:
        _schalter = dict(_ml.THINK_OFF_SWITCHES.get(_name) or {})
        if not _schalter:
            continue
        for _anlauf in (1, 2, 3, 4):
            try:
                _text = (await _a.to_thread(_hol, _schalter, _msgs)).strip()
            except Exception as e:  # noqa: BLE001 — abgelehnt heisst nur: naechster Anlauf
                _ml.learn_from_error(getattr(llm, "_provider_id", None), llm._model, e)
                # Relativ schrumpfen statt auf die Formel. Die rechnet mit 3 Zeichen
                # je Token, deutscher Text liegt naeher bei 2 und passt sonst nie.
                _zu_lang = "context length" in str(e).lower() or "max_tokens" in str(e).lower()
                _jetzt = sum(len(m.get("content") or "") for m in _msgs)
                if _zu_lang and _anlauf < 4 and _jetzt > _ml.MIN_CONTEXT_CHARS:
                    _msgs = _ml.fit_messages(
                        _msgs, max(_ml.MIN_CONTEXT_CHARS, int(_jetzt * 0.55))
                    )
                    logger.info("Nachschlag zu lang, gekuerzt auf {} Zeichen",
                                sum(len(m.get("content") or "") for m in _msgs))
                    continue
                logger.warning("Nachschlag mit Schalter {} fehlgeschlagen: {}",
                               _name, str(e)[:160])
                break
            if _text:
                logger.info("Nachschlag erfolgreich mit Schalter {}", _name)
                return _text
            break
    return ""


def _stream_usage_tokens(chunk) -> tuple[Optional[int], Optional[int]]:
    """Pulls the token counts out of a stream chunk, otherwise (None, None)."""
    usage = getattr(chunk, "usage", None)
    if usage is None:
        return None, None
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


def _enrich_chat_trace(trace_id, question, answer, *, user_id, session_id) -> None:
    """Backfills question and answer via the trace id, errors stay silent."""
    if not trace_id:
        return
    try:
        langfuse_context.client_instance.trace(
            id=trace_id,
            input=question,
            output=answer,
            user_id=user_id,
            session_id=session_id,
        )
    except Exception:
        pass
