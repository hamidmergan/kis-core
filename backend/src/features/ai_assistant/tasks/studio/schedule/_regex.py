"""Regex-based date extraction (DE + EN + ISO) plus 'to-be-arranged' phrases."""

import re


# German + ISO + mixed patterns. Captures anchored date strings so the LLM
# only has to classify, not find.
_MONTH_DE = (
    "januar|februar|märz|maerz|april|mai|juni|juli|august|"
    "september|oktober|november|dezember|jan|feb|mär|mar|apr|"
    "jun|jul|aug|sep|sept|okt|nov|dez"
)
_MONTH_EN = (
    "january|february|march|april|may|june|july|august|"
    "september|october|november|december|jan|feb|mar|apr|"
    "jun|jul|aug|sep|sept|oct|nov|dec"
)

# German shorthand: same DD.MM., multiple years, slash-separated.
# E.g. "Zwischenberichte: 30.04.2026/2027/2028/2029" -> 4 separate dates.
# Whitespace around the slashes is tolerated ("30.06.2030 / 2031 / 2032").
# Expanded into one candidate per year by the candidate scanner.
_MULTI_YEAR_SHORTHAND = re.compile(
    r"\b(?P<dm>\d{1,2}\.\d{1,2}\.)(?P<years>\d{4}(?:\s*/\s*\d{4})+)\b"
)

_DATE_PATTERNS_WITH_YEAR = [
    # DD.MM.YYYY
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\b"),
    # YYYY-MM-DD (ISO)
    re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b"),
    # D. Month YYYY (German), e.g. "15. Juli 2026"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\s+\d{{4}})\b", re.IGNORECASE),
    # D.Month.YYYY, e.g. "03.Juli.2026". Ohne diese Zeile griff nur die jahrlose Form
    # darunter, das Jahr fiel weg und der Termin landete im laufenden Jahr.
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE})\.\s*\d{{4}})\b", re.IGNORECASE),
    # Month D, YYYY (English), e.g. "July 15, 2026"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}},\s*\d{{4}})\b", re.IGNORECASE),
]

# Monat mit Jahr, ohne Tag: "06.2026". Der Monat muss 1 bis 12 sein, das prueft
# _normalize_month_date. Vierstellig hinten haelt Gliederungsnummern draussen: "3.6.26"
# faellt hier nicht rein, das beurteilt das Modell mit dem Zusammenhang.
_DATE_PATTERNS_MONTH_ONLY = [
    re.compile(r"\b(?P<date>\d{1,2}\.\d{4})\b"),
]

_DATE_PATTERNS_YEARLESS = [
    # DD.MM. (German short, no year), e.g. "03.07." or "3.7."
    re.compile(r"\b(?P<date>\d{1,2}\.\d{1,2}\.)(?!\d)"),
    # D. Month (German, no year), e.g. "15. Juli"
    re.compile(rf"\b(?P<date>\d{{1,2}}\.\s*(?:{_MONTH_DE}))(?!\s+\d{{4}})\b", re.IGNORECASE),
    # Month D (English, no year), e.g. "July 15"
    re.compile(rf"\b(?P<date>(?:{_MONTH_EN})\s+\d{{1,2}})(?!,?\s*\d{{4}})\b", re.IGNORECASE),
]

# "Date not yet fixed" patterns: the event is real but happens at a time still
# to be negotiated. We surface these so the schedule shows them as a separate
# 'to be arranged' block in the UI.
#
# Diese Liste ist NICHT die Erkennung, sie ist nur deren schneller Weg. Sie kennt
# Deutsch und Englisch und kostet nichts. Jeder Chunk, in dem sie nichts findet, geht
# in _discover.py an das Modell, das die Stelle in jeder Sprache und in jeder
# Formulierung lesen kann. Die Liste darf deshalb luecken haben, sie zu erweitern
# bringt nur Tempo, nie Abdeckung.
#
# Deshalb stehen hier nur eindeutige Wendungen. Die blossen Kuerzel TBA, TBD und TBC
# standen bis zum 13.08.2026 mit drin und haben genau einen falschen Eintrag gebaut:
# in "Online-Praesenz: tba, mgl. Schreibwerkstatt, Poster | 27.06.2026" meint das "tba"
# den offenen INHALT der Zeile, das Datum steht daneben. Ein Kuerzel allein sagt nicht,
# WAS offen ist, das entscheidet der Satz drumherum. Solche Stellen beurteilt das
# Modell, es sieht den ganzen Chunk. Am echten Kursplan nachgemessen: es findet
# "Klausur | TBA" und "Abgabe | TBD" weiterhin und laesst die Themen-Zeile stehen.
_TBD_PATTERNS = [
    re.compile(
        r"(?P<phrase>nach\s+(?:individueller\s+)?(?:Vereinbarung|Absprache)"
        r"|Terminabsprache"
        r"|Termin\s+(?:wird|werden)\s+vereinbart"
        r"|zeitlich\s+nach\s+Absprache"
        r"|Datum\s+nach\s+Absprache"
        r"|to\s+be\s+(?:announced|decided|confirmed))",
        re.IGNORECASE,
    ),
]


