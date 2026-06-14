"""Shared helpers for card/exercise generation (mode='source')."""


def with_avoid(existing_fronts: list[str], base_content: str) -> str:
    """Append an 'avoid duplicates' block so the LLM produces variations instead
    of repetitions from earlier sets of the same tool."""
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
