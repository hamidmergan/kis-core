"""Which way the instruction takes: fill the budget from the front or search the matching spots."""

import asyncio
import json
import re

from loguru import logger

from src import database as db
from src.features.podcast import source_text
from src.services import model_limits

FILL = "fill"
SEARCH = "search"

# The assistant's pre-call asks whether a QUESTION is pointed or broad. A podcast
# instruction is mostly no question at all, so it gets its own one.
_SYSTEM = (
    "Du ordnest die Anweisung zu einer Podcast-Folge ein. Die Anweisung kann in jeder Sprache stehen.\n"
    "THEMA bedeutet: sie sagt, WORUEBER gesprochen werden soll, also ein Thema, ein Kapitel, "
    "ein Begriff oder ein Teil des Materials.\n"
    "STIL bedeutet: sie sagt nur, WIE gesprochen werden soll, also Ton, Tempo, Anrede, Laenge, "
    "Schwierigkeit, Art der Beispiele. Ein Wunsch nach einem Ueberblick ueber alles ist ebenfalls STIL.\n"
    "Steckt beides darin, antwortest du THEMA.\n"
    'Du antwortest mit einem JSON-Objekt der Form {"art": "THEMA"} oder {"art": "STIL"} und mit nichts sonst.'
)

_BEISPIELE = (
    "Beispiele:\n"
    'halte es einfach und locker -> {"art": "STIL"}\n'
    'sprich langsam und benutze kurze Saetze -> {"art": "STIL"}\n'
    'duze die Zuhoerer -> {"art": "STIL"}\n'
    'gib einen Ueberblick ueber das gesamte Material -> {"art": "STIL"}\n'
    'mach es kurz -> {"art": "STIL"}\n'
    'sprich nur ueber die Aufwandsschaetzung -> {"art": "THEMA"}\n'
    'konzentriere dich auf Kapitel 3 -> {"art": "THEMA"}\n'
    'erklaere die Kuehlung einfach und kurz -> {"art": "THEMA"}\n\n'
)


def _llm():
    """The same client the assistant routes with."""
    from src.dependencies import _resolve_llm_provider
    from src.services.openai_compat_llm import OpenAICompatLLMClient
    api_key, base_url, model, provider = _resolve_llm_provider()
    return OpenAICompatLLMClient(
        api_key=api_key, base_url=base_url, model=model,
        whisper_model=model, provider=provider,
    )


def _read_art(raw: str) -> str:
    """THEMA or STIL out of the answer, a thinking model puts its reasoning in front."""
    ohne_denken = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    treffer = re.search(r"\{.*\}", ohne_denken.replace("```json", "").replace("```", ""), re.DOTALL)
    if not treffer:
        return ""
    try:
        return str(json.loads(treffer.group(0)).get("art", "")).strip().upper()
    except Exception:  # noqa: BLE001 — an unreadable answer is simply no answer
        return ""


async def _classify(llm, instruction: str) -> str:
    """One pre-call, it only has to tell a topic apart from a manner of speaking."""
    def _call():
        return llm._client.with_options(timeout=60.0, max_retries=0).chat.completions.create(
            model=llm._model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"{_BEISPIELE}Anweisung: {instruction}"},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
            **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
        )

    antwort = await asyncio.to_thread(_call)
    msg = antwort.choices[0].message
    art = _read_art(msg.content or getattr(msg, "reasoning_content", None) or "")
    logger.info("Podcast: Anweisung '{}' eingeordnet als {}", instruction[:60], art or "unlesbar")
    return SEARCH if art == "THEMA" else FILL


async def route(instruction: str) -> str:
    """An empty instruction never asks the model, everything else goes through the pre-call."""
    if not (instruction or "").strip():
        return FILL
    try:
        return await _classify(_llm(), instruction)
    except Exception as e:  # noqa: BLE001 — a missing provider must not stop the podcast
        logger.warning("Podcast: Anweisung nicht einzuordnen, es wird aufgefuellt: {}", e)
        return FILL


def _ready_ids(workspace_id: int, source_uuids: list[str]) -> list[int]:
    """Only sources whose pieces are already embedded can be searched."""
    ids = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source and source["workspace_id"] == workspace_id and source["status"] == "ready":
            ids.append(source["id"])
    return ids


async def _search(workspace_id: int, source_ids: list[int], instruction: str) -> list[dict]:
    from src.features.ai_assistant.routes._retrieval import _retrieve_specific_context
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget
    from src.services.aia_embeddings import get_embedding_provider_with_fallback

    provider = get_embedding_provider_with_fallback()
    return await _retrieve_specific_context(
        provider, workspace_id, source_ids, [instruction], instruction, tool_context_budget("podcast"),
    )


def _as_text(chunks: list[dict]) -> str:
    """The found spots in the shape the fill path produces, one header per source."""
    namen: dict[int, str] = {}
    je_quelle: dict[int, list[str]] = {}
    for chunk in chunks:
        inhalt = (chunk.get("content") or "").strip()
        if not inhalt:
            continue
        sid = chunk["source_id"]
        if sid not in namen:
            source = db.get_aia_source_by_id(sid)
            namen[sid] = source["filename"] if source else ""
        je_quelle.setdefault(sid, []).append(inhalt)
    teile = []
    for sid, stuecke in je_quelle.items():
        kopf = f"# {namen[sid]}\n" if namen[sid] else ""
        teile.append(kopf + "\n".join(stuecke))
    return "\n\n".join(teile)


async def build_context(
    sources: list[tuple[str, list[dict]]],
    instruction: str,
    workspace_id: int | None = None,
    source_uuids: list[str] | None = None,
) -> str:
    """Fills the budget, unless a precise instruction and embedded material allow a search."""
    weg = await route(instruction)
    if weg != SEARCH or not workspace_id or not source_uuids:
        return source_text.fit_to_budget(sources)

    ids = _ready_ids(workspace_id, source_uuids)
    if not ids:
        logger.info("Podcast: gezielte Anweisung, aber noch nichts eingebettet, es wird aufgefuellt")
        return source_text.fit_to_budget(sources)

    try:
        chunks = await _search(workspace_id, ids, instruction)
    except Exception as e:  # noqa: BLE001 — a failed search is no reason to drop the podcast
        logger.warning("Podcast: Suche zur Anweisung fehlgeschlagen, es wird aufgefuellt: {}", e)
        return source_text.fit_to_budget(sources)

    text = _as_text(chunks)
    if not text.strip():
        logger.info("Podcast: Suche zur Anweisung ohne Treffer, es wird aufgefuellt")
        return source_text.fit_to_budget(sources)
    logger.info("Podcast: Anweisung gezielt, {} Stellen aus {} Quellen, {} Zeichen",
                len(chunks), len(ids), len(text))
    return text
