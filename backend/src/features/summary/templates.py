"""The build plans of the summary tool, five in code, each overridable in the prompt table."""

from dataclasses import dataclass

from src.services.openai_compat_llm.base import load_prompt


@dataclass(frozen=True)
class Template:
    """One build plan and how it is shown in the picker."""

    slug: str
    name_de: str
    name_en: str
    hint_de: str
    hint_en: str
    body: str
    headings: bool


TEMPLATES: tuple[Template, ...] = (
    Template(
        slug="fliesstext",
        name_de="Fließtext", name_en="Continuous text",
        hint_de="Ein durchgehender Text ohne Überschriften.",
        hint_en="One continuous text without headings.",
        headings=False,
        body=(
            "Write one continuous text that carries the whole material. Paragraphs, no "
            "headings, no bullet points. Every figure, date and named party the material "
            "states appears with what it refers to. Open with the subject and its most "
            "important point, close with what the material leaves open."
        ),
    ),
    Template(
        slug="kurzbriefing",
        name_de="Kurzbriefing", name_en="Short briefing",
        hint_de="Kernaussagen, Zahlen und Zuständigkeiten, knapp und geordnet.",
        hint_en="Key points, figures and who is responsible, brief and ordered.",
        headings=True,
        body=(
            "Write a briefing for a reader with five minutes. Under each heading: the core "
            "statements as bullet points, one statement each. Every figure, deadline and "
            "responsibility the material states appears, each with what it refers to. What the "
            "material needs from the reader comes first, background last."
        ),
    ),
    Template(
        slug="lernleitfaden",
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
    ),
    Template(
        slug="zeitstrahl",
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
    Template(
        slug="haeufige_fragen",
        name_de="Häufige Fragen", name_en="Frequently asked questions",
        hint_de="Frage und Antwort, so wie Lesende das Material befragen würden.",
        hint_en="Question and answer, the way readers would ask the material.",
        headings=True,
        body=(
            "Write the material as questions and answers. Each section holds one theme and "
            "under it the questions a reader would ask, each followed by its answer in two to "
            "five sentences drawn strictly from the material. Questions are written the way a "
            "person asks, answers name figures, deadlines and parties with what they refer to."
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
