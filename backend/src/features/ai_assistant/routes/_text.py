"""Pure text handling for KI-Assistent answers: cleaning, splitting, comparing."""

import re
import unicodedata


# Repairs citations where the model closes the bracket too early.
_CITATION_FIX_TIME_RE = re.compile(r"\[(\d+)\]\s+(\d{1,2}:\d{2}(?::\d{2})?)")


_CITATION_FIX_PAGE_RE = re.compile(r"\[(\d+)\]\s+(S\.\s*\d+(?:[-,–]\s*\d+)*)")


# Drops empty 【…】 brackets, real citations and CJK text stay.
_STRAY_LENTICULAR_RE = re.compile(
    r"\s?【(?![^】]*(?:S\.\s*\d|\d{1,2}:\d{2}|[぀-鿿가-퟿]))[^】]*】"
)


def _sanitize_citations(text: str) -> str:
    """Repair malformed `[N] pos` citations and drop stray 【…】 placeholders."""
    text = _CITATION_FIX_TIME_RE.sub(r"[\1, \2]", text)
    text = _CITATION_FIX_PAGE_RE.sub(r"[\1, \2]", text)
    text = _STRAY_LENTICULAR_RE.sub("", text)
    return text


# Arrows between two steps out, they hide the verb.
_ARROW_CONNECTOR_RE = re.compile(r"[ \t]*(?:→|⟶|➔|➜|-->|->|=>)[ \t]*")


def _strip_arrow_connectors(text: str) -> str:
    """Drop arrow connectors, keeping one separating space."""
    return _ARROW_CONNECTOR_RE.sub(" ", text)


