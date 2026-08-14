"""Folgefragen im Chat eigenstaendig machen, bevor gesucht wird.

Jede Chat-Runde steht fuer sich: es geht kein Verlauf an das Modell, damit
nichts aus einer frueheren Antwort in eine neue leckt und die Quellen-Grenze
streng bleibt. Der Preis dafuer war, dass eine Nachfrage nicht ankam. "erklaere
genauer" ging als Suchtext in die Quellen, traf nichts und bekam den Satz
"steht nicht in den Quellen"; "in 3 Stichpunkten" wurde als Ueberblick gelesen
und lieferte einen zweiten, unabhaengigen Querschnitt derselben Datei.

Der Weg hier ist ein anderer als echter Verlauf: die letzte Runde geht NUR in
den ohnehin vorhandenen Vor-Call (siehe ``_understand_query``), und der baut
daraus eine eigenstaendige Frage. Gesucht und geantwortet wird wie bisher, nur
mit der besseren Frage. Kein zusaetzlicher Modell-Aufruf, kein Verlauf im
Antwort-Prompt, keine Aenderung an Chips oder Quellen-Grenze.

Zwei Arten von Nachfrage:

``UMSCHREIBEN``  "erklaere genauer", "warum ist das so?" -> die Frage wird um
                 das Thema der letzten Runde ergaenzt und normal gesucht.
``UMFORMEN``     "in 3 Stichpunkten", "kuerzer", "als Tabelle" -> es ist nichts
                 zu suchen, gemeint ist die letzte Antwort selbst.
"""

import json
import re
from typing import Optional

from ._helpers import _strip_inline_citation_chips

KEINE = "none"
UMSCHREIBEN = "rewrite"
UMFORMEN = "reformat"

# Nur kurze Eingaben werden als Nachfrage gelesen. Eine ausformulierte Frage
# steht fuer sich, und der Vor-Call bekommt dann Zeichen fuer Zeichen dieselbe
# Eingabe wie vorher - seine Wegwahl ist fein abgestimmt und soll sich fuer den
# Normalfall nicht bewegen.
MAX_NACHFRAGE_WOERTER = 15

# Die letzte Runde ist Anhaltspunkt, nicht Stoff. Mehr als der Anfang der
# Antwort hilft dem Vor-Call nicht und kostet nur Fenster.
_MAX_ANTWORT_ZEICHEN = 1200
_MAX_FRAGE_ZEICHEN = 300


def lohnt_nachschlagen(frage: str, quelltext: Optional[str] = None) -> bool:
    """Lohnt es sich, fuer diese Eingabe ueberhaupt die letzte Runde zu holen?

    Steht vor dem Datenbankzugriff, damit eine ausformulierte Frage keinen
    kostet.
    """
    if quelltext:
        return False
    return len((frage or "").split()) <= MAX_NACHFRAGE_WOERTER


def ist_nachfrage_moeglich(
    frage: str, letzte_runde: Optional[dict], quelltext: Optional[str] = None
) -> bool:
    """Kommt fuer diese Eingabe ueberhaupt eine Nachfrage infrage?

    Nein bei markiertem Text (die Auswahl bringt ihren Zusammenhang selbst mit),
    ohne vorherige Runde, ohne Antwort in dieser Runde (eine abgebrochene Runde
    traegt keinen Zusammenhang) und bei einer ausformulierten Frage.
    """
    from src.tool_prompts import is_sentinel_refusal

    if quelltext:
        return False
    if not letzte_runde:
        return False
    antwort = (letzte_runde.get("answer") or "").strip()
    if not antwort:
        return False
    # Eine Antwort, die NUR "steht nicht in den Quellen" sagt, nennt kein Thema.
    # Eine Nachfrage darauf eigenstaendig zu machen hiesse raten, also bleibt sie
    # wie sie ist. Absage MIT Hinweis auf etwas Verwandtes zaehlt dagegen: der
    # Hinweis ist das Thema, auf das sich die Nachfrage bezieht.
    if is_sentinel_refusal(antwort):
        return False
    return len((frage or "").split()) <= MAX_NACHFRAGE_WOERTER


def verlaufsblock(letzte_runde: dict) -> str:
    """Die letzte Runde als kurzer Block fuer den Vor-Call.

    Die Quellenchips der Antwort fallen raus: sie sind Navigation fuer die
    Oberflaeche und im Prompt nur Rauschen.
    """
    frage = (letzte_runde.get("question") or "").strip()[:_MAX_FRAGE_ZEICHEN]
    antwort = _strip_inline_citation_chips(letzte_runde.get("answer") or "").strip()
    antwort = antwort[:_MAX_ANTWORT_ZEICHEN]
    return (
        "PREVIOUS TURN OF THIS CHAT (context only, never answer it again):\n"
        f"Previous question: {frage}\n"
        f"Previous answer (may be truncated): {antwort}"
    )


