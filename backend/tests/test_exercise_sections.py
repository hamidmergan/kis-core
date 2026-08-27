"""Equally sized numbered sections so all sources get their turn."""

from src.features.ai_assistant.tasks.language_training._context import (
    QuelleContext,
    _MIN_PER_SOURCE_CHARS,
    build_source_context,
    coverage_rule,
    missing_section_uuids,
    per_section_quota,
    rebalance_to_count,
    remap_sections,
    section_usage,
)


def _chunks(source_id, n_pages, chars):
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, n_pages + 1)]


def _install(monkeypatch, sizes):
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
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._context.tool_context_budget",
        lambda: 250000)
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

def test_a_long_source_no_longer_drowns_a_short_one(monkeypatch):
    """The measured regression: one source held 39% of the context, another 8%."""
    uuids = _install(monkeypatch, {
        "lang.webm": (120, 500),   # 60k
        "kurz.pdf": (12, 500),     # 6k
        "mittel.pdf": (40, 500),   # 20k
    })
    ctx = build_source_context(uuids, "quiz", count=6)
    sizes = _block_sizes(ctx)
    smallest, largest = min(sizes.values()), max(sizes.values())
    # Header lengths differ, so this is "the same order of magnitude", not byte equality.
    assert largest <= smallest * 1.5, sizes


def test_a_tiny_source_cannot_starve_the_others(monkeypatch):
    uuids = _install(monkeypatch, {
        "winzig.pdf": (1, 200),    # 200 chars
        "normal.pdf": (60, 500),   # 30k
    })
    ctx = build_source_context(uuids, "quiz", count=4)
    sizes = _block_sizes(ctx)
    # Without a floor the smallest source would squeeze all the others together.
    assert sizes["normal.pdf"] > _MIN_PER_SOURCE_CHARS * 0.8, sizes
    assert sizes["normal.pdf"] > sizes["winzig.pdf"] * 5, sizes


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


def test_without_a_count_the_header_states_no_quota(monkeypatch):
    uuids = _install(monkeypatch, {"a.pdf": (20, 500), "b.pdf": (20, 500)})
    ctx = build_source_context(uuids, "quiz")
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


# --- checking the outcome ----------------------------------------------------

def test_usage_counts_per_section_and_names_the_skipped_ones():
    ctx = QuelleContext(context="", first_label="", multi_label="", source_hint="",
                        sections={1: "a.pdf", 2: "b.pdf", 3: "c.webm"})
    items = [{"_section": 1}, {"_section": 1}, {"_section": 3}]
    assert section_usage(items, ctx) == {1: 2, 2: 0, 3: 1}


def test_usage_survives_a_missing_or_bogus_section_number():
    ctx = QuelleContext(context="", first_label="", multi_label="", source_hint="",
                        sections={1: "a.pdf", 2: "b.pdf"})
    items = [{"_section": "2"}, {"_section": None}, {"_section": 9}, {"_section": "abc"}, {}]
    assert section_usage(items, ctx) == {1: 0, 2: 1}


# The top-up for skipped sections, measured as necessary.

def _full_ctx():
    return QuelleContext(
        context="", first_label="a.pdf", multi_label="", source_hint="",
        source_by_name={"a.pdf": {"uuid": "ua"}, "b.pdf": {"uuid": "ub"},
                        "c.webm": {"uuid": "uc"}},
        sections={1: "a.pdf", 2: "b.pdf", 3: "c.webm"},
    )


def test_only_the_skipped_sections_are_topped_up():
    items = [{"_section": 1}, {"_section": 1}, {"_section": 3}]
    assert missing_section_uuids(items, _full_ctx()) == ["ub"]


def test_nothing_to_top_up_when_every_section_was_served():
    items = [{"_section": 1}, {"_section": 2}, {"_section": 3}]
    assert missing_section_uuids(items, _full_ctx()) == []


def test_a_run_that_names_no_section_is_not_topped_up():
    """A missing field must not be read as 'all sections missed'."""
    items = [{"front": "x"}, {"_section": None}, {"_section": "keine Zahl"}]
    assert missing_section_uuids(items, _full_ctx()) == []


def test_the_top_ups_own_numbering_is_translated_back():
    """The top-up numbers its own sections, that has to be mapped back."""
    gap = QuelleContext(context="", first_label="b.pdf", multi_label="", source_hint="",
                        sections={1: "b.pdf"})
    extra = [{"_section": 1}, {"_section": 1}]
    assert [i["_section"] for i in remap_sections(extra, gap, _full_ctx())] == [2, 2]


def test_an_unusable_claim_from_the_top_up_becomes_unknown():
    gap = QuelleContext(context="", first_label="b.pdf", multi_label="", source_hint="",
                        sections={1: "b.pdf"})
    extra = [{"_section": None}, {"_section": 7}]
    assert [i["_section"] for i in remap_sections(extra, gap, _full_ctx())] == [None, None]


def test_the_learner_still_gets_the_number_of_entries_they_asked_for():
    items = [{"_section": 1}] * 8 + [{"_section": 2}, {"_section": 3}, {"_section": 2}]
    assert len(rebalance_to_count(items, 10)) == 10


def test_trimming_takes_from_the_fullest_section_first():
    items = [{"_section": 1}, {"_section": 1}, {"_section": 1}, {"_section": 2}]
    kept = rebalance_to_count(items, 2)
    assert sorted(i["_section"] for i in kept) == [1, 2]


def test_entries_without_a_section_go_first():
    """They cannot be shown to serve any section, so they are the cheapest to lose."""
    items = [{"_section": 1}, {"_section": None}, {"_section": 2}]
    kept = rebalance_to_count(items, 2)
    assert sorted(i["_section"] for i in kept) == [1, 2]


def test_a_set_at_or_below_the_wanted_count_is_left_alone():
    items = [{"_section": 1}, {"_section": 2}]
    assert rebalance_to_count(items, 5) is items