def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS or H:MM:SS for citation references."""
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


_TRANSCRIPT_LINE = re.compile(
    r"\[(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(\d{1,2}:\d{2}(?::\d{2})?)\]\s*(.+)"
)


def _parse_ts(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return parts[0] * 60 + parts[1]


def _norm_for_match(s: str) -> str:
    """Prepares text for the verbatim keyword comparison."""
    s = unicodedata.normalize("NFKC", s).casefold()
    for hy in ("‐", "‑", "‒", "–", "—", "−"):
        s = s.replace(hy, "-")
    return re.sub(r"\s+", " ", s).strip()


# Recognises a table-of-contents line by the dot leader before the page number.
_TOC_LEADER_RE = re.compile(r"(?:\.\s*){4,}\d{1,4}")


def _strip_toc_lines(text: str) -> str:
    """Drops lines that are table-of-contents entries."""
    if not text or "." not in text:
        return text
    return "\n".join(ln for ln in text.split("\n") if not _TOC_LEADER_RE.search(ln))


def _is_toc_chunk(content: str, *, min_chars: int = 20, max_kept_ratio: float = 0.4) -> bool:
    """True when a chunk is almost only a table of contents and therefore no evidence target."""
    raw = (content or "").replace(" ", "").replace("\n", "")
    if len(raw) < min_chars:
        return False
    kept = _strip_toc_lines(content).replace(" ", "").replace("\n", "")
    return len(kept) <= len(raw) * max_kept_ratio


# Guard against repetition loops, lines are compared by their prose.
_DEDUP_BRACKET_RE = re.compile(r"[\[【][^\]】]*[\]】]")


_DEDUP_MIN_KEY_LEN = 16


def _line_dedup_key(line: str) -> str:
    """Comparison form of a line: chips and bullets out, then normalise."""
    s = _DEDUP_BRACKET_RE.sub("", line)
    s = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)", "", s)
    return _norm_for_match(s)


class _RepetitionGuard:
    """Detects a repetition loop of the model across whole lines."""

    def __init__(self, max_repeats: int = 4, min_key_len: int = _DEDUP_MIN_KEY_LEN) -> None:
        self._counts: dict = {}
        self._max = max_repeats
        self._min = min_key_len

    def is_loop(self, line: str) -> bool:
        key = _line_dedup_key(line)
        if len(key) < self._min:
            return False
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] >= self._max


def _tail_repeats(buf: str, *, min_unit: int = 6, max_unit: int = 160,
                  repeats: int = 5, window: int = 2000) -> bool:
    """True when the end of the buffer repeats a short unit without a line break."""
    tail = buf[-window:]
    n = len(tail)
    for unit in range(min_unit, max_unit + 1):
        if unit * repeats > n:
            break
        seg = tail[-unit:]
        if seg.strip() and tail.endswith(seg * repeats):
            return True
    return False


# Folds a short unit repeated three times in a row.
_COLLAPSE_REPEAT_RE = re.compile(r"(.{6,160}?)(?:\1){3,}", re.DOTALL)


def _collapse_repeats(text: str) -> str:
    """Folds a unit repeated three or more times down to one copy."""
    if len(text) > 60000:
        return text
    return _COLLAPSE_REPEAT_RE.sub(lambda m: m.group(1), text)


def _dedup_repeated_lines(text: str) -> str:
    """Drops later duplicates of a content-bearing line."""
    seen: set = set()
    out: list[str] = []
    for line in text.split("\n"):
        key = _line_dedup_key(line)
        if len(key) >= _DEDUP_MIN_KEY_LEN:
            if key in seen:
                continue
            seen.add(key)
        out.append(line)
    return "\n".join(out)


# A page ("S. 6" / "S.6") or timestamp ("08:58" / "1:05:19") locator, optional leading pipe.
_SRC_LOCATOR_RE = re.compile(r"\|?\s*(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)\s*", re.IGNORECASE)


_LIST_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _is_pure_source_ref(line: str, names: list[str]) -> bool:
    """True when a line is only a source name plus a page or time reference."""
    s = _LIST_BULLET_RE.sub("", line.strip())
    if not s:
        return False
    low = s.lower()
    hit = next((nm for nm in names if nm and nm.lower() in low), None)
    if not hit:
        return False
    rest = low.replace(hit.lower(), " ")
    rest = _SRC_LOCATOR_RE.sub(" ", rest)
    rest = re.sub(r"[|,;:_\-\s]+", "", rest)
    return len(rest) <= 2


def _strip_source_list(text: str, source_filenames: list[str]) -> str:
    """Removes a source list written by the model together with its heading."""
    names: list[str] = []
    for f in source_filenames:
        if not f:
            continue
        names.append(f)
        stem = f.rsplit(".", 1)[0]
        if stem and stem != f:
            names.append(stem)
    if not names:
        return text
    lines = text.split("\n")
    is_ref = [_is_pure_source_ref(ln, names) for ln in lines]
    keep = [True] * len(lines)
    n = len(lines)
    i = 0
    while i < n:
        if not is_ref[i]:
            i += 1
            continue
        j, cnt, last = i, 0, i
        while j < n and (is_ref[j] or not lines[j].strip()):
            if is_ref[j]:
                cnt += 1
                last = j
            j += 1
        if cnt >= 2:
            for k in range(i, last + 1):
                keep[k] = False
            p = i - 1
            while p >= 0 and not lines[p].strip():
                p -= 1
            if p >= 0 and lines[p].strip().endswith(":") and len(lines[p].strip()) <= 40:
                keep[p] = False
        i = j
    return "\n".join(ln for ln, k in zip(lines, keep) if k).strip()


def _is_table_row(line: str) -> bool:
    """A Markdown table row: trimmed line starts and ends with a pipe."""
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _is_table_delim(line: str) -> bool:
    """A separator row of a Markdown table."""
    s = line.strip()
    return bool(s) and set(s) <= set("|-: ")


def _strip_tiny_tables(text: str) -> str:
    """Drops a table with fewer than two data rows when enough text remains."""
    lines = text.split("\n")
    keep = [True] * len(lines)
    n = len(lines)
    i = 0
    while i < n:
        if _is_table_row(lines[i]) and i + 1 < n and _is_table_delim(lines[i + 1]):
            j = i + 2
            data = 0
            while j < n and _is_table_row(lines[j]):
                data += 1
                j += 1
            if data < 2:
                for k in range(i, j):
                    keep[k] = False
            i = j
        else:
            i += 1
    remaining = "\n".join(ln for ln, k in zip(lines, keep) if k).strip()
    return remaining if len(remaining) >= 15 else text


# DE+EN filler — dropped before exact-match so only content words must line up.
_ATTR_STOP = frozenset((
    "der die das ein eine und oder ist hat war wer was wie wo mit von für auf aus bei "
    "den dem des als nach über vor bis wenn dass aber auch noch nur doch sehr wird sind "
    "kann mehr nicht sich gibt diese einer einem einen welche welcher welches dieser "
    "sein ihre über unter zwischen werden wurde "
    "the and or of is in to was that this for with on at by from as it be are were has "
    "had have not but so if then do does did what which who when where why how their "
    "there here than them they you are our its".split()
))


# Keep word characters and umlauts, allow at sign, dot and inner hyphen.
_TOKEN_RE = re.compile(r"[0-9A-Za-zÄÖÜäöüß][0-9A-Za-zÄÖÜäöüß@.\-]*")


def _significant_tokens(line: str) -> list[str]:
    """The distinguishing content words of a line."""
    s = re.sub(r"[*_`~#>]+", " ", line)
    out: list[str] = []
    for w in _TOKEN_RE.findall(s):
        wl = w.strip(".-").lower()
        if len(wl) >= 4 and wl not in _ATTR_STOP:
            out.append(wl)
    return out


_CLAUSE_SPLIT_RE = re.compile(r"[,;]")


def _clauses(line: str) -> list[str]:
    """The content-bearing clauses of a line, without the whole line."""
    if not _CLAUSE_SPLIT_RE.search(line):
        return []
    whole = line.strip()
    out: list[str] = []
    for part in _CLAUSE_SPLIT_RE.split(line):
        p = part.strip()
        if p and p != whole and len(_line_dedup_key(p)) >= _DEDUP_MIN_KEY_LEN and p not in out:
            out.append(p)
    return out


# A sentence boundary, digits behind it rule it out.
_SENT_BOUNDARY_RE = re.compile(r"[.!?]+\s+(?=[^\W\d_])")


def _is_abbreviation_end(prefix: str) -> bool:
    """Whether the final period ends an abbreviation or number instead of a sentence."""
    tok = prefix.rstrip(".!?").split()
    if not tok:
        return False
    # Strip brackets and quotes, inner periods stay.
    tok = re.sub(r"^\W+|\W+$", "", tok[-1])
    if not tok:
        return False
    if len(tok) == 1:
        return True
    if tok.isdigit():
        return True
    if "." in tok and len(tok) <= 4:
        return True
    if tok[0].isupper() and len(tok) <= 4:
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    """Splits prose into sentences for per-sentence evidence matching."""
    s = text.strip()
    if not s:
        return []
    out: list[str] = []
    start = 0
    for m in _SENT_BOUNDARY_RE.finditer(s):
        nxt = s[m.end()] if m.end() < len(s) else ""
        if not nxt.isupper():
            continue
        # End of the sentence text = end of the terminal marks (before the whitespace).
        cut = m.end()
        while cut > start and s[cut - 1].isspace():
            cut -= 1
        if _is_abbreviation_end(s[start:cut]):
            continue
        out.append(s[start:cut].strip())
        start = m.end()
    tail = s[start:].strip()
    if tail:
        out.append(tail)
    return out


_INLINE_CITE_STRIP_RE = re.compile(r"\s*[\[【][^\]】\n]*(?:#\s*\d|S\.\s*\d|\d{1,2}:\d{2})[^\]】\n]*[\]】]")


def _strip_inline_citation_chips(text: str) -> str:
    """Removes citation-shaped brackets from a line."""
    out = _INLINE_CITE_STRIP_RE.sub("", text)
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).rstrip()


def _context_snippet(page_text: str, term: str, max_chars: int = 700) -> str:
    """A short excerpt of the page around the marked term."""
    text = re.sub(r"\s+", " ", (page_text or "")).strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    low = text.lower()
    pos = low.find((term or "").lower().strip()) if term else -1
    if pos < 0:
        head = text[:max_chars].rsplit(" ", 1)[0]
        return head + " …"
    half = max_chars // 2
    start = max(0, pos - half)
    end = min(len(text), pos + len(term) + half)
    if start > 0:
        start = text.find(" ", start) + 1 or start
    if end < len(text):
        cut = text.rfind(" ", start, end)
        if cut > start:
            end = cut
    snippet = text[start:end].strip()
    return ("… " if start > 0 else "") + snippet + (" …" if end < len(text) else "")


def _term_appears_in_text(term: str, text_lower: str) -> bool:
    """Checks whether the term appears verbatim or as a word stem in the text."""
    t = term.lower().strip()
    if not t:
        return False
    if t in text_lower:
        return True
    stem_len = max(5, len(t) * 3 // 4)
    stem = t[:stem_len]
    return bool(re.search(r"\b" + re.escape(stem), text_lower))
