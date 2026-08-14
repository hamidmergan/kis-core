"""LLM-backed title generation for exercise sets."""


def title_from_items(client, model, items_list: list[dict], fallback: str,
                     avoid: list[str] | None = None) -> str:
    """Titel aus den Vorderseiten der Karten. Die Arbeit macht ``tasks._titles``.

    Bleibt als eigener Name stehen, weil die Generatoren die Karten-Form kennen
    und das geteilte Modul absichtlich nur Textzeilen sieht.
    """
    from src.features.ai_assistant.tasks._titles import title_from_entries

    if not items_list:
        return fallback
    return title_from_entries(
        client, model, [(it.get("front") or "") for it in items_list], fallback, avoid=avoid,
    )


def title_from_glossary_terms(client, model, terms: list[str]) -> str:
    """Short thematic title from a list of technical terms (fallback: comma-separated list)."""
    from src.services import model_limits

    fallback = ", ".join(terms)
    if not terms:
        return fallback
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Provide a short, concise title that summarizes the topic of these technical terms. "
                    "Respond in the same language as the terms. "
                    "Respond ONLY with the title, no quotation marks."
                )},
                {"role": "user", "content": fallback},
            ],
            temperature=0.3,
            # Ein Titel ist kurz, aber ein denkendes Modell braucht davor Platz,
            # sonst kommt der Inhalt leer zurueck. Nur eine Obergrenze.
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
        )
        title = (resp.choices[0].message.content or "").strip().strip('"\'')
        return title or fallback
    except Exception:
        return fallback
