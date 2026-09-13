"""The quota only goes into the prompt when the model can actually fulfil it."""

from src.features.ai_assistant.tasks.language_training._context import (
    QuelleContext,
    coverage_rule,
    quota_fits,
)


def _ctx(n_sections: int) -> QuelleContext:
    labels = [f"q{i}.pdf" for i in range(1, n_sections + 1)]
    return QuelleContext(
        context="ctx", first_label=labels[0] if labels else "",
        multi_label="T", source_hint="Quelle",
        source_by_name={label: {"id": i, "uuid": f"u{i}"}
                        for i, label in enumerate(labels, start=1)},
        sections={i: label for i, label in enumerate(labels, start=1)},
    )


def test_the_quota_fits_when_there_are_more_entries_than_sections():
    assert quota_fits(_ctx(3), 10) is True


def test_the_quota_fits_exactly_at_one_entry_per_section():
    assert quota_fits(_ctx(10), 10) is True


def test_the_quota_does_not_fit_with_more_sections_than_entries():
    # 25 sources and 10 flashcards: "at least one from each" cannot be done.
    assert quota_fits(_ctx(25), 10) is False


def test_a_single_section_needs_no_quota():
    assert quota_fits(_ctx(1), 10) is False


def test_the_prompt_block_stays_away_when_the_quota_does_not_fit():
    assert coverage_rule(_ctx(25), 10) == ""


def test_the_prompt_block_is_there_when_the_quota_fits():
    block = coverage_rule(_ctx(3), 9)
    assert "COVERAGE" in block
    assert "at least 3" in block
