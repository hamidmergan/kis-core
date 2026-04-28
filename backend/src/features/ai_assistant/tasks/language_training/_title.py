"""LLM-gestützte Titel-Generierung für Exercise-Sets."""


def title_from_items(client, model, items_list: list[dict], fallback: str) -> str:
    """Erzeugt einen kurzen Titel aus den tatsächlichen Item-Fronts, damit Sets aus
    derselben Quelle unterschiedliche Titel bekommen."""
    if not items_list:
        return fallback
    preview = "\n".join(
        f"- {(it.get('front') or '')[:160]}" for it in items_list[:10]
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Gib einen kurzen, prägnanten Titel (max. 6 Wörter) für diese Übung, "
                    "der das konkrete Thema der unten stehenden Einträge widerspiegelt. "
                    "Antworte NUR mit dem Titel, ohne Anführungszeichen."
                )},
                {"role": "user", "content": f"Einträge:\n{preview}"},
            ],
            temperature=0.7,
            max_tokens=30,
        )
        t = (resp.choices[0].message.content or "").strip().strip('"\'')
        return t or fallback
    except Exception:
        return fallback


def title_from_glossary_terms(client, model, terms: list[str]) -> str:
    """Kurzer thematischer Titel aus einer Liste von Fachbegriffen (Fallback: kommaseparierte Liste)."""
    fallback = ", ".join(terms)
    if not terms:
        return fallback
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Gib einen kurzen, prägnanten Titel der das Thema dieser Fachbegriffe "
                    "zusammenfasst. Antworte NUR mit dem Titel, ohne Anführungszeichen."
                )},
                {"role": "user", "content": fallback},
            ],
            temperature=0.3,
            max_tokens=80,
        )
        title = (resp.choices[0].message.content or "").strip().strip('"\'')
        return title or fallback
    except Exception:
        return fallback
