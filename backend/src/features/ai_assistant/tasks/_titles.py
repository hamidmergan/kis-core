"""Der Anzeigename eines erzeugten Ergebnisses, aus dem Ergebnis selbst.

Frueher lag das unter ``language_training``, weil nur Uebungs-Saetze es brauchten.
Mindmap und Datentabelle benutzen jetzt dieselbe Logik, deshalb liegt sie hier
neutral. Der eine Unterschied zur alten Fassung: die Liste der schon vergebenen
Titel kommt als Uebergabewert herein. Vorher las das Modul sie selbst aus
``aia_exercise_sets``, und diese eine Tabelle passt fuer Mindmaps nicht.

Sprach-unabhaengig gebaut: nichts hier schaut sich Woerter an, die Aehnlichkeit
geht ueber Zeichenueberdeckung und die Normalisierung ueber Unicode-Kategorien.
"""

from loguru import logger

# Die Laenge, mit der die Titelspalten und die Oberflaeche rechnen.
MAX_TITLE_LEN = 120

# So viele Eintraege sieht der Titel-Aufruf, und so lang darf einer sein. Mehr
# Material macht den Titel nicht besser, nur den Aufruf teurer.
_MAX_ENTRIES = 10
_MAX_ENTRY_LEN = 160


def title_from_entries(client, model, entries: list[str], fallback: str,
                       avoid: list[str] | None = None) -> str:
    """Generate a short title from the actual entries so results from the same
    source get distinct titles.

    ``avoid`` lists titles the workspace already uses. It matters because this call is
    the retry after a clash: without it the model reaches for the document's name again,
    which is the very title that clashed. The entries are the only material given, so a
    title from here describes what the result is about rather than what the document is.
    """
    sauber = [str(e).strip() for e in entries if str(e or "").strip()]
    if not sauber:
        return fallback
    preview = "\n".join(f"- {e[:_MAX_ENTRY_LEN]}" for e in sauber[:_MAX_ENTRIES])
    avoid_rule = ""
    if avoid:
        avoid_rule = (
            " These titles are already taken and MUST NOT be used, not even with a single "
            "word changed, added or removed: " + "; ".join(t for t in avoid[:10] if t) + "."
        )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Provide a short, concise title (max 6 words) for this material "
                    "that reflects the concrete topic of the entries below. "
                    # Without this the model reaches past the entries for the subject of
                    # the course they come from, and every result of one document ends up
                    # with a variant of that one name.
                    "Name the specific thing the entries have in common, for example the "
                    "step, the activity or the material they are about. Do NOT name the "
                    "document, the lecture, the course or the field as a whole. "
                    "Respond in the same language as the entries. "
                    "Respond ONLY with the title, no quotation marks."
                    + avoid_rule
                )},
                {"role": "user", "content": f"Entries:\n{preview}"},
            ],
            temperature=0.7,
            # Generous budget: reasoning models spend tokens on thinking before the first
            # content token, and a 30-token cap left content empty -> silent fallback.
            max_tokens=400,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # First non-empty line only: with the larger budget a chatty model may add a
        # second line, and the title column is a single short line.
        t = next((ln.strip().strip('"\'') for ln in raw.splitlines() if ln.strip()), "")[:MAX_TITLE_LEN]
        if not t:
            logger.warning("Title: empty LLM response, falling back to {!r}", fallback)
        return t or fallback
    except Exception as e:
        logger.warning("Title generation failed ({}), falling back to {!r}", e, fallback)
        return fallback


# Above this similarity two titles read as the same one to a human. Measured against real
# titles from one document: a one-letter variant of the same title scores 0.99, while
# "… im Seminar: Passiv üben" against "… im Seminar" scores 0.85 and is clearly its own
# title. The threshold sits between the two. Substring containment is deliberately NOT a
# criterion: a longer, more specific title is exactly what we want to keep.
_SAME_TITLE_RATIO = 0.90


def is_title_taken(title: str, existing: list[str]) -> bool:
    """Whether ``title`` reads as one of ``existing`` to a human.

    Not an equality check. The model varies a title by a single letter and calls it new,
    which is how one workspace ended up with "Wissenschaftliche Arbeiten im Seminar" next
    to "Wissenschaftliches Arbeiten im Seminar".

    Language-agnostic: normalisation goes by Unicode category, similarity by character
    overlap. No word list anywhere.
    """
    from difflib import SequenceMatcher
    from src.services.aia_grammar_check import normalize

    want = normalize(title)
    if not want:
        return False
    for other in existing:
        have = normalize(other)
        if have and (want == have or SequenceMatcher(None, want, have).ratio() >= _SAME_TITLE_RATIO):
            return True
    return False


def next_free_counter(title: str, taken: list[str]) -> str:
    """``title (n)`` with the lowest n not yet used by this title's own family.

    Counting only exact matches was the bug behind two results both ending in "(2)": their
    bases differed by a letter, so neither saw the other. The family is therefore
    everything ``is_title_taken`` considers the same title, and ``normalize`` drops the
    bracketed counter, so a counted title lands in its own family.
    """
    used: set[int] = set()
    for other in taken:
        if not is_title_taken(title, [other]):
            continue
        tail = (other or "").rstrip().rsplit("(", 1)
        if len(tail) == 2 and tail[1].rstrip().endswith(")"):
            digits = tail[1].rstrip()[:-1].strip()
            if digits.isdigit():
                used.add(int(digits))
    n = 2
    while n in used:
        n += 1
    return f"{title} ({n})"


def resolve_title(client, model, taken: list[str], fallback: str, entries: list[str]) -> str:
    """The name a finished result gets.

    Built from the result's OWN entries rather than from the generation call. That call
    sees the whole document and therefore keeps naming the document, which is why every
    result from one script came out as a variant of its title.

    ``fallback`` is the title the generation call proposed; it is used only when the
    title call gives nothing back.

    Costs one model call, and a second one only when the first result still reads like a
    title the workspace already has.
    """
    fallback = (fallback or "").strip()
    if not entries:
        return fallback

    title = (title_from_entries(client, model, entries, fallback, avoid=taken) or "").strip()
    if not title:
        title = fallback
    if not title or not is_title_taken(title, taken):
        return title

    # Second attempt, this time naming the title it collided with.
    clashing = [t for t in taken if is_title_taken(title, [t])]
    retitled = (title_from_entries(client, model, entries, "", avoid=clashing + taken) or "").strip()
    if retitled and not is_title_taken(retitled, taken):
        return retitled

    return next_free_counter(title, taken)
