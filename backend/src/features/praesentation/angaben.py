"""What a presentation was made with, for the info next to the result."""

from src.features.praesentation.schemas import PraesentationParams


def angaben(params: PraesentationParams, anbieter: str = "", bildanbieter: str = "") -> dict:
    """Template, language, material, instruction and picture style, plus who wrote and who drew."""
    return {"anbieter": anbieter, "bildanbieter": bildanbieter,
            "vorlage": params.template_name or params.template_id, "sprache": params.language,
            "anweisung": params.instructions.strip(), "bildstil": params.style_text.strip(),
            "material": params.source_label}
