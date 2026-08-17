"""Does a further-away chunk carry, word for word, something the best one lacks?

Citation chips are picked by cosine distance, and an ADDITIONAL chip must sit within a
small relative delta of the closest one. That gate exists for a good reason (a clearly
best source must not collect on-topic near-misses) but it is blind to the one thing a
reader checks: whether the cited passage actually CONTAINS what the sentence claims.

Measured on a real course: the slide stating "Wöchentliche Sprechstunde (Mittwoch
17:30-18:30 Uhr)" sat at distance 0.501 while a transcript segment that merely mentions
office hours sat at 0.394 and took the only chip. Same shape for "10 Minuten
Fragerunde/Diskussion" and for a mentor's e-mail address: the passage that states the
fact loses to the passage that talks around it, because talking around something at
length is what embeddings reward.

What counts as evidence is measured, never listed: a token is distinctive when FEW of
the retrieved candidates for this very line carry it. No word lists, no per-document
tuning, nothing about any particular subject — in a statute the distinctive token is a
section number, on a chemistry slide a formula.
"""

import re
from typing import Optional

# A word must be this long before its presence means anything. Shorter ones ("Uhr",
# "Plan", "Teil") ride along in almost any German sentence.
_WORD_MIN_CHARS = 5
# A token carried by more than this share of the corpus cannot tell one passage from
# another.
_COMMON_SHARE = 0.15
# Below this many texts the share above is meaningless (with three texts every token is
# either on 33% or more of them), so rarity is not required. Rarity wants a CORPUS, not a
# handful: measured against only the ten candidates for one line, the filler adverb
# "insgesamt" looked as distinctive as "Fragerunde" and earned a passage a chip it had no
# business getting.
_MIN_CORPUS = 8
# How many distinct words the chunk must state that the closest passage does not. One is
# not enough (see adds_literal_evidence); a figure needs no company at all.
_MIN_WORDS_AS_EVIDENCE = 2
# How many figures of one line are looked up in the material. A sentence listing eight
# dates is a table, and one lookup per date would hang the whole table under it.
_MAX_LOOKUP_FIGURES = 3

# A figure run: starts with a digit and continues through digits and the punctuation that
# lives INSIDE numbers — clock times, dates, ranges, section numbers.
_FIGURE_RE = re.compile(r"\d[\d.:,/\-]*\d|\d")
# Marks that make a token checkable without carrying a digit: an address, a section sign,
# a hash. Compared whole, like figures.
_MARK_RE = re.compile(r"\S*[@§#]\S*")
_WORD_RE = re.compile(r"[^\W\d_]{%d,}" % _WORD_MIN_CHARS)


def figure_runs(text: str) -> set[str]:
    """Every number-shaped run in ``text``, keeping its shape.

    Whole runs, never substrings: "17:30" must not answer for the "30" of "30 Minuten",
    which is exactly how a citation for an unsourced total landed on a clock time.

    A range is ALSO indexed by its ends, because the two sides meet written apart as often
    as together: the slide says "17:30-18:30 Uhr", the sentence says "von 17:30 bis 18:30".
    Only structured ends join (a time, a date), never a bare digit, so "6-7 Seiten" cannot
    be answered by any stray 7 on another page.
    """
    runs = {m.group(0).rstrip(".,:/-") for m in _FIGURE_RE.finditer(text)}
    for run in list(runs):
        for part in re.split(r"[-/]", run):
            if len(part) > 1 and (":" in part or "." in part):
                runs.add(part)
    runs |= {m.group(0).lower().strip(".,;:()[]") for m in _MARK_RE.finditer(text)}
    return runs