def vorcall_eingabe(frage: str, letzte_runde: Optional[dict]) -> str:
    """Die Nutzer-Nachricht des Vor-Calls: ohne Runde die blanke Frage, sonst
    die letzte Runde davor und die neue Zeile zuletzt (Nachwirkung)."""
    if not letzte_runde:
        return frage
    return f"{verlaufsblock(letzte_runde)}\n\nNEW LINE FROM THE USER:\n{frage}"


def umform_nachrichten(
    letzte_runde: dict, anweisung: str, chat_lang: str,
    vorherige_fragen: list[str], zusatz: str,
) -> list[dict]:
    """Die beiden Nachrichten fuer eine Umformung der letzten Antwort.

    Anders als im Verlaufsblock geht die Antwort hier VOLLSTAENDIG mit: beim
    Umformen ist sie der Stoff, nicht nur ein Anhaltspunkt. Die Quellenchips
    fallen raus, damit das Modell sie nicht in den neuen Text abschreibt - die
    Chips werden hinterher ohnehin frisch angehaengt.
    """
    from src.tool_prompts import aia_reformat_user_message, aia_system_reformat

    text = _strip_inline_citation_chips(letzte_runde.get("answer") or "").strip()
    return [
        {"role": "system", "content": aia_system_reformat(chat_lang, vorherige_fragen)},
        {"role": "user", "content": aia_reformat_user_message(text, anweisung) + zusatz},
    ]


def letzte_quellen(
    letzte_runde: dict, uuid_zu_id: dict
) -> tuple[list[dict], dict, dict, list[dict]]:
    """Die Quellenangaben der letzten Runde fuer eine Umformung weiterverwenden.

    Beim Umformen wird nicht gesucht, es gibt also keine frischen Treffer, aus
    denen die Quellennummern und die gesehenen Seiten entstehen koennten. Beides
    stammt deshalb aus der Runde, die umgeformt wird - und ist damit genau
    richtig: die umgeformte Antwort sagt dasselbe wie die alte und darf auf
    dieselben Stellen zeigen.

    Liefert ``(qmap, id_zu_qnum, gesehene_seiten, seiten)``. Eine inzwischen
    geloeschte Quelle faellt ueberall raus, damit kein Chip ins Leere zeigt.
    """
    qmap = [q for q in (letzte_runde.get("source_qmap") or [])
            if q.get("uuid") in uuid_zu_id]
    id_zu_qnum = {uuid_zu_id[q["uuid"]]: q["qnum"] for q in qmap}
    seiten = [s for s in (letzte_runde.get("source_pages") or [])
              if s.get("source_uuid") in uuid_zu_id]
    gesehen: dict[int, set] = {}
    for eintrag in seiten:
        sid = uuid_zu_id[eintrag["source_uuid"]]
        menge = gesehen.setdefault(sid, set())
        # Ton und Video werden auf Quellen-Ebene geprueft (siehe ``_is_seen``):
        # ihre Seitenzahl ist ein Abschnittszaehler, keine anspringbare Seite.
        if eintrag.get("start_time") is None and eintrag.get("page_number") is not None:
            menge.add(eintrag["page_number"])
    return qmap, id_zu_qnum, gesehen, seiten


def _json_objekt(roh: str) -> Optional[dict]:
    """Erstes JSON-Objekt aus einer Modellantwort, tolerant wie im Vor-Call:
    Denkbloecke und Codezaeune stoeren nicht."""
    text = re.sub(r"<think>.*?</think>", "", roh or "", flags=re.DOTALL)
    text = text.replace("```json", "").replace("```", "")
    treffer = re.search(r"\{.*\}", text, re.DOTALL)
    if not treffer:
        return None
    try:
        obj = json.loads(treffer.group(0))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def nachfrage_lesen(roh: str, frage: str) -> tuple[str, str]:
    """``(art, frage)`` aus der Antwort des Vor-Calls.

    Im Zweifel ``(KEINE, frage)``: lieber die Frage unveraendert lassen als sie
    auf einen erratenen Zusammenhang umzubiegen.
    """
    obj = _json_objekt(roh)
    if not obj:
        return KEINE, frage
    art = str(obj.get("followup") or "").strip().lower()
    if art not in (UMSCHREIBEN, UMFORMEN):
        return KEINE, frage
    eigenstaendig = str(obj.get("standalone") or "").strip()
    if not eigenstaendig:
        return KEINE, frage
    return art, eigenstaendig
