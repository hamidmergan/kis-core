"""The build plans of the summary tool, five in code, each overridable in the prompt table."""

from dataclasses import dataclass

from src.services.openai_compat_llm.base import load_prompt


@dataclass(frozen=True)
class Template:
    """One build plan, how it is shown in the picker, and what the reader looks for."""

    slug: str
    name_de: str
    name_en: str
    hint_de: str
    hint_en: str
    body: str
    headings: bool
    # The search grid of the read call, English because the model echoes it verbatim.
    categories: tuple[str, ...]
    # The last sections answer the ones before, so they are written after the rest, reading it.
    closing_reads_document: bool = False
    # How many sections, whatever the size of the material, None lets the size decide.
    sections: tuple[int, int] | None = None
    # The length of the whole prose, None lets the material decide.
    length_chars: int | None = None


TEMPLATES: tuple[Template, ...] = (
    Template(
        slug="kurzbriefing",
        categories=("core statement", "figure", "deadline", "responsibility", "action needed",
                    "background"),
        name_de="Kurzbriefing", name_en="Short briefing",
        hint_de="Kernaussagen, Zahlen und Zuständigkeiten, knapp und geordnet.",
        hint_en="Key points, figures and who is responsible, brief and ordered.",
        headings=True,
        body=(
            "Write a briefing a reader takes in within five minutes. The sections are kinds of "
            "statement across all files, never one file after the other, in this order: what "
            "the reader must do and by when, who is responsible for what, figures and "
            "consequences, background last. Leave out a kind the material does not carry. "
            "Under each heading: bullet points, one statement each, the most consequential "
            "first. Pick what matters most, a briefing never lists everything. Each figure, "
            "deadline and responsibility you keep stands with what it refers to. Where the "
            "material comes from more than one document, begin each bullet with the document's "
            "short name, in bold and followed by a colon."
        ),
        sections=(4, 7),
        length_chars=9_000,
    ),
    Template(
        slug="lernleitfaden",
        categories=("term and definition", "connection", "example", "testable statement",
                    "open question"),
        name_de="Lernleitfaden", name_en="Study guide",
        hint_de="Begriffe, Zusammenhänge und Prüfungsfragen zum Selbstlernen.",
        hint_en="Terms, connections and self-check questions for studying.",
        headings=True,
        body=(
            "Write a study guide. For each topic: the terms with their definitions as the "
            "material gives them, the connections between them as short prose, then three "
            "questions a learner should be able to answer from this section. A final section "
            "headed as self-check questions collects every question. Draw these questions from "
            "the facts given to you for every topic, never from how earlier sections of this "
            "document happen to read, since that text may already be shortened. A section "
            "after it headed as answers answers each one from the material, numbered to match. "
            "Both headings in the output language."
        ),
        closing_reads_document=True,
    ),
    Template(
        slug="zeitstrahl",
        categories=("dated event", "deadline or period", "sequence", "consequence", "undated"),
        name_de="Zeitstrahl", name_en="Timeline",
        hint_de="Alles Datierte in zeitlicher Reihenfolge, mit Fristen und Folgen.",
        hint_en="Everything dated in order, with deadlines and consequences.",
        headings=True,
        body=(
            "Write a timeline. Sections are periods in chronological order. Every dated "
            "statement, deadline, period and sequence the material carries, in chronological "
            "order, one entry per line starting with the date or the period. Each entry names "
            "what happens, who is concerned and what follows from it. Undated material goes "
            "into a closing section headed as undated, in the output language."
        ),
    ),
)


def get_template(slug: str) -> Template | None:
    """The build plan behind a short name, None when there is none."""
    return next((t for t in TEMPLATES if t.slug == slug), None)


def default_template() -> Template:
    """The plan a request without a choice gets."""
    return TEMPLATES[0]


def template_body(template: Template) -> str:
    """The plan text, the prompt table wins over the code when it has an entry."""
    return load_prompt(f"summary_template_{template.slug}", template.body)
