"""LLM-backed title generation for exercise sets."""

from loguru import logger


def title_from_items(client, model, items_list: list[dict], fallback: str) -> str:
    """Generate a short title from the actual item fronts so sets from the same
    source get distinct titles."""
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
                    "Provide a short, concise title (max 6 words) for this exercise "
                    "that reflects the concrete topic of the entries below. "
                    "Respond in the same language as the entries. "
                    "Respond ONLY with the title, no quotation marks."
                )},
                {"role": "user", "content": f"Entries:\n{preview}"},
            ],
            temperature=0.7,
            # Generous budget: reasoning models spend tokens on thinking before the first
            # content token, and a 30-token cap left content empty -> silent filename fallback.
            max_tokens=400,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # First non-empty line only: with the larger budget a chatty model may add a
        # second line, and the title column is a single short line.
        t = next((ln.strip().strip('"\'') for ln in raw.splitlines() if ln.strip()), "")[:120]
        if not t:
            logger.warning("Exercise-set title: empty LLM response, falling back to {!r}", fallback)
        return t or fallback
    except Exception as e:
        logger.warning("Exercise-set title generation failed ({}), falling back to {!r}", e, fallback)
        return fallback


def title_from_glossary_terms(client, model, terms: list[str]) -> str:
    """Short thematic title from a list of technical terms (fallback: comma-separated list)."""
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
            max_tokens=80,
        )
        title = (resp.choices[0].message.content or "").strip().strip('"\'')
        return title or fallback
    except Exception:
        return fallback
