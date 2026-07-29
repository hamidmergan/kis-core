"""Prüfung einer Freitext-Antwort in der Grammatik-Übung.

Zwei Stufen, in dieser Reihenfolge:

1. Normalisierter Vergleich mit der Musterlösung. Trifft er zu, ist die Antwort
   richtig und es läuft KEIN Modell-Aufruf. Das ist der häufige Fall und der
   Grund für die Stufe: das geteilte GWDG-Limit (siehe Notizen zu den Rate-Limits)
   verträgt keinen Aufruf pro getippter Antwort.
2. Nur bei Abweichung ein Modell-Aufruf. Er bekommt Regel, Musterlösung und die
   Antwort und liefert ein Urteil plus eine kurze Rückmeldung.

Fällt der Aufruf aus, entscheidet eine Wortüberdeckung. Der Lernende bekommt dann
zwar keine erklärende Rückmeldung, hängt aber nie fest.

Die Normalisierung ist bewusst sprach-unabhängig: kein Wörterbuch, keine deutschen
Sonderregeln, nur Unicode-Kategorien.
"""

import json
import re
import unicodedata
from typing import Optional

from loguru import logger

VERDICT_CORRECT = "correct"
VERDICT_CLOSE = "close"
VERDICT_WRONG = "wrong"

_VERDICTS = (VERDICT_CORRECT, VERDICT_CLOSE, VERDICT_WRONG)

# Ab dieser Wortüberdeckung gilt eine Antwort im Notfallpfad als "fast".
_CLOSE_RATIO = 0.72

# Klammereinschübe sind im Muster optional ("Die Briefe müssen (von mir) ...").
# Wer sie weglässt, hat trotzdem recht, also fliegen sie vor dem Vergleich raus.
_PARENS_RE = re.compile(r"\([^)]*\)")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Vergleichsform: klein, ohne Klammereinschübe, ohne Satzzeichen."""
    if not text:
        return ""
    cleaned = _PARENS_RE.sub(" ", text)
    # Unicode-Kategorie P* sind alle Satzzeichen, in jeder Sprache.
    cleaned = "".join(
        " " if unicodedata.category(ch).startswith("P") else ch
        for ch in cleaned
    )
    return _WS_RE.sub(" ", cleaned).strip().casefold()


def is_exact_match(given: str, expected: str) -> bool:
    """True wenn die Antwort nach Normalisierung der Musterlösung entspricht."""
    normalized = normalize(given)
    return bool(normalized) and normalized == normalize(expected)


def overlap_ratio(given: str, expected: str) -> float:
    """Anteil gemeinsamer Wörter, Vielfachheit berücksichtigt. 0.0 bis 1.0."""
    a = normalize(given).split()
    b = normalize(expected).split()
    if not a or not b:
        return 0.0
    pool = list(b)
    hits = 0
    for word in a:
        if word in pool:
            pool.remove(word)
            hits += 1
    return hits / max(len(a), len(b))


def heuristic_verdict(given: str, expected: str) -> str:
    """Urteil ohne Modell. Notfallpfad, wenn der Aufruf scheitert."""
    if is_exact_match(given, expected):
        return VERDICT_CORRECT
    return VERDICT_CLOSE if overlap_ratio(given, expected) >= _CLOSE_RATIO else VERDICT_WRONG


def _build_prompt(rule: str, language: str) -> str:
    return (
        "You mark a single grammar exercise answer. The learner had to transform a "
        "sentence according to this rule:\n"
        f"{rule}\n\n"
        "You get the original sentence, the expected solution and the learner's answer.\n"
        "Judge ONLY the grammatical transformation:\n"
        "- 'correct' when the transformation is right, even if wording, word order or the "
        "optional agent phrase differ from the expected solution.\n"
        "- 'close' when the transformation is attempted and the meaning is there, but one "
        "form is wrong (wrong auxiliary, wrong participle, wrong case, missing part).\n"
        "- 'wrong' when the transformation was not carried out, or the meaning changed.\n"
        "Spelling slips and missing capitalisation alone do NOT make an answer wrong.\n\n"
        f"Write 'feedback' in {language}, address the learner informally, one or two short "
        "sentences. Name the form that is off. Never reveal the expected solution in the "
        "feedback, the interface shows it separately.\n\n"
        'Respond ONLY with JSON: {"verdict": "correct|close|wrong", "feedback": "..."}'
    )


def check_answer(
    client, model: str, *,
    given: str, expected: str, prompt_sentence: str, rule: str,
    language: str = "German",
) -> dict:
    """Ein Urteil zu einer Antwort: ``{"verdict": ..., "feedback": ..., "used_llm": bool}``.

    Der Modell-Aufruf entfällt bei exakter Übereinstimmung, deshalb ist ``client``
    in dem Fall nie in Benutzung.
    """
    if is_exact_match(given, expected):
        return {"verdict": VERDICT_CORRECT, "feedback": None, "used_llm": False}

    user = (
        f"Original sentence: {prompt_sentence}\n"
        f"Expected solution: {expected}\n"
        f"Learner's answer: {given}"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _build_prompt(rule, language)},
                {"role": "user", "content": user},
            ],
            # Marking is a judgement call, not a creative one.
            temperature=0.1,
        )
        raw = (response.choices[0].message.content or "").strip()
        data = json.loads(_strip_fences(raw))
        verdict = str(data.get("verdict") or "").strip().lower()
        if verdict not in _VERDICTS:
            raise ValueError(f"unknown verdict {verdict!r}")
        feedback = (data.get("feedback") or "").strip() or None
        return {"verdict": verdict, "feedback": feedback, "used_llm": True}
    except Exception as e:
        # Never block the learner on a provider hiccup: fall back to the word overlap
        # and say nothing rather than something wrong.
        logger.warning("KI Tutor: grammar check fell back to heuristic: {}", e)
        return {
            "verdict": heuristic_verdict(given, expected),
            "feedback": None,
            "used_llm": False,
        }


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def get_check_client() -> tuple[Optional[object], str]:
    """(client, model) für die Prüfung, oder (None, "") wenn keine Route gesetzt ist.

    Nutzt dieselbe Chat-Route wie der Rest des Assistenten. Der Aufrufer fällt bei
    None auf die Heuristik zurück.
    """
    try:
        from langfuse.openai import OpenAI
        from src.dependencies import _resolve_llm_provider
        api_key, base_url, model, _provider = _resolve_llm_provider()
        # Kurzer Timeout: der Lernende wartet vor dem Bildschirm auf die Rückmeldung.
        return OpenAI(api_key=api_key, base_url=base_url, max_retries=0, timeout=30), model
    except Exception as e:
        logger.warning("KI Tutor: no chat route for grammar check: {}", e)
        return None, ""


__all__ = [
    "VERDICT_CORRECT", "VERDICT_CLOSE", "VERDICT_WRONG",
    "normalize", "is_exact_match", "overlap_ratio", "heuristic_verdict",
    "check_answer", "get_check_client",
]