# Spaltengrenze in einer Textzeile: ein Strich, ein Tabulator oder mehrere Leerzeichen.
# Der Chunker gibt Tabellen genau so aus. Reine Layout-Regel, sie braucht keine Sprache.
_COLUMN_GAP = re.compile(r"[|\t]|   ")


def _date_in_neighbouring_column(text: str, start: int, end: int) -> bool:
    """Steht in derselben Zeile ein Datum, aber in einer anderen Spalte?

    Dann traegt die Zeile ihr Datum bereits, und ein "tba" darin meint den offenen
    INHALT der Zeile, nicht ihren offenen Termin. Genau daran ist der Zeitplan bisher
    gescheitert: "Online-Praesenz: tba, mgl. Schreibwerkstatt | 27.06.2026, 10:00 Uhr".

    Im Fliesstext greift die Regel nicht, dort fehlt die Spaltengrenze. Ein Transkript
    hat oft gar keinen Zeilenumbruch, ein Datum weiter hinten im selben Absatz darf den
    offenen Termin also nicht abraeumen.
    """
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    phrase_start, phrase_end = start - line_start, end - line_start
    for date_start, date_end, _raw, _has_year, _prec in _date_candidates_in_text(line):
        if date_start >= phrase_end:
            gap = line[phrase_end:date_start]
        elif date_end <= phrase_start:
            gap = line[date_end:phrase_start]
        else:
            continue
        if _COLUMN_GAP.search(gap):
            return True
    return False


# Zwei Daten dicht beieinander in derselben Zeile sind meist EINE Zeitspanne
# ("28.09.2026 bis 02.11.2026"). Welches Wort dazwischen steht, ist sprachabhaengig und
# wird darum nicht geprueft, nur der Abstand und was dort NICHT stehen darf. Der Regex
# schlaegt die Spanne nur vor, bestaetigen muss sie die Klassifikation.
_RANGE_MAX_GAP = 15

# Ein Komma, ein Semikolon, ein Schraegstrich zwischen zwei Daten heisst Aufzaehlung,
# nicht Spanne. Das gilt sprachuebergreifend.
_LIST_SEPARATORS = frozenset(",;/&+")


def _looks_like_range(text: str, end_of_first: int, start_of_second: int) -> bool:
    """Verbindet der Text zwischen zwei Daten sie zu einer Zeitspanne?

    Geprueft wird nur, was ohne Sprachkenntnis entscheidbar ist. Ein Zeilenumbruch oder
    eine Spaltengrenze trennt zwei Tabellenzeilen, eine Ziffer dazwischen ist ein
    drittes Datum, ein blosses Komma ist eine Aufzaehlung, und gar nichts dazwischen
    sind zwei Spalten ohne Trennzeichen.

    Mehrfache Leerzeichen zaehlen hier NICHT als Spaltengrenze: in einer Tabellenzelle
    steht "28.09.2026    bis    02.11.2026" mit weiten Abstaenden, das Wort dazwischen
    gehoert trotzdem zur selben Zelle.
    """
    if not 0 < start_of_second - end_of_first <= _RANGE_MAX_GAP * 4:
        return False
    gap = text[end_of_first:start_of_second]
    if "\n" in gap or "|" in gap or "\t" in gap:
        return False
    if any(ch.isdigit() for ch in gap):
        return False
    kern = " ".join(gap.split())
    if not kern or len(kern) > _RANGE_MAX_GAP:
        return False
    if all(ch in _LIST_SEPARATORS for ch in kern):
        return False
    return True


def _date_candidates_in_text(text: str) -> list[tuple[int, int, str, bool, str]]:
    """Return list of (start_index, end_index, matched_string, has_year, precision).

    precision ist "day" oder "month". "month" heisst, im Text stand nur ein Monat mit
    Jahr ("06.2026"), es gibt dort keinen Tag zu holen.

    Year-full matches win over year-less at overlapping positions.
    """
    found: list[tuple[int, int, str, bool, str]] = []
    for pat in _DATE_PATTERNS_WITH_YEAR:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True, "day"))
    for pat in _DATE_PATTERNS_MONTH_ONLY:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), True, "month"))
    for pat in _DATE_PATTERNS_YEARLESS:
        for m in pat.finditer(text):
            found.append((m.start(), m.end(), m.group("date"), False, "day"))
    # Deduplicate: prefer has_year=True, then longer span, then earliest start.
    # Der laengere Treffer gewinnt auch gegen den Monat: in "03.07.2026" steckt
    # "07.2026", gemeint ist aber das ganze Datum.
    found.sort(key=lambda t: (t[0], not t[3], -(t[1] - t[0])))
    result: list[tuple[int, int, str, bool, str]] = []
    last_end = -1
    for s, e, d, hy, prec in found:
        if s >= last_end:
            result.append((s, e, d, hy, prec))
            last_end = e
    return result
