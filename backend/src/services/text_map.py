"""The whole material of a run as numbered passages, and the way back from a number.

Planning happens over this map, writing happens from the original text behind the
numbers. Nothing is extracted in between: a number points into the canonical text of
sources.json and never into something a model wrote.

The reason is time. A model reads fast and writes slowly, and the provider ends every
call after five minutes. A call that plans over the whole text writes little, a call
that writes one part of the result writes little too, so every call stays short.
"""

from __future__ import annotations

import bisect
import json
import math
import re
from dataclasses import dataclass
from typing import Callable

from src.limits import (
    MAP_ANKER_MIN_ANTEIL,
    MAP_ANKER_MIN_ZEICHEN,
    MAP_MATERIAL_MAX_CHARS,
    MAP_FILE_WEIGHT_FLOOR,
    MAP_MAX_REFS,
    MAP_MIN_FILE_SHARE,
    MAP_MAX_TOPICS_PER_PART,
    MAP_MAX_TOPICS_TOTAL,
    MAP_MIN_TOPICS_PER_FILE,
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
# The first words of an entry's text, copied, so KIS finds the passage itself.
ANFANG = "start"

STELLEN = "stellen"
THEMEN = "themen"

# Labels in front of passage and topic numbers, a bare [45] reads like § 45 in a law and none of 119 test PDFs holds them.
MARKE_STELLE = "SZ"
MARKE_THEMA = "TZ"

# A number or a range with or without its label, any dash a model writes, gpt-oss uses the non-breaking hyphen.
_BEREICH = re.compile(r"^\s*[A-Za-z]{0,3}\s*(\d+)\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]\s*[A-Za-z]{0,3}\s*(\d+)\s*$")
_EINZELN = re.compile(r"^\s*[A-Za-z]{0,3}\s*(\d+)\s*$")


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


_LEERRAUM = re.compile(r"\s+")
# Soft hyphen and the like vanish, every dash becomes one, so a copied quote still matches.
_ZEICHEN = str.maketrans({"\u00ad": None, "\u2010": "-", "\u2011": "-", "\u2012": "-",
                          "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u201e": '"',
                          "\u201c": '"', "\u201d": '"', "\u2019": "'"})


def _normal(text: str) -> str:
    return _LEERRAUM.sub(" ", text.translate(_ZEICHEN)).strip().casefold()


def _normal_mit_orten(text: str) -> tuple[str, list[int]]:
    """The text as ``_normal`` makes it, with the original position of every character kept."""
    zeichen: list[str] = []
    orte: list[int] = []
    leer = True
    for i, z in enumerate(text):
        z = z.translate(_ZEICHEN)
        if not z:
            continue
        if z.isspace():
            if not leer:
                zeichen.append(" ")
                orte.append(i)
            leer = True
            continue
        for teil in z.casefold():
            zeichen.append(teil)
            orte.append(i)
        leer = False
    return "".join(zeichen), orte


def schreib_budget(window_tokens: int) -> int:
    """How much original text one writing call may carry, the fixed cap or what the window leaves."""
    return min(MAP_MATERIAL_MAX_CHARS, window_chars(window_tokens))


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
            teile.append(f"[{MARKE_STELLE}{n}] {self.segment(n)}")
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

    def abschnitte(self, window_tokens: int) -> list[tuple[range, int]]:
        """The pieces of the topic stage: the parts, cut again where a file ends.

        Each piece gets topics by its share of the whole, never fewer than a floor. One call
        over several files lists the first ones and runs out before the last.
        """
        teile = self.teile(window_tokens)
        gesamt = min(MAP_MAX_TOPICS_PER_PART * len(teile), MAP_MAX_TOPICS_TOTAL)
        aus: list[tuple[range, int]] = []
        for teil in teile:
            start = teil.start
            for n in range(teil.start + 1, teil.stop + 1):
                if n == teil.stop or self.stelle(n).source != self.stelle(n - 1).source:
                    bereich = range(start, n)
                    anzahl = max(MAP_MIN_TOPICS_PER_FILE, round(gesamt * len(bereich) / len(self)))
                    aus.append((bereich, anzahl))
                    start = n
        return aus

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

    def finde(self, zitat, *, bereich: range | None = None,
              nahe: list[int] | None = None) -> int | None:
        ort = self.finde_mit_anteil(zitat, bereich=bereich, nahe=nahe)
        return ort[0] if ort else None

    def finde_mit_anteil(self, zitat, *, bereich: range | None = None,
                         nahe: list[int] | None = None) -> tuple[int, float] | None:
        """The passage where these copied words stand, None when they stand nowhere.

        A model copies text far more reliably than it keeps numbers apart from the
        paragraph numbers of a law, so its first words find the place it meant. Words
        cut off at the end still count, the shorter the rest the likelier it repeats,
        so it never gets shorter than MAP_ANKER_MIN_ZEICHEN. Of several places the one
        where most of the copied words go on matching wins, a table of contents repeats
        a heading but not the sentence after it. A tie goes to the one closest to ``nahe``.
        """
        ganz = _normal(str(zitat or ""))
        woerter = ganz.split(" ")
        if not hasattr(self, "_index"):
            self._index = [_normal_mit_orten(q.text) for q in self.sources]
        for laenge in range(len(woerter), 0, -1):
            nadel = " ".join(woerter[:laenge])
            if len(nadel) < MAP_ANKER_MIN_ZEICHEN:
                return None
            orte = [(n, gleich) for n, gleich in self._orte(nadel, ganz) if bereich is None or n in bereich]
            if orte:
                naehe = (lambda n: min(abs(n - m) for m in nahe)) if nahe else (lambda n: 0)
                ort, gleich = min(orte, key=lambda o: (-o[1], naehe(o[0])))
                return ort, gleich / max(1, len(ganz))
        return None

    def _orte(self, nadel: str, ganz: str) -> list[tuple[int, int]]:
        """Every passage in which the words begin, with how many characters of ``ganz`` match there."""
        orte: list[tuple[int, int]] = []
        vorher = 0
        for q, (text, positionen) in enumerate(self._index):
            anfaenge = [s.von for s in self.sources[q].stuecke]
            start = text.find(nadel)
            while start != -1:
                gleich = len(nadel)
                while gleich < len(ganz) and start + gleich < len(text) and text[start + gleich] == ganz[gleich]:
                    gleich += 1
                orte.append((vorher + bisect.bisect_right(anfaenge, positionen[start]), gleich))
                start = text.find(nadel, start + 1)
            vorher += len(anfaenge)
        return orte

    def verankern(self, stellen: list[int], zitat, *, bereich: range | None = None) -> list[int]:
        """The passages moved to where the copied first words really stand.

        Unchanged when the words stand nowhere or already at or next to the passages
        named. Otherwise as many passages as were named, from the found place on, kept
        inside its file and ``bereich``.
        """
        treffer = self.finde_mit_anteil(zitat, bereich=bereich, nahe=stellen or None)
        if treffer is None or treffer[1] < MAP_ANKER_MIN_ANTEIL:
            return stellen
        ort = treffer[0]
        if any(abs(ort - n) <= 1 for n in stellen):
            return stellen
        datei = self.stelle(ort).source
        ende = max(n for n in range(ort, len(self) + 1) if self.stelle(n).source == datei
                   and (bereich is None or n in bereich))
        return list(range(ort, min(ort + max(1, len(set(stellen))), ende + 1, ort + MAP_MAX_REFS)))

    def passagen(self, nummern: list[int], *, vorrang: list[int] | None = None,
                 nachbarn: int = 1, budget: int | None = None) -> str:
        """The original text behind these numbers, each with its neighbours.

        Neighbouring numbers are joined into one passage, each passage names its file
        and page. The passages come in the order of the text. When they do not fit the
        budget, the numbers in ``vorrang`` go first and the rest fills what is left, in
        both every file keeps its share, spread over the whole file.
        """
        zuerst = set(vorrang or []) & set(nummern)
        benannt = self._nach_datei(n for n in nummern if n in zuerst)
        rest = self._nach_datei(n for n in nummern if n not in zuerst)
        gewollt = self._mit_nachbarn(self._vereint(benannt, rest), nachbarn)
        if budget is not None and self._kosten(gewollt) > budget:
            gewollt = self._gekuerzt(benannt, rest, nachbarn, budget)
        teile: list[str] = []
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
                teile.append(f"[{quelle.dateiname}, S. {erstes.seite}]\n{text}")
        return "\n\n".join(teile)

    def _nach_datei(self, nummern) -> dict[int, set[int]]:
        aus: dict[int, set[int]] = {}
        for n in nummern:
            if 1 <= n <= len(self):
                st = self.stelle(n)
                aus.setdefault(st.source, set()).add(st.piece)
        return aus

    @staticmethod
    def _vereint(*teile: dict[int, set[int]]) -> dict[int, set[int]]:
        aus: dict[int, set[int]] = {}
        for teil in teile:
            for q, stuecke in teil.items():
                aus.setdefault(q, set()).update(stuecke)
        return aus

    def _gekuerzt(self, zuerst: dict[int, set[int]], rest: dict[int, set[int]],
                  nachbarn: int, budget: int) -> dict[int, set[int]]:
        """The first numbers within the budget, the rest only in the room they leave."""
        if not zuerst:
            return self._im_budget(rest, nachbarn, budget)
        gewollt = self._mit_nachbarn(zuerst, nachbarn)
        if self._kosten(gewollt) > budget:
            return self._im_budget(zuerst, nachbarn, budget)
        frei = budget - self._kosten(gewollt)
        uebrig = {q: {p for p in stuecke if p not in gewollt.get(q, set())}
                  for q, stuecke in rest.items()}
        uebrig = {q: stuecke for q, stuecke in uebrig.items() if stuecke}
        mittel = self._kosten(uebrig) / max(1, sum(len(v) for v in uebrig.values()))
        if not uebrig or frei < mittel * len(uebrig):
            return gewollt
        return self._vereint(gewollt, self._im_budget(uebrig, nachbarn, frei))

    def _mit_nachbarn(self, benannt: dict[int, set[int]], nachbarn: int) -> dict[int, set[int]]:
        aus: dict[int, set[int]] = {}
        for q, stuecke in benannt.items():
            anzahl = len(self.sources[q].stuecke)
            aus[q] = {p + d for p in stuecke for d in range(-nachbarn, nachbarn + 1)
                      if 0 <= p + d < anzahl}
        return aus

    def _stueck_kosten(self, q: int, p: int) -> int:
        """What one piece costs in a passage, its own header counted as if it stood alone."""
        quelle = self.sources[q]
        stueck = quelle.stuecke[p]
        return stueck.bis - stueck.von + len(quelle.dateiname) + 12

    def _kosten(self, gewollt: dict[int, set[int]]) -> int:
        return sum(self._stueck_kosten(q, p) for q, stuecke in gewollt.items() for p in stuecke)

    def _im_budget(self, benannt: dict[int, set[int]], nachbarn: int,
                   budget: int) -> dict[int, set[int]]:
        """Every file gets the budget by its share of the named pieces, spread over the file.

        Cut in the order of the text, the first file would fill the budget and a later one
        would reach no writer at all. Neighbours come only where a file's share has room.
        """
        gesamt = self._kosten(benannt) or 1
        aus: dict[int, set[int]] = {}
        for q, stuecke in benannt.items():
            reihe = sorted(stuecke)
            anteil = budget * self._kosten({q: stuecke}) / gesamt
            mittel = self._kosten({q: stuecke}) / len(reihe)
            k = max(1, min(len(reihe), int(anteil // mittel)))
            gewaehlt = {reihe[round(i * (len(reihe) - 1) / (k - 1))] for i in range(k)} \
                if k > 1 else {reihe[0]}
            rest = anteil - self._kosten({q: gewaehlt})
            anzahl = len(self.sources[q].stuecke)
            for p in sorted(gewaehlt):
                for d in range(1, nachbarn + 1):
                    for nachbar in (p - d, p + d):
                        if 0 <= nachbar < anzahl and nachbar not in gewaehlt:
                            preis = self._stueck_kosten(q, nachbar)
                            if preis <= rest:
                                gewaehlt.add(nachbar)
                                rest -= preis
            aus[q] = gewaehlt
        return aus


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


def exklusiv(listen: list[list[int]]) -> list[list[int]]:
    """A passage several entries name stays with the first, two writers would repeat it.

    An entry that would be left with nothing keeps its own numbers, an empty entry
    would rest on the whole text instead.
    """
    vergeben: set[int] = set()
    aus: list[list[int]] = []
    for liste in listen:
        eigene = [n for n in liste if n not in vergeben]
        aus.append(eigene if eigene else list(liste))
        vergeben.update(liste)
    return aus


def abdecken(listen: list[list[int]], gesamt: int,
             datei: Callable[[int], int] | None = None) -> list[list[int]]:
    """Every passage no entry names goes to the entry whose numbers lie closest.

    A plan that leaves a stretch of the text out would lose it for good, the writer only
    ever sees what its entry names. Entries without numbers stay as they are, they rest
    on the whole anyway. With ``datei`` a passage only goes to an entry that already draws
    on its file, a file no entry names falls back to the closest entry.
    """
    genannt = {n for liste in listen for n in liste}
    mit = [i for i, liste in enumerate(listen) if liste]
    if not mit:
        return [list(liste) for liste in listen]
    aus = [list(liste) for liste in listen]
    for n in range(1, gesamt + 1):
        if n in genannt:
            continue
        eigene = [] if datei is None else [i for i in mit if any(datei(m) == datei(n) for m in listen[i])]
        if eigene:
            naechster = min(eigene, key=lambda i: min(abs(n - m) for m in listen[i] if datei(m) == datei(n)))
        else:
            naechster = min(mit, key=lambda i: min(abs(n - m) for m in listen[i]))
        aus[naechster].append(n)
    return [sorted(liste) for liste in aus]


def _nummern(roh, hoechste: int) -> list[int]:
    if not isinstance(roh, list):
        return []
    # A model sometimes packs several numbers into one entry, "10, 16, 30".
    werte = [teil for wert in roh if not isinstance(wert, bool)
             for teil in (re.split(r"[,;]", wert) if isinstance(wert, str) else [wert])]
    aus: list[int] = []
    for wert in werte:
        treffer = _BEREICH.match(str(wert))
        if treffer:
            a, b = int(treffer.group(1)), int(treffer.group(2))
            if b < a:
                a, b = b, a
            kandidaten = range(a, min(b, a + MAP_RANGE_MAX - 1) + 1)
        else:
            einzeln = _EINZELN.match(str(wert))
            if not einzeln:
                continue
            kandidaten = [int(einzeln.group(1))]
        for n in kandidaten:
            if 1 <= n <= hoechste and n not in aus:
                aus.append(n)
            if len(aus) >= MAP_MAX_REFS:
                return aus
    return aus


# ── Die Planungsgrundlage ────────────────────────────────────────────────────

def hinweis(modus: str) -> str:
    """What the labels in the material mean, the same wording for every service."""
    if modus == THEMEN:
        return (
            f'The material is a list of topics, each written as "[{MARKE_THEMA}n] title: gist". '
            "Together they cover the whole text. Under \"refs\" name the labels of the "
            f'topics an entry draws on, copied exactly, such as "{MARKE_THEMA}3". Labels stand '
            "only under refs, never in a title, intro or any other text you write."
        )
    return (
        f'The material is the full text, cut into passages, each written as "[{MARKE_STELLE}n] text". '
        "Under \"refs\" name the passages an entry draws on by their labels, copied exactly. "
        f'Write neighbouring passages as one range such as "{MARKE_STELLE}12-{MARKE_STELLE}18" '
        "instead of listing them, and keep refs short: at most 10 entries. Name only labels "
        f"that appear in the material. A label is never a paragraph, article or page: § 45 or "
        f"S. 45 in the text is not {MARKE_STELLE}45, look up the label in front of the passage "
        "that holds it. Labels stand only under refs, never in a title, intro or any other "
        "text you write."
    )


def refs_beispiel(modus: str) -> str:
    """The refs of one entry in an answer example, in the labels of the material."""
    m = MARKE_THEMA if modus == THEMEN else MARKE_STELLE
    return f'["{m}12", "{m}14-{m}17"]'


def anfang_hinweis(modus: str) -> str:
    """The rule for the copied first words, empty over topics since they carry their own."""
    if modus == THEMEN:
        return ""
    return (f'Under "{ANFANG}" copy the first six to ten words of the text an entry draws on, '
            "exactly as they stand in the material, never a label. Empty when refs are empty.")


def anfang_beispiel(modus: str) -> str:
    """The first words field of one entry in an answer example, nothing over topics."""
    return "" if modus == THEMEN else f', "{ANFANG}": "..."'


@dataclass
class Grundlage:
    """What a planning call reads, and how its answer finds its way back to the text."""

    material: str
    modus: str
    themen: list[Thema]

    def stellen(self, refs, karte: Karte, anfang=None) -> list[int]:
        """The passage numbers behind the refs of one entry, moved to its copied first words."""
        if self.modus != THEMEN:
            nummern = karte.gueltig(refs)
            # Empty refs stay empty, an agenda slide or a slide without material asks for nothing.
            return karte.verankern(nummern, anfang) if nummern and anfang else nummern
        nach_nummer = {t.nummer: t for t in self.themen}
        aus: list[int] = []
        for n in _nummern(refs, len(self.themen)):
            for s in nach_nummer[n].stellen:
                if s not in aus:
                    aus.append(s)
        return aus


def themen_nachrichten(karte: Karte, teil: range, teile: int, nummer: int,
                       language: str, zweck: str,
                       hoechstens: int = MAP_MAX_TOPICS_PER_PART) -> list[dict]:
    """One part of the material boiled down to its topics, when the whole does not fit."""
    system = (
        "You map a text. The text is cut into labelled passages. List the topics this "
        f"text covers, in the order they appear, at most {hoechstens}, spread over the "
        "whole text to its last passage. "
        f"This is part {nummer} of {teile} of the material, other parts are mapped "
        "separately. For every topic give a short title, one sentence saying what the "
        "text states about it that names the concrete duties, deadlines and figures it gives, "
        f'and the passages it draws on by the labels in front of them, such as "{MARKE_STELLE}4" or '
        f'a range "{MARKE_STELLE}4-{MARKE_STELLE}7". A label is never a paragraph or page: § 4 in '
        f"the text is not {MARKE_STELLE}4, name the label of the passage that holds it. Under "
        '"start" copy the first six to ten words of the text the topic begins with, exactly as '
        "they stand, never the label. Every passage that carries content belongs to a topic. "
        f"Write titles and sentences in {language}. The material will be used for: {zweck}.\n"
        'Answer with one JSON object only: {"topics": [{"title": "...", "gist": "...", '
        f'"start": "...", "refs": ["{MARKE_STELLE}1", "{MARKE_STELLE}4-{MARKE_STELLE}7"]}}]}}'
    )
    return [{"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\n{karte.block(teil)}"}]


def parse_themen(raw: str | None, karte: Karte, erste_nummer: int,
                 hoechstens: int = MAP_MAX_TOPICS_PER_PART,
                 bereich: range | None = None) -> list[Thema]:
    """The topics out of one answer, numbered on from where the previous part stopped.

    The copied first words of a topic move its passages to where they really stand,
    looked up only inside ``bereich``, the part this answer read.
    """
    daten = _json_objekt(raw)
    roh = daten.get("topics") if isinstance(daten, dict) else None
    aus: list[Thema] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, dict):
            continue
        titel = " ".join(str(eintrag.get("title") or "").split())[:120]
        stellen = karte.verankern(karte.gueltig(eintrag.get(REFS)), eintrag.get(ANFANG),
                                  bereich=bereich)
        if not titel or not stellen:
            continue
        aus.append(Thema(nummer=erste_nummer + len(aus), titel=titel,
                         kern=" ".join(str(eintrag.get("gist") or "").split())[:300],
                         stellen=tuple(stellen)))
        if len(aus) >= hoechstens:
            break
    return aus


def themen_block(themen: list[Thema]) -> str:
    return "\n".join(f"[{MARKE_THEMA}{t.nummer}] {t.titel}: {t.kern}" for t in themen)


def grundlage(karte: Karte, window_tokens: int, *, language: str, zweck: str,
              frage: Callable[[list[list[dict]]], list[str | None]]) -> Grundlage:
    """The material a planning call reads: the full numbered text, or its topics.

    ``frage`` sends several calls at once and returns their raw answers in order, so
    each service keeps its own way of calling the model.
    """
    if len(karte.teile(window_tokens)) <= 1:
        return Grundlage(material=karte.block(), modus=STELLEN, themen=[])
    stuecke = karte.abschnitte(window_tokens)
    antworten = frage([themen_nachrichten(karte, bereich, len(stuecke), i + 1, language, zweck,
                                          hoechstens=anzahl)
                       for i, (bereich, anzahl) in enumerate(stuecke)])
    themen: list[Thema] = []
    for antwort, (bereich, anzahl) in zip(antworten, stuecke):
        themen.extend(parse_themen(antwort, karte, len(themen) + 1, hoechstens=anzahl,
                                   bereich=bereich))
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
