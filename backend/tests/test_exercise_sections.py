"""Equally sized numbered sections so all sources get their turn."""

from src.features.ai_assistant.tasks.language_training._context import (
    QuelleContext,
    build_source_context,
    coverage_rule,
    per_section_quota,
)


def _chunks(source_id, n_pages, chars):
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, n_pages + 1)]


def _install(monkeypatch, sizes, budget=250000):
    """Fake workspace: ``sizes`` maps filename -> (pages, chars per page)."""
    by_uuid = {}
    by_id = {}
    for i, (name, (pages, chars)) in enumerate(sizes.items(), start=1):
        source = {"id": i, "filename": name, "workspace_id": 1}
        by_uuid[f"u{i}"] = source
        by_id[i] = _chunks(i, pages, chars)
    monkeypatch.setattr("src.database.get_aia_source", lambda u: by_uuid.get(u))
    monkeypatch.setattr("src.database.get_chunks_by_source", lambda sid: by_id.get(sid, []))
    # Every call is a first run, nothing is written back.
    monkeypatch.setattr("src.database.get_context_cursors", lambda w, s, t: [])
    monkeypatch.setattr("src.database.set_context_cursors", lambda w, s, t, c: None)
    monkeypatch.setattr("src.database.get_context_rotation", lambda w, t: None)
    monkeypatch.setattr("src.database.set_context_rotation", lambda w, t, s: None)
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks._context_budget.exercise_context_budget",
        lambda count: budget)
    return list(by_uuid)


def _block_sizes(ctx):
    return {label: len(block) for block, label
            in ((b, next(l for l in ctx.source_by_name if l in b.split("\n")[0]))
                for b in ctx.context.split("\n\n"))}


# --- the quota ---------------------------------------------------------------

def test_the_quota_is_the_share_each_section_gets():
    # The user's own arithmetic: 5 sections, 5 entries -> 1 each, 10 -> 2, 15 -> 3.
    assert per_section_quota(5, 5) == 1
    assert per_section_quota(5, 10) == 2
    assert per_section_quota(5, 15) == 3


def test_fewer_entries_than_sections_still_asks_for_one():
    # Integer division would say zero, which reads as "this section is optional".
    assert per_section_quota(5, 2) == 1


# --- equal sections ----------------------------------------------------------

def test_every_source_keeps_its_own_length(monkeypatch):
    """Nothing is levelled down any more, a long source stays long."""
    uuids = _install(monkeypatch, {
        "lang.webm": (120, 500),   # 60k
        "kurz.pdf": (12, 500),     # 6k
    })
    ctx = build_source_context(uuids, "quiz", count=6)
    sizes = _block_sizes(ctx)
    assert sizes["lang.webm"] > sizes["kurz.pdf"] * 5, sizes


def test_the_tail_falls_away_once_the_budget_is_full(monkeypatch):
    uuids = _install(monkeypatch, {
        "erste.pdf": (60, 500),    # 30k
        "zweite.pdf": (60, 500),
        "dritte.pdf": (60, 500),
    }, budget=32000)
    ctx = build_source_context(uuids, "quiz", count=6)
    assert list(ctx.sections.values()) == ["erste.pdf"]


def test_the_label_names_only_the_sources_that_made_it(monkeypatch):
    """Two sources fell away, the label must not still promise three."""
    uuids = _install(monkeypatch, {
        "erste.pdf": (60, 500),
        "zweite.pdf": (60, 500),
        "dritte.pdf": (60, 500),
    }, budget=32000)
    ctx = build_source_context(uuids, "quiz", count=6)
    assert ctx.first_label == "erste.pdf"
    assert ctx.multi_label == "erste.pdf"
    assert ctx.source_hint == "folgender Source"


def test_the_header_drops_the_quota_when_it_cannot_be_met(monkeypatch):
    # Three sections and two entries: "at least one each" is impossible.
    uuids = _install(monkeypatch, {"a.pdf": (5, 500), "b.pdf": (5, 500), "c.pdf": (5, 500)})
    ctx = build_source_context(uuids, "quiz", count=2)
    assert "take at least" not in ctx.context
    assert "=== SECTION 1 OF 3 — a.pdf ===" in ctx.context


def test_a_single_source_keeps_the_plain_header(monkeypatch):
    uuids = _install(monkeypatch, {"nur_eine.pdf": (20, 500)})
    ctx = build_source_context(uuids, "quiz", count=5)
    assert ctx.context.startswith("--- nur_eine.pdf ---")
    assert "SECTION" not in ctx.context
    assert ctx.sections == {1: "nur_eine.pdf"}


def test_sections_are_numbered_and_carry_the_quota(monkeypatch):
    uuids = _install(monkeypatch, {"a.pdf": (20, 500), "b.pdf": (20, 500)})
    ctx = build_source_context(uuids, "quiz", count=10)
    assert "=== SECTION 1 OF 2 — a.pdf — take at least 5 entries from here ===" in ctx.context
    assert "=== SECTION 2 OF 2 — b.pdf — take at least 5 entries from here ===" in ctx.context
    assert ctx.sections == {1: "a.pdf", 2: "b.pdf"}


def test_a_tool_that_wants_no_quota_gets_a_bare_header(monkeypatch):
    # The cloze is one continuous text, a quota per section would break it apart.
    uuids = _install(monkeypatch, {"a.pdf": (20, 500), "b.pdf": (20, 500)})
    ctx = build_source_context(uuids, "quiz", 10, with_quota=False)
    assert "=== SECTION 1 OF 2 — a.pdf ===" in ctx.context


def test_the_excerpt_is_not_just_the_front_of_the_document(monkeypatch):
    """Cutting to size by taking chunks in order would always keep page 1 onwards."""
    uuids = _install(monkeypatch, {"lang.pdf": (200, 500), "kurz.pdf": (8, 500)})
    pages = set()
    for _ in range(6):
        ctx = build_source_context(uuids, "quiz", count=4)
        block = next(b for b in ctx.context.split("\n\n") if "lang.pdf" in b.split("\n")[0])
        pages.update(int(line.split("S. ")[1].split("]")[0])
                     for line in block.split("\n") if line.startswith("[lang.pdf"))
    assert max(pages) > 100, sorted(pages)[-5:]


# --- the rule ----------------------------------------------------------------

def test_a_single_section_needs_no_rule():
    ctx = QuelleContext(context="", first_label="a", multi_label="a", source_hint="",
                        sections={1: "a.pdf"})
    assert coverage_rule(ctx, 10) == ""


def test_the_rule_numbers_the_sections_and_asks_for_the_number_back():
    ctx = QuelleContext(context="", first_label="a", multi_label="", source_hint="",
                        sections={1: "a.pdf", 2: "b.webm"})
    rule = coverage_rule(ctx, 10)
    assert "1 = a.pdf" in rule and "2 = b.webm" in rule
    assert "at least 5 of the 10 entries" in rule
    assert '"section"' in rule
