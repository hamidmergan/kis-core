"""Geteilter Karten-Parser für Lernkarten/Karteikarten (mode='quelle')."""

from src.features.ki_assistent.tasks.sprachtraining._context import (
    QuelleContext,
    find_all_pages,
)


def parse_card(
    ctx: QuelleContext,
    c: dict,
    include_back_en: bool = False,
    search_term: str = "",
    multi_source: bool = False,
) -> dict:
    """Parse card. search_term validates/corrects page. multi_source=True stores all pages."""
    sl = c.get("source_label", ctx.first_label)
    pn = c.get("page_number")
    item: dict = {
        "front": c["front"],
        "back": c["back"],
        "source_label": sl,
        "page_number": pn,
        "start_time": ctx.time_map.get((sl, pn or 0)),
    }
    if include_back_en:
        item["back_en"] = c.get("back_en", "")
    if search_term:
        pages = find_all_pages(ctx.source_by_name, ctx.time_map, ctx.segments_by_label, search_term)
        if pages:
            if multi_source:
                item["sources"] = pages
            # LLM-zugewiesene Seite beibehalten, wenn sie den Term enthält; sonst erste Match nehmen
            llm_page_valid = any(
                p["source_label"] == sl and p["page_number"] == pn
                for p in pages
            )
            if not llm_page_valid:
                item["source_label"] = pages[0]["source_label"]
                item["page_number"] = pages[0]["page_number"]
                item["start_time"] = pages[0].get("start_time")
    return item


def with_avoid(existing_fronts: list[str], base_content: str) -> str:
    """Hängt einen 'avoid duplicates'-Block an, damit der LLM Variationen statt
    Wiederholungen aus früheren Sets desselben Tools liefert."""
    if not existing_fronts:
        return base_content
    preview = "\n".join(f"- {(f or '')[:160]}" for f in existing_fronts)
    return base_content + (
        "\n\n---\n"
        "Bereits existierende Einträge in diesem Workspace:\n"
        f"{preview}\n\n"
        "Regel: Erstelle UNTERSCHIEDLICHE Einträge, die thematisch NICHT "
        "dasselbe abdecken. Wenn dein Material erschöpft ist und du ein "
        "Thema wiederverwenden musst, erstelle eine klare VARIATION "
        "(anderer Blickwinkel, andere Fragestellung, anderer Schwerpunkt), "
        "keine Wiederholung mit nur umformuliertem Wortlaut."
    )
