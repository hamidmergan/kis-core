"""Does a more distant chunk carry verbatim something the best one lacks?"""

import re

# This long a word has to be before its occurrence means anything.
_WORD_MIN_CHARS = 5
# A word above this share no longer distinguishes a spot.
_COMMON_SHARE = 0.15
# Below this many texts the share is meaningless, then rarity does not count.
_MIN_CORPUS = 8
# How many words the chunk must name that the best hit lacks.
_MIN_WORDS_AS_EVIDENCE = 2
# How many numbers of a line are looked up.
_MAX_LOOKUP_FIGURES = 3

# A number sequence, including the characters that occur inside numbers.
_FIGURE_RE = re.compile(r"\d[\d.:,/\-]*\d|\d")
# Characters that make a word checkable without carrying a digit.
_MARK_RE = re.compile(r"\S*[@§#]\S*")
_WORD_RE = re.compile(r"[^\W\d_]{%d,}" % _WORD_MIN_CHARS)


def figure_runs(text: str) -> set[str]:
    """All number-shaped sequences in the text, as whole sequences instead of pieces."""
    runs = {m.group(0).rstrip(".,:/-") for m in _FIGURE_RE.finditer(text)}
    for run in list(runs):
        for part in re.split(r"[-/]", run):
            if len(part) > 1 and (":" in part or "." in part):
                runs.add(part)
    runs |= {m.group(0).lower().strip(".,;:()[]") for m in _MARK_RE.finditer(text)}
    return runs


def _words(text: str) -> set[str]:
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


# Words are compared at the word start so inflection matches in both directions.
_STEM_CHARS = 6


def _stems(text: str) -> set[str]:
    return {w[:_STEM_CHARS] for w in _words(text)}


def _carries_word(stems: set[str], word: str) -> bool:
    return word[:_STEM_CHARS] in stems


def distinctive_tokens(line: str, corpus: list[str]) -> tuple[set[str], set[str]]:
    """The words and numbers of the line that only a minority of the material carries."""
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


def names_line_verbatim(line: str, chunk: str, corpus: list[str]) -> bool:
    """True when the chunk carries a rare number or two rare words of the line verbatim."""
    words, figures = distinctive_tokens(line, corpus)
    if figures & figure_runs(chunk):
        return True
    stems = _stems(chunk)
    return sum(_carries_word(stems, w) for w in words) >= _MIN_WORDS_AS_EVIDENCE


# A pin word ties a claim to a spot: long enough and rare in the material.
_PIN_MIN_CHARS = 9

# How rare a pin word has to be, distinctly tighter than the general threshold.
_PIN_SHARE = 0.005


def pin_words(line: str, corpus: list[str]) -> set[str]:
    """All pin words of the line, possibly empty."""
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
    """Whether this chunk carries the pin word verbatim."""
    return pin.lower() in (chunk or "").lower()


def lookup_figures(line: str, corpus: list[str]) -> list[str]:
    """The numbers of the line that are specific enough to look up."""
    _, figures = distinctive_tokens(line, corpus)
    worth = [f for f in figures if any(ch in f for ch in ":.-/") and len(f) >= 4]
    return sorted(worth, key=lambda f: (-len(f), f))[:_MAX_LOOKUP_FIGURES]


def adds_literal_evidence(line: str, chunk: str, primary: str, corpus: list[str]) -> bool:
    """True when the chunk names verbatim something the best hit lacks."""
    words, figures = distinctive_tokens(line, corpus)
    if not words and not figures:
        return False
    chunk_stems, primary_stems = _stems(chunk), _stems(primary)
    chunk_figs, primary_figs = figure_runs(chunk), figure_runs(primary)
    # One number is enough, it is the part a reader looks up.
    for f in figures:
        if f in chunk_figs and f not in primary_figs:
            return True
    # Words need two, rarity alone does not tell a term from a filler.
    missing = [w for w in words
               if _carries_word(chunk_stems, w) and not _carries_word(primary_stems, w)]
    return len(missing) >= _MIN_WORDS_AS_EVIDENCE