def _words(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


# Words are compared on their first characters, not as substrings, so inflection matches
# in BOTH directions: a substring test finds "Sprechstunde" inside "Sprechstunden" but
# not "Mittwoch" inside "mittwochs", and that asymmetry made a transcript segment look
# like it carried something the slide lacked when the slide said the very same word.
# Over-matching here is the safe direction: it makes a token look less distinctive and
# more likely already covered, i.e. fewer extra chips, never more.
_STEM_CHARS = 6


def _stems(text: str) -> set[str]:
    return {w[:_STEM_CHARS] for w in _words(text)}


def _carries_word(stems: set[str], word: str) -> bool:
    return word[:_STEM_CHARS] in stems


def distinctive_tokens(line: str, corpus: list[str]) -> tuple[set[str], set[str]]:
    """The line's (words, figures) that only a MINORITY of ``corpus`` carries.

    ``corpus`` should be everything the answer was written from — the chunks in the
    model's context — not just the handful retrieved for this one line. The yardstick is
    then the material actually in play, and it is large enough for "common" to mean
    something: measured against ten candidates alone, the filler adverb "insgesamt"
    looked as distinctive as "Fragerunde" and earned a passage a chip it had not earned.
    """
    words = _words(line)
    figures = figure_runs(line)
    if len(corpus) < _MIN_CORPUS:
        return words, figures
    stems = [_stems(c) for c in corpus]
    figs = [figure_runs(c) for c in corpus]
    limit = len(corpus) * _COMMON_SHARE
    rare_words = {w for w in words if sum(_carries_word(s, w) for s in stems) <= limit}
    rare_figs = {f for f in figures if sum(f in fs for fs in figs) <= limit}
    return rare_words, rare_figs


# Ein PIN-WORT ist das eine Wort, an dem eine Aussage haengt: lang genug, um etwas zu
# bedeuten, und im Material so selten, dass es auf eine Stelle zeigt. Traegt der beste
# Treffer es, muss jeder WEITERE Chip es auch tragen — sonst belegt er die Aussage nicht,
# sondern nur ihr Thema.
#
# Der gemeldete Fall: zu "nach der Behandlung von affinen Chiffren bleibt noch Zeit fuer
# eine Fragestunde" standen drei Chips. Der erste traf die Stelle mit der Fragestunde. Die
# anderen beiden hingen an der NEBENSACHE: einer an "dann kommt hier die affine Chiffre
# dran" (es ging dort um den Klausurstoff), einer an einer Aufzaehlung von
# Verschluesselungsverfahren. Beide sagen zur Fragestunde nichts.
#
# Neun Zeichen, gemessen: kuerzer geraten Hilfsverben und Wortteile hinein, die in DIESEM
# Material zufaellig selten sind ("wurden", "stellt" — letzteres traf mitten in
# "hochgestellt"). Ein langes deutsches Wort ist fast immer ein Inhaltswort.
_PIN_MIN_CHARS = 9

# Wie selten. Ein halbes Prozent des Materials, mindestens aber ein Vorkommen: das Wort
# faellt also praktisch an einer Stelle. Bewusst viel enger als ``_COMMON_SHARE``, das nur
# entscheidet, ob ein Wort ueberhaupt etwas unterscheidet.
_PIN_SHARE = 0.005


def pin_words(line: str, corpus: list[str]) -> set[str]:
    """ALLE Pin-Woerter der Zeile, moeglicherweise leer.

    Eine MENGE, nicht das eine seltenste: mehrere Woerter kommen im Material gleich oft
    vor, naemlich einmal, und dann waere die Wahl reine Willkuer. Gemessen am gemeldeten
    Fall — "In einer Aufzeichnung ... wird erwaehnt ... Fragestunde" — trugen
    "aufzeichnung", "fragestunde" und "behandelt" alle die Haeufigkeit eins, und der Zufall
    griff nach "aufzeichnung". Damit haette ein Chip ueber die AUFNAHME als Beleg fuer die
    FRAGESTUNDE durchgereicht.

    Wer die Menge einschraenkt, ist der beste Treffer: nur seine Pin-Woerter zaehlen (siehe
    Aufrufer). Ein Wort, das er selbst nicht traegt, sagt nichts darueber, was ein zweiter
    Beleg tragen muss.

    ``corpus`` ist alles, woraus die Antwort geschrieben wurde. Ohne genug Material laesst
    sich Seltenheit nicht messen, dann gibt es keine Pin-Woerter und alles bleibt wie
    bisher."""
    if len(corpus) < _MIN_CORPUS:
        return set()
    lows = [c.lower() for c in corpus]
    limit = max(1.0, len(corpus) * _PIN_SHARE)
    raus = set()
    for w in _words(line):
        if len(w) < _PIN_MIN_CHARS:
            continue
        df = sum(1 for c in lows if w in c)
        if 0 < df <= limit:
            raus.add(w)
    return raus


def carries_pin(pin: str, chunk: str) -> bool:
    """Ob dieser Chunk das Pin-Wort woertlich traegt."""
    return pin.lower() in (chunk or "").lower()


def lookup_figures(line: str, corpus: list[str]) -> list[str]:
    """The figures of ``line`` specific enough to go looking for, most specific first.

    Only STRUCTURED figures qualify — a clock time, a date, a range, a section number.
    A bare count ("20 Minuten", "7 Seiten") matches half a document and would drag in
    whatever happens to carry that digit. On top of that the figure has to be rare in
    ``corpus``, so a year that stands on every second page is not looked up either.

    Capped: a line listing eight dates is a table, and a lookup per date would put the
    whole table under one sentence.
    """
    _, figures = distinctive_tokens(line, corpus)
    worth = [f for f in figures if any(ch in f for ch in ":.-/") and len(f) >= 4]
    return sorted(worth, key=lambda f: (-len(f), f))[:_MAX_LOOKUP_FIGURES]


def adds_literal_evidence(line: str, chunk: str, primary: str, corpus: list[str]) -> bool:
    """True if ``chunk`` states a distinctive part of ``line`` that ``primary`` does not.

    This is what earns a chunk a chip past the relative distance gate. It never removes a
    chip and never overrides the absolute gate — a passage still has to be on topic; it
    only stops the closest passage from being the ONLY one allowed to be right.
    """
    words, figures = distinctive_tokens(line, corpus)
    if not words and not figures:
        return False
    chunk_stems, primary_stems = _stems(chunk), _stems(primary)
    chunk_figs, primary_figs = figure_runs(chunk), figure_runs(primary)
    # ONE figure is enough. A time, a date, a page count or a section number is the part of
    # a claim a reader goes and checks, and it is either there or it is not.
    for f in figures:
        if f in chunk_figs and f not in primary_figs:
            return True
    # Words need TWO. Rarity cannot tell a technical term from a filler adverb on its own:
    # "insgesamt" sits in a few percent of a real course's chunks, exactly like
    # "Fragerunde", and on its own it earned a passage a chip it had not earned. Two
    # distinct words that the closest passage is missing is no longer a coincidence.
    missing = [w for w in words
               if _carries_word(chunk_stems, w) and not _carries_word(primary_stems, w)]
    return len(missing) >= _MIN_WORDS_AS_EVIDENCE
