"""Drops exercises this workspace already has.

The context sweep in ``_context_budget`` makes two runs read different material, which
makes repetition unlikely. It cannot make it impossible: the same fact can be asked from
two different pages, and a document read a second time comes round to the same pages
again. Uniqueness therefore has to be decided on the finished items, not hoped for from
the context.

It has to happen AFTER generation, not in the prompt. Listing the existing exercises in
the prompt was built and reverted once already (see ``_variation``): fed back in they act
as few-shot material and the model copies them verbatim, which is the opposite of the
intent.

Why an exact comparison and not a fuzzy one like ``is_title_taken``. Measured over the
9,908 same-workspace pairs of exercises in the database:

* 99 pairs are the same task. All of them are exactly equal once ``normalize`` has folded
  case, quotes and punctuation, e.g. ``Im Vorgangspassiv wird das Hilfsverb 'sein'
  verwendet.`` against the same sentence with double quotes.
* every fuzzy threshold tried on top of that produced false positives, because exercises
  of one tool share their instruction line and their sentence frame. ``Die Studierenden
  stellen die Forschungsfrage`` and ``Die Studierenden schreiben die Forschungsfrage``
  are two different exercises with two different answers and score 0.949 on characters.
  Comparing the backs as well does not separate them either, since those differ by one
  word too.

A title has no such boilerplate, which is why the fuzzy comparison is right there and
wrong here. Same reason there is no word list anywhere in this module: ``normalize`` goes
by Unicode category, so the comparison holds in any language.
"""

from src.services.aia_grammar_check import normalize


def item_key(front: str) -> str:
    """Comparison form of an exercise: its front, normalised. Empty when unusable."""
    return normalize(front or "")


def drop_repeats(items: list[dict], existing: list[str]) -> tuple[list[dict], int]:
    """Return the items that are new, plus how many were dropped.

    ``existing`` are the fronts the workspace already has for this tool. Items are also
    compared against each other, so one call cleans both the repeats of earlier sets and
    the ones inside this set. Order is preserved, the first occurrence wins.

    An item without a usable front is kept: it is the generators' business to reject
    those, and dropping it here would hide the problem behind a duplicate count.
    """
    seen = {key for key in (item_key(f) for f in existing) if key}
    kept: list[dict] = []
    dropped = 0
    for item in items:
        key = item_key(item.get("front", ""))
        if not key:
            kept.append(item)
            continue
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(item)
    return kept, dropped


def seen_by_user(user_id: int | None, tool: str) -> list[str]:
    """Die Vorderseiten, die DIESE Person in diesem Werkzeug schon bekommen hat.

    Nach Person und nicht nach Kursraum: seit es den Vorrat gibt, ist eine Aufgabe, die
    jemand anderes erzeugt hat, fuer diese Person neu und soll ihr angeboten werden. Nur
    was sie selbst schon hatte, ist eine Wiederholung.

    Ein fehlgeschlagener Lesevorgang heisst: der Satz entsteht ohne Filter, so wie vor
    diesem Modul. Den Filter zu verlieren kostet eine wiederholte Aufgabe, den Auftrag
    scheitern zu lassen kostet den ganzen Satz.
    """
    if not user_id:
        return []
    from src import database as db
    try:
        return db.seen_fingerprints(user_id, tool)
    except Exception:  # noqa: BLE001
        return []


__all__ = ["item_key", "drop_repeats", "seen_by_user"]
