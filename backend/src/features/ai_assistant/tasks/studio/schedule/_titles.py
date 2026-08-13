"""Title normalization plus fuzzy matching for schedule deduplication."""

from difflib import SequenceMatcher


def _find_merge_target(entries: list[dict], due_date, precision: str,
                       title: str, ref: dict) -> dict | None:
    """Der Eintrag, in den dieser Fund gehoert, oder None fuer einen neuen.

    Mit Datum bindet der Tag, dazu reicht ein aehnlicher Titel. Ohne Datum faellt der
    Tag als Schutz weg, dort gilt der strengere Titelvergleich UND zusaetzlich der
    Wortlaut: derselbe Satz gehoert in denselben Eintrag, auch wenn das Modell ihn
    zweimal verschieden benannt hat.

    Die Genauigkeit muss ebenfalls passen. "im Juli" und der 01.07. teilen sich zwar den
    Sortierpunkt, sind aber nicht dieselbe Aussage, und der eine darf den anderen nicht
    schlucken.
    """
    same_title = _fuzzy_same_undated if due_date is None else _fuzzy_same
    for e in entries:
        if e.get("due_date") != due_date:
            continue
        if (e.get("date_precision") or "day") != (precision or "day"):
            continue
        if same_title(title, e.get("title") or ""):
            return e
        if due_date is None and _same_source_text(ref.get("raw_quote") or "",
                                                  e.get("source_refs") or []):
            return e
    return None


def _norm_quote(text: str) -> str:
    """Vergleichsform einer Fundstelle: klein, ein Leerzeichen zwischen den Woertern."""
    return " ".join(str(text or "").lower().split())


def _same_source_text(quote: str, refs: list[dict]) -> bool:
    """Haengt genau dieser Wortlaut schon an einem Eintrag?

    Derselbe Kursplan steht in mehreren PDFs des Semesters, die Zeile
    "Praesentationen (online) | waehrend der Pruefungswochen (wird individuell
    vereinbart)" kommt dann Wort fuer Wort mehrfach an. Ob zwei TITEL dasselbe meinen,
    ist Auslegung und das Modell entscheidet mal so und mal so. Ob zwei Fundstellen
    derselbe Satz sind, ist dagegen nachpruefbar. Deshalb schlaegt der Wortlaut den
    Titel: gleicher Text heisst gleicher Eintrag, egal wie er genannt wurde.

    Nur fuer Eintraege ohne Datum gedacht. Mit Datum bindet ohnehin schon der Tag.
    """
    key = _norm_quote(quote)
    if not key:
        return False
    return any(_norm_quote(r.get("raw_quote") or "") == key for r in refs)


def _norm_title(t: str) -> str:
    """Lower-case + whitespace/separator collapse. Language-agnostic."""
    raw = str(t or "").lower()
    for sep in "/:-_()[]{}|\"'":
        raw = raw.replace(sep, " ")
    return " ".join(raw.split())


def _token_overlap(a: str, b: str) -> float:
    """Fraction of shorter token set that also appears in the longer one.
    Handles stem-like matches by simple prefix comparison for 5+ char tokens.
    Digit-only tokens (years, day numbers, month numbers) are excluded: they
    carry no semantic signal about the event itself.
    Language-agnostic.
    """
    ta = set(t for t in _norm_title(a).split() if len(t) >= 3 and not t.isdigit())
    tb = set(t for t in _norm_title(b).split() if len(t) >= 3 and not t.isdigit())
    if not ta or not tb:
        return 0.0
    small, large = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    hits = 0
    for t in small:
        if t in large:
            hits += 1
            continue
        # prefix match for stem variants: 'sprechstunde' matches 'sprechstunden'
        if len(t) >= 5 and any(
            (t.startswith(x[:5]) or x.startswith(t[:5])) for x in large
        ):
            hits += 1
    return hits / len(small)


def _fuzzy_same_undated(a: str, b: str) -> bool:
    """Strengerer Vergleich fuer Eintraege ohne Datum.

    Beim Zusammenfuehren schuetzt sonst das Datum vor Verwechslung, zwei Eintraege
    kommen nur zusammen, wenn sie am selben Tag liegen. Eintraege ohne Datum haben
    diesen Schutz nicht, sie teilen sich alle dasselbe leere Datum. Die Wortueberdeckung
    reicht dort nicht: sie haelt "Praesentation: online" und "Online-Praesenz:
    Peer-Review" fuer dasselbe, weil beide Woerter treffen ("online" woertlich,
    "praesentation" ueber den Wortstamm von "praesenz"). Gemessen an echten Titeln
    liegen falsche Paare bei 0,30 bis 0,38 und richtige bei 0,77 bis 0,97, deshalb
    bleibt hier nur der Vergleich Zeichen fuer Zeichen.
    """
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    return SequenceMatcher(None, na, nb).ratio() >= 0.75


def _fuzzy_same(a: str, b: str) -> bool:
    """Merge candidate and existing entry if titles are similar by EITHER
    character-level similarity (difflib >= 0.75) OR content-token overlap (>= 0.7).
    Both are language-agnostic.
    """
    na, nb = _norm_title(a), _norm_title(b)
    if not na or not nb:
        return False
    if SequenceMatcher(None, na, nb).ratio() >= 0.75:
        return True
    if _token_overlap(a, b) >= 0.7:
        return True
    return False
