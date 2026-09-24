"""The whole material of a run as numbered passages, and the way back from a number.

Planning happens over this map, writing happens from the original text behind the
numbers. Nothing is extracted in between: a number points into the canonical text of
sources.json and never into something a model wrote.

The reason is time. A model reads fast and writes slowly, and the provider ends every
call after five minutes. A call that plans over the whole text writes little, a call
that writes one part of the result writes little too, so every call stays short.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Callable

from src.limits import (
    MAP_FILE_WEIGHT_FLOOR,
    MAP_MAX_REFS,
    MAP_MIN_FILE_SHARE,
    MAP_MAX_TOPICS_PER_PART,
    MAP_MIN_WINDOW_TOKENS,
    MAP_OUTPUT_TOKENS,
    MAP_PROMPT_TOKENS,
    MAP_RANGE_MAX,
    MAP_UNMEASURED_WINDOW_TOKENS,
)
from src.services.model_limits import CHARS_PER_TOKEN
from src.services.source_reading import Source

# What the answer of a planning call calls its passage or topic numbers.
REFS = "refs"

STELLEN = "stellen"
THEMEN = "themen"

_BEREICH = re.compile(r"^\s*(\d+)\s*[-–—]\s*(\d+)\s*$")


class WindowTooSmall(ValueError):
    """The chosen model cannot carry a useful part of the material, refused up front."""


@dataclass(frozen=True)
class Stelle:
    """Where a numbered passage sits: which source, which of its pieces."""

    source: int
    piece: int


@dataclass(frozen=True)
class Thema:
    """One topic a part of the material was boiled down to, with the passages behind it."""

    nummer: int
    titel: str
    kern: str
    stellen: tuple[int, ...]


def window_chars(window_tokens: int) -> int:
    """How much numbered text one planning call may carry on this model."""
    if window_tokens and window_tokens < MAP_MIN_WINDOW_TOKENS:
        raise WindowTooSmall(window_tokens)
    fenster = window_tokens or MAP_UNMEASURED_WINDOW_TOKENS
    return max(1, int((fenster - MAP_PROMPT_TOKENS - MAP_OUTPUT_TOKENS) * CHARS_PER_TOKEN))


class Karte:
    """Every piece of every source under one running number, counted from 1."""

    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources
        self.stellen: list[Stelle] = [
            Stelle(source=q, piece=p)
            for q, source in enumerate(sources) for p in range(len(source.stuecke))
        ]

    def __len__(self) -> int:
        return len(self.stellen)

    def stelle(self, nummer: int) -> Stelle:
        return self.stellen[nummer - 1]

    def _seite(self, nummer: int) -> tuple[int, int]:
        st = self.stelle(nummer)
        return st.source, self.sources[st.source].stuecke[st.piece].seite

    def segment(self, nummer: int) -> str:
        """The text of one number, up to where the next piece begins.

        Pieces overlap so that no sentence is cut apart. On the map the overlap would
        only double the text, so each number shows its piece up to its successor.
        """
        st = self.stelle(nummer)
        quelle = self.sources[st.source]
        stuecke = quelle.stuecke
        von = stuecke[st.piece].von
        bis = stuecke[st.piece + 1].von if st.piece + 1 < len(stuecke) else stuecke[st.piece].bis
        return quelle.text[von:bis].strip()

    def block(self, nummern: range | None = None) -> str:
        """The numbered text as a planning call reads it, each file under its name."""
        teile: list[str] = []
        vorige = -1
        for n in nummern if nummern is not None else range(1, len(self) + 1):
            st = self.stelle(n)
            if st.source != vorige:
                teile.append(f"=== {self.sources[st.source].dateiname} ===")
                vorige = st.source
            teile.append(f"[{n}] {self.segment(n)}")
        return "\n\n".join(teile)

    def teile(self, window_tokens: int) -> list[range]:
        """The numbers cut into as few planning calls as the window allows.

        Cut at a change of file or page near the even share, so no call starts in the
        middle of a page when it does not have to.
        """
        if not self.stellen:
            return []
        nutzbar = window_chars(window_tokens)
        # What each number costs on the map, its header included where a file begins.
        kosten = []
        for n in range(1, len(self) + 1):
            kopf = len(self.sources[self.stelle(n).source].dateiname) + 10 \
                if n == 1 or self.stelle(n).source != self.stelle(n - 1).source else 0
            kosten.append(len(self.segment(n)) + len(str(n)) + 4 + kopf)
        gesamt = sum(kosten)
        if gesamt <= nutzbar:
            return [range(1, len(self) + 1)]
        anzahl = math.ceil(gesamt / nutzbar)
        ziel = gesamt / anzahl
        grenzen = [1]
        summe = 0
        for n in range(1, len(self) + 1):
            summe += kosten[n - 1]
            voll = len(grenzen) < anzahl and summe >= ziel * len(grenzen)
            if voll and n < len(self):
                grenzen.append(self._naechste_grenze(n, grenzen[-1]))
        grenzen.append(len(self) + 1)
        return [range(a, b) for a, b in zip(grenzen, grenzen[1:]) if b > a]

    def _naechste_grenze(self, n: int, start: int) -> int:
        """The first number of the next part: a new file or page close before n, else n + 1."""
        for kandidat in range(n + 1, max(start + 1, n - 30), -1):
            if kandidat > len(self):
                continue
            if self._seite(kandidat) != self._seite(kandidat - 1):
                return kandidat
        return n + 1

    def gueltig(self, roh) -> list[int]:
        """The passage numbers of an answer, invented and doubled ones dropped.

        Accepts numbers and ranges written as "12-15", a range is capped so one wild
        answer cannot pull in a whole document.
        """
        return _nummern(roh, len(self))

    def passagen(self, nummern: list[int], *, nachbarn: int = 1,
                 budget: int | None = None) -> str:
        """The original text behind these numbers, each with its neighbours.

        Neighbouring numbers are joined into one passage, each passage names its file
        and page. The passages come in the order of the text, cut where the budget ends.
        """
        gewollt: dict[int, set[int]] = {}
        for n in nummern:
            if not 1 <= n <= len(self):
                continue
            st = self.stelle(n)
            anzahl = len(self.sources[st.source].stuecke)
            gewollt.setdefault(st.source, set()).update(
                p for p in range(st.piece - nachbarn, st.piece + nachbarn + 1) if 0 <= p < anzahl)
        teile: list[str] = []
        laenge = 0
        for q in sorted(gewollt):
            quelle = self.sources[q]
            laeufe: list[list[int]] = []
            for p in sorted(gewollt[q]):
                if laeufe and p == laeufe[-1][-1] + 1:
                    laeufe[-1].append(p)
                else:
                    laeufe.append([p])
            for lauf in laeufe:
                erstes = quelle.stuecke[lauf[0]]
                text = quelle.text[erstes.von:quelle.stuecke[lauf[-1]].bis].strip()
                stueck = f"[{quelle.dateiname}, S. {erstes.seite}]\n{text}"
                if budget is not None and teile and laenge + len(stueck) > budget:
                    return "\n\n".join(teile)
                teile.append(stueck)
                laenge += len(stueck) + 2
        return "\n\n".join(teile)


def abdeckung(listen: list[list[int]], gesamt: int) -> float:
    """Which share of all passages the entries of a plan name, from 0 to 1."""
    if not gesamt:
        return 1.0
    return len({n for liste in listen for n in liste if 1 <= n <= gesamt}) / gesamt


def fehlende_dateien(listen: list[list[int]], karte: "Karte") -> list[str]:
    """The files no entry of a plan draws on, a plan that skips one is not usable."""
    genannt = {karte.stelle(n).source for liste in listen for n in liste if 1 <= n <= len(karte)}
    return [q.dateiname for i, q in enumerate(karte.sources) if q.stuecke and i not in genannt]


def zu_kurz(listen: list[list[int]], karte: "Karte") -> list[tuple[str, int]]:
    """The files a plan hardly draws on, with the share of the material they hold.

    Naming one passage of a file is not covering it: an entry follows its title, and a
    file that only turns up in a stray number is talked over. A file gets at least a
    quarter of the weight it has in the material, files below a twentieth are spared.
    """
    genannt = [n for liste in listen for n in set(liste) if 1 <= n <= len(karte)]
    if not genannt or not len(karte):
        return []
    aus: list[tuple[str, int]] = []
    for i, q in enumerate(karte.sources):
        anteil_text = len(q.stuecke) / len(karte)
        if anteil_text < MAP_MIN_FILE_SHARE:
            continue
        anteil_plan = sum(1 for n in genannt if karte.stelle(n).source == i) / len(genannt)
        if anteil_plan < anteil_text * MAP_FILE_WEIGHT_FLOOR:
            aus.append((q.dateiname, round(anteil_text * 100)))
    return aus


def ziel_eintraege(zeichen: int, lo: int, hi: int, *, grund: int, je: int) -> int:
    """How many entries the material carries, a target the planner may deviate from."""
    return max(lo, min(hi, grund + zeichen // je))


def abdecken(listen: list[list[int]], gesamt: int) -> list[list[int]]:
    """Every passage no entry names goes to the entry whose numbers lie closest.

    A plan that leaves a stretch of the text out would lose it for good, the writer only
    ever sees what its entry names. Entries without numbers stay as they are, they rest
    on the whole anyway.
    """
    genannt = {n for liste in listen for n in liste}
    mit = [i for i, liste in enumerate(listen) if liste]
    if not mit:
        return [list(liste) for liste in listen]
    aus = [list(liste) for liste in listen]
    for n in range(1, gesamt + 1):
        if n in genannt:
            continue
        naechster = min(mit, key=lambda i: min(abs(n - m) for m in listen[i]))
        aus[naechster].append(n)
    return [sorted(liste) for liste in aus]


def _nummern(roh, hoechste: int) -> list[int]:
    if not isinstance(roh, list):
        return []
    aus: list[int] = []
    for wert in roh:
        if isinstance(wert, bool):
            continue
        treffer = _BEREICH.match(str(wert))
        if treffer:
            a, b = int(treffer.group(1)), int(treffer.group(2))
            if b < a:
                a, b = b, a
            kandidaten = range(a, min(b, a + MAP_RANGE_MAX - 1) + 1)
        else:
            try:
                kandidaten = [int(str(wert).strip())]
            except ValueError:
                continue
        for n in kandidaten:
            if 1 <= n <= hoechste and n not in aus:
                aus.append(n)
            if len(aus) >= MAP_MAX_REFS:
                return aus
    return aus


# ── Die Planungsgrundlage ────────────────────────────────────────────────────

def hinweis(modus: str) -> str:
    """What the numbers in the material mean, the same wording for every service."""
    if modus == THEMEN:
        return (
            'The material is a numbered list of topics, written as "[n] title: gist". '
            "Together they cover the whole text. Under \"refs\" name the numbers of the "
            "topics an entry draws on."
        )
    return (
        'The material is the full text, cut into numbered passages written as "[n] text". '
        "Under \"refs\" name the passages an entry draws on. Write neighbouring numbers as "
        'one range such as "12-18" instead of listing them, and keep refs short: at most '
        "10 entries. Name only numbers that appear in the material."
    )


@dataclass
class Grundlage:
    """What a planning call reads, and how its answer finds its way back to the text."""

    material: str
    modus: str
    themen: list[Thema]

    def stellen(self, refs, karte: Karte) -> list[int]:
        """The passage numbers behind the refs of one entry."""
        if self.modus != THEMEN:
            return karte.gueltig(refs)
        nach_nummer = {t.nummer: t for t in self.themen}
        aus: list[int] = []
        for n in _nummern(refs, len(self.themen)):
            for s in nach_nummer[n].stellen:
                if s not in aus:
                    aus.append(s)
        return aus


def themen_nachrichten(karte: Karte, teil: range, teile: int, nummer: int,
                       language: str, zweck: str) -> list[dict]:
    """One part of the material boiled down to its topics, when the whole does not fit."""
    system = (
        "You map a text. The text is cut into numbered passages. List the topics this "
        f"text covers, in the order they appear, at most {MAP_MAX_TOPICS_PER_PART}. "
        f"This is part {nummer} of {teile} of the material, other parts are mapped "
        "separately. For every topic give a short title, one sentence saying what the "
        "text states about it, and the passage numbers it draws on, as integers or as "
        'ranges written "12-15". Every passage that carries content belongs to a topic. '
        f"Write titles and sentences in {language}. The material will be used for: {zweck}.\n"
        'Answer with one JSON object only: {"topics": [{"title": "...", "gist": "...", '
        '"refs": [1, "4-7"]}]}'
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\n{karte.block(teil)}"}]


def parse_themen(raw: str | None, karte: Karte, erste_nummer: int) -> list[Thema]:
    """The topics out of one answer, numbered on from where the previous part stopped."""
    daten = _json_objekt(raw)
    roh = daten.get("topics") if isinstance(daten, dict) else None
    aus: list[Thema] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, dict):
            continue
        titel = " ".join(str(eintrag.get("title") or "").split())[:120]
        stellen = karte.gueltig(eintrag.get(REFS))
        if not titel or not stellen:
            continue
        aus.append(Thema(nummer=erste_nummer + len(aus), titel=titel,
                         kern=" ".join(str(eintrag.get("gist") or "").split())[:300],
                         stellen=tuple(stellen)))
        if len(aus) >= MAP_MAX_TOPICS_PER_PART:
            break
    return aus


def themen_block(themen: list[Thema]) -> str:
    return "\n".join(f"[{t.nummer}] {t.titel}: {t.kern}" for t in themen)


def grundlage(karte: Karte, window_tokens: int, *, language: str, zweck: str,
              frage: Callable[[list[list[dict]]], list[str | None]]) -> Grundlage:
    """The material a planning call reads: the full numbered text, or its topics.

    ``frage`` sends several calls at once and returns their raw answers in order, so
    each service keeps its own way of calling the model.
    """
    teile = karte.teile(window_tokens)
    if len(teile) <= 1:
        return Grundlage(material=karte.block(), modus=STELLEN, themen=[])
    antworten = frage([themen_nachrichten(karte, teil, len(teile), i + 1, language, zweck)
                       for i, teil in enumerate(teile)])
    themen: list[Thema] = []
    for antwort in antworten:
        themen.extend(parse_themen(antwort, karte, len(themen) + 1))
    if not themen:
        raise RuntimeError("Aus keinem Teil des Materials liessen sich Themen gewinnen.")
    return Grundlage(material=themen_block(themen), modus=THEMEN, themen=themen)


def grundlage_als_dict(g: Grundlage) -> dict:
    """For the job folder, so a later stage does not pay for the topics again."""
    return {"modus": g.modus, "themen": [
        {"nummer": t.nummer, "titel": t.titel, "kern": t.kern, "stellen": list(t.stellen)}
        for t in g.themen]}


def grundlage_aus_dict(daten: dict | None, karte: Karte) -> Grundlage | None:
    if not isinstance(daten, dict):
        return None
    if daten.get("modus") == STELLEN:
        return Grundlage(material=karte.block(), modus=STELLEN, themen=[])
    themen = []
    for e in daten.get("themen") or []:
        try:
            themen.append(Thema(nummer=int(e["nummer"]), titel=str(e["titel"]),
                                kern=str(e.get("kern") or ""),
                                stellen=tuple(int(s) for s in e.get("stellen") or [])))
        except (KeyError, TypeError, ValueError):
            continue
    if not themen:
        return None
    return Grundlage(material=themen_block(themen), modus=THEMEN, themen=themen)


def _json_objekt(raw: str | None):
    text = (raw or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    start, ende = text.find("{"), text.rfind("}")
    if start < 0 or ende <= start:
        return None
    try:
        return json.loads(text[start:ende + 1])
    except json.JSONDecodeError:
        return None
