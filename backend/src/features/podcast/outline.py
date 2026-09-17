"""The podcast when the material does not fit: topics from the summaries, text from search."""

from loguru import logger

from src.features.ai_assistant.summaries import MAX_SUMMARY_CHARS as _MAX_SUMMARY_CHARS

# Segments of one episode, more only splinters the script.
_MAX_TOPICS = 8
# Passages per segment, enough to talk about it.
_PER_TOPIC = 4

PROMPT = (
    "Du planst eine Podcast-Folge. Unten steht je Quelle eine kurze Zusammenfassung.\n"
    "Nenne die Themen, ueber die die Folge sprechen soll, damit ALLE Quellen vorkommen.\n\n"
    'Antworte NUR mit einem JSON-Objekt der Form {"themen": ["Thema 1", "Thema 2"]}.\n\n'
    "Regeln:\n"
    "- Hoechstens 8 Themen, jedes hoechstens 8 Woerter\n"
    "- Jede Zusammenfassung muss sich in mindestens einem Thema wiederfinden\n"
    "- Ein Thema benennt einen Inhalt, nie einen Dateinamen\n"
    "- Nur was in den Zusammenfassungen steht, nichts erfinden\n"
    "- Antworte NUR mit dem JSON-Objekt, sonst nichts."
)


def usable(sources: list[dict]) -> bool:
    """True when every source carries a summary, otherwise the old way stays."""
    return bool(sources) and all((s.get("summary") or "").strip() for s in sources)


def summary_context(sources: list[dict]) -> str:
    """One labelled block per source: what that source is about."""
    teile = []
    for s in sources:
        summary = (s.get("summary") or "").strip()
        if summary:
            teile.append(f"--- {s.get('label')} ---\n{summary[:_MAX_SUMMARY_CHARS]}")
    return "\n\n".join(teile)


def topic_list(answer: dict, max_topics: int = _MAX_TOPICS) -> list[str]:
    """The segments of the episode, each one becomes a search."""
    out: list[str] = []
    for thema in (answer or {}).get("themen") or []:
        t = str(thema).strip()
        if t and t not in out:
            out.append(t)
    return out[:max_topics]


def as_text(hits_by_topic: dict[str, list[dict]]) -> str:
    """The found passages as text, grouped under their topic, every passage once."""
    teile: list[str] = []
    gesehen: set[tuple] = set()
    for thema, treffer in hits_by_topic.items():
        stuecke = []
        for chunk in treffer:
            schluessel = (chunk.get("source_label"), chunk.get("page_number"),
                          chunk.get("start_time"), (chunk.get("content") or "")[:60])
            if schluessel in gesehen:
                continue
            gesehen.add(schluessel)
            stuecke.append(f"[{chunk.get('source_label')}]\n{chunk.get('content')}")
        if stuecke:
            teile.append(f"# {thema}\n" + "\n\n".join(stuecke))
    return "\n\n".join(teile)


async def build(*, sources: list[dict], ask, search, per_topic: int = _PER_TOPIC) -> str:
    """One call names the topics, the search brings the text, no second call needed."""
    antwort = await ask([
        {"role": "system", "content": PROMPT},
        {"role": "user", "content": "/no_think\n" + summary_context(sources)},
    ])
    themen = topic_list(antwort if isinstance(antwort, dict) else {})
    if not themen:
        logger.info("Podcast: keine Gliederung erhalten, es wird aufgefuellt")
        return ""

    treffer: dict[str, list[dict]] = {}
    for thema in themen:
        try:
            gefunden = search(thema, per_topic) or []
        except Exception as e:  # noqa: BLE001 - one topic without text is no reason to stop
            logger.warning("Podcast: keine Suche fuer {}: {}", thema, e)
            continue
        if gefunden:
            treffer[thema] = gefunden
    text = as_text(treffer)
    logger.info("Podcast: {} Themen, {} Zeichen aus der Suche", len(themen), len(text))
    return text
