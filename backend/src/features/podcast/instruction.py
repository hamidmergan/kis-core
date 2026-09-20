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
OUTLINE = "outline"
FACTS = "facts"

# Cosine distance to the material, measured 15.09.2026 on a law module: a topic that is in
# it lands at 0.39 to 0.56, one that is not at 0.65 and up.
MAX_DIST = 0.60
_PROBE_LIMIT = 30
_PROBE_TOP = 5

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


def _embedder():
    """The embedding call, in one place so a test can stand in for it."""
    from src.services.aia_embeddings import get_embedding_provider_with_fallback
    return get_embedding_provider_with_fallback().embed_one


def _probe(workspace_id: int, source_ids: list[int], instruction: str) -> float:
    """Mean distance of the best spots, the search itself has no such floor."""
    from src.features.ai_assistant.routes._retrieval import _truncate_query_for_embedding

    frage = _truncate_query_for_embedding(instruction)
    treffer = db.hybrid_search_chunks(
        workspace_id, frage, _embedder()(frage), source_ids=source_ids,
        limit=_PROBE_LIMIT, mode="dense") or []
    abstaende = sorted(float(t["vec_distance"]) for t in treffer
                       if t.get("vec_distance") is not None)
    if not abstaende:
        return 1.0
    beste = abstaende[:_PROBE_TOP]
    return sum(beste) / len(beste)


async def _search(workspace_id: int, source_ids: list[int], instruction: str) -> list[dict]:
    from src.features.ai_assistant.routes._retrieval import _retrieve_specific_context
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget
    from src.services.aia_embeddings import get_embedding_provider_with_fallback

    provider = get_embedding_provider_with_fallback()
    return await _retrieve_specific_context(
        provider, workspace_id, source_ids, [instruction], instruction, tool_context_budget(),
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


def _quellen_mit_zusammenfassung(source_uuids: list[str]) -> list[dict]:
    """Per source its file name and its summary, that is what the outline is built from."""
    quellen = []
    for suuid in source_uuids:
        source = db.get_aia_source(suuid)
        if source:
            quellen.append({"id": source["id"], "label": source["filename"],
                            "summary": source.get("summary")})
    return quellen


async def _broad_context(sources, workspace_id: int | None,
                         source_uuids: list[str] | None) -> str:
    """The outline way, only when the material does not fit and every source is summarised."""
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget
    from src.features.podcast import outline

    gesamt = sum(len((c.get("content") or "")) for _label, chunks in sources for c in chunks)
    if gesamt <= tool_context_budget() or not workspace_id or not source_uuids:
        return ""

    quellen = _quellen_mit_zusammenfassung(source_uuids)
    if not outline.usable(quellen):
        logger.info("Podcast: Material zu gross, aber nicht alles zusammengefasst, es wird aufgefuellt")
        return ""

    ids = _ready_ids(workspace_id, source_uuids)
    if not ids:
        return ""

    from src.services.aia_embeddings import get_embedding_provider_with_fallback
    provider = get_embedding_provider_with_fallback()
    namen = {q["id"]: q["label"] for q in quellen}

    def _suche(thema: str, limit: int) -> list[dict]:
        treffer = db.hybrid_search_chunks(
            workspace_id, thema, provider.embed_one(thema), source_ids=ids, limit=limit) or []
        for c in treffer:
            c["source_label"] = namen.get(c.get("source_id"), "")
        return treffer

    llm = _llm()

    async def _frage(messages):
        """The same client and shape the pre-call uses, it must answer JSON."""
        def _call():
            return llm._client.with_options(timeout=120.0, max_retries=0).chat.completions.create(
                model=llm._model, messages=messages, temperature=0.2,
                response_format={"type": "json_object"},
                **(llm._extra_body and {"extra_body": llm._extra_body} or {}),
            )

        antwort = await asyncio.to_thread(_call)
        roh = (antwort.choices[0].message.content or "").strip()
        if roh.startswith("```"):
            roh = roh.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            return json.loads(roh)
        except json.JSONDecodeError:
            return {}

    try:
        return await outline.build(sources=quellen, ask=_frage, search=_suche)
    except Exception as e:  # noqa: BLE001 - a failed outline is no reason to drop the podcast
        logger.warning("Podcast: Gliederung fehlgeschlagen, es wird aufgefuellt: {}", e)
        return ""


async def build_context(
    sources: list[tuple[str, list[dict]]],
    instruction: str,
    workspace_id: int | None = None,
    source_uuids: list[str] | None = None,
    zahlen: dict | None = None,
    facts=None,
) -> str:
    """Fills the budget, unless a precise instruction or the read sources give something better.

    The ways in order: a precise instruction searches, otherwise the facts of every source
    win, and the older two stay below them as a fallback. ``facts`` is only handed in by
    the task, a caller without it keeps exactly the behaviour of before.
    """
    notiz = zahlen if zahlen is not None else {}
    notiz["weg"] = FILL

    async def _ohne_suche() -> str:
        """Everything that is not the targeted search, in order: facts, outline, filling.

        Every giving up inside the search way lands here too, never straight on filling.
        An upload has nothing embedded, so that is the normal way in.
        """
        if facts is not None:
            aus_fakten = await facts()
            if aus_fakten:
                notiz["weg"] = FACTS
                return aus_fakten
            logger.info("Podcast: keine Fakten gewonnen, es geht die aelteren Wege weiter")
        breit = await _broad_context(sources, workspace_id, source_uuids)
        if breit:
            notiz["weg"] = OUTLINE
            return breit
        return source_text.fit_to_budget(sources)

    weg = await route(instruction)
    if weg != SEARCH:
        return await _ohne_suche()
    if not workspace_id or not source_uuids:
        logger.info("Podcast: gezielte Anweisung, aber nichts Durchsuchbares dabei")
        return await _ohne_suche()

    ids = _ready_ids(workspace_id, source_uuids)
    if not ids:
        logger.info("Podcast: gezielte Anweisung, aber noch nichts eingebettet")
        return await _ohne_suche()

    try:
        abstand = await asyncio.to_thread(_probe, workspace_id, ids, instruction)
    except Exception as e:  # noqa: BLE001 — eine misslungene Messung darf nicht sperren
        logger.warning("Podcast: Abstand der Anweisung nicht messbar: {}", e)
        abstand = 0.0
    if abstand > MAX_DIST:
        logger.info("Podcast: Anweisung liegt neben dem Material (Abstand {:.2f})", abstand)
        notiz["daneben"] = True
        return await _ohne_suche()

    try:
        chunks = await _search(workspace_id, ids, instruction)
    except Exception as e:  # noqa: BLE001 — a failed search is no reason to drop the podcast
        logger.warning("Podcast: Suche zur Anweisung fehlgeschlagen: {}", e)
        return await _ohne_suche()

    text = _as_text(chunks)
    if not text.strip():
        logger.info("Podcast: Suche zur Anweisung ohne Treffer")
        return await _ohne_suche()
    logger.info("Podcast: Anweisung gezielt, {} Stellen aus {} Quellen, {} Zeichen",
                len(chunks), len(ids), len(text))
    notiz["weg"] = SEARCH
    notiz["stellen"] = len(chunks)
    return text
