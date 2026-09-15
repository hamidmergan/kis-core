"""The terms a podcast keeps fixed: sifted against the material, rendered for the prompt."""

from src.services.glossary import GlossaryService

# Three lists of 500 pairs may be picked, so only a small share can ever reach the prompt.
MAX_TERMS = 60

LABEL_DE = "Feste Begriffe, genau so verwenden"
LABEL_EN = "Fixed terms, use exactly this wording"


def sift(entries: dict[str, str], material: str) -> dict[str, str]:
    """Only the pairs whose term really occurs in the material, longest first, capped."""
    if not entries or not material.strip():
        return {}
    service = GlossaryService()
    service.set_entries(entries)
    paare = service.entries
    return {begriff: paare[begriff] for begriff in service.terms_in(material)[:MAX_TERMS]}


def block(entries: dict[str, str], language: str) -> str:
    """The prompt block, empty when there is nothing to keep fixed."""
    if not entries:
        return ""
    label = LABEL_DE if language == "de" else LABEL_EN
    zeilen = "\n".join(f"- {quelle} = {ziel}" for quelle, ziel in entries.items())
    return f"\n{label}:\n{zeilen}\n"
