"""The user's instruction to a learning tool: which way it takes and how it enters the prompt."""

import asyncio
import json
import re
from dataclasses import dataclass

from loguru import logger

from src import database as db
from src.limits import AIA_INSTRUCTION_MAX_CHARS as MAX_CHARS
from src.features.ai_assistant.tasks._helpers import _clean_llm_json, _get_llm_client
from src.services import model_limits
from src.services.llm_call import create_logged

# The ways an instruction can take, the result carries one of them.
NONE = "none"          # no instruction at all
STYLE = "style"        # only says how, the material stays as it is
SEARCH = "search"      # names a topic, only the found spots are the material
UNMATCHED = "unmatched"  # names a topic the material does not cover, dropped
FILL = "fill"          # a topic, but nothing to search, the material stays as it is

# Cosine distance to the material, measured 15.09.2026 on a law module: a topic that is in
# it lands at 0.39 to 0.56, one that is not at 0.65 and up.
MAX_DIST = 0.60
_PROBE_LIMIT = 30
_PROBE_TOP = 5

# The assistant's pre-call asks whether a QUESTION is pointed or broad. An instruction to a
# learning tool is mostly no question at all, so it gets its own one.
_SYSTEM = (
    "Du ordnest die Anweisung zu einem Lernwerkzeug ein (Karteikarten, Quiz, Mindmap oder "
    "Datentabelle). Die Anweisung kann in jeder Sprache stehen.\n"
    "THEMA bedeutet: sie sagt, WORUEBER es gehen soll, also ein Thema, ein Kapitel, ein Begriff "
    "oder ein Teil des Materials.\n"
    "STIL bedeutet: sie sagt nur, WIE es sein soll, also Schwierigkeit, Art der Fragen, Tiefe, "
    "Aufbau, Spalten, Zielgruppe oder Sprache. Ein Wunsch nach einem Ueberblick ueber alles ist "
    "ebenfalls STIL.\n"
    "Steckt beides darin, antwortest du THEMA.\n"
    'Du antwortest mit einem JSON-Objekt der Form {"art": "THEMA"} oder {"art": "STIL"} und mit nichts sonst.'
)

_BEISPIELE = (
    "Beispiele:\n"
    'leichte Fragen -> {"art": "STIL"}\n'
    'nur Richtig-oder-Falsch-Aufgaben -> {"art": "STIL"}\n'
    'Spalten: Begriff, Frist, Folge -> {"art": "STIL"}\n'
    'fuer Anfaenger, kurze Antworten -> {"art": "STIL"}\n'
    'gib einen Ueberblick ueber alles -> {"art": "STIL"}\n'
    'nur Kapitel 3 -> {"art": "THEMA"}\n'
    'konzentriere dich auf die Kuehlung -> {"art": "THEMA"}\n'
    'schwere Fragen zur Aufwandsschaetzung -> {"art": "THEMA"}\n\n'
)

# The block every tool appends to its system prompt, the guard keeps the sources in charge.
_BLOCK = (
    "\n\nADDITIONAL INSTRUCTION FROM THE USER: \"{instruction}\"\n"
    "Follow it as far as the source material allows. It never overrides the rules above: "
    "the JSON format, the number of entries and the output language stay as specified. "
    "Never invent content to satisfy it. When the sources do not cover what it asks for, "
    "leave that part out."
)

# On the search way the material is the found passages plus their neighbours, which may be
# about something else. The count stays full, the model rephrases instead of drifting.
_NARROWED = (
    "\nThe source material holds only the passages found for this instruction plus their "
    "neighbouring passages, which may be about other matters. Everything you produce must be "
    "about what the instruction names, leave the rest out. Keep the number of entries as "
    "specified: when the topic yields fewer distinct points, cover the same points from another "
    "angle or in other words rather than switching to another topic."
)


@dataclass
class Resolution:
    """What the tool does with the instruction: the prompt text, the material, the flag."""
    text: str                      # goes into the prompt, empty when dropped
    chunks: list[dict] | None      # the found spots, None when the material stays as today
    unmatched: bool                # the instruction named something the material lacks
    way: str                       # one of NONE, STYLE, SEARCH, UNMATCHED, FILL


_WHITESPACE = re.compile(r"\s+")


def clean(text) -> str:
    """One line of plain text, cut to the limit the schema also enforces."""
    if not text:
        return ""
    return _WHITESPACE.sub(" ", str(text)).strip()[:MAX_CHARS]


def prompt_block(instruction: str, narrowed: bool = False) -> str:
    """The instruction with its guard, empty when there is none, narrowed on the search way."""
    text = clean(instruction)
    if not text:
        return ""
    block = _BLOCK.format(instruction=text.replace('"', "'"))
    return block + _NARROWED if narrowed else block


def _read_art(raw: str) -> str:
    """THEMA or STIL out of the answer, a thinking model puts its reasoning in front."""
    ohne_denken = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL)
    treffer = re.search(r"\{.*\}", _clean_llm_json(ohne_denken), re.DOTALL)
    if not treffer:
        return ""
    try:
        return str(json.loads(treffer.group(0)).get("art", "")).strip().upper()
    except Exception:  # noqa: BLE001 - an unreadable answer is simply no answer
        return ""


def classify(instruction: str) -> str:
    """One pre-call, it only has to tell a topic apart from a manner. Any failure fills."""
    try:
        client, model, _provider = _get_llm_client()
        antwort = create_logged(
            client, endpoint="anweisung", model=model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": f"/no_think\n{_BEISPIELE}Anweisung: {instruction}"},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            max_tokens=model_limits.PRECALL_MAX_TOKENS,
        )
        msg = antwort.choices[0].message
        art = _read_art(msg.content or getattr(msg, "reasoning_content", None) or "")
    except Exception as e:  # noqa: BLE001 - a missing provider must not stop the tool
        logger.warning("Anweisung nicht einzuordnen, es wird aufgefuellt: {}", e)
        return FILL
    logger.info("Anweisung '{}' eingeordnet als {}", instruction[:60], art or "unlesbar")
    return SEARCH if art == "THEMA" else FILL


def _ready_ids(source_ids: list[int]) -> list[int]:
    """Only sources whose pieces are already embedded can be searched."""
    ids = []
    for sid in source_ids:
        source = db.get_aia_source_by_id(sid)
        if source and source.get("status") == "ready":
            ids.append(sid)
    return ids


def _embedder():
    """The embedding call, in one place so a test can stand in for it."""
    from src.services.aia_embeddings import get_embedding_provider_with_fallback
    return get_embedding_provider_with_fallback().embed_one


def probe(workspace_id: int, source_ids: list[int], instruction: str) -> float:
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


def search(workspace_id: int, source_ids: list[int], instruction: str, budget: int) -> list[dict]:
    """The spots that match the instruction, the same retrieval a pointed question uses."""
    from src.features.ai_assistant.routes._retrieval import _retrieve_specific_context
    from src.services.aia_embeddings import get_embedding_provider_with_fallback

    provider = get_embedding_provider_with_fallback()
    return asyncio.run(_retrieve_specific_context(
        provider, workspace_id, source_ids, [instruction], instruction, budget))


def spots_by_source(chunks: list[dict]) -> dict[int, list[dict]]:
    """The found spots grouped per source, in hit order, empty ones left out."""
    gruppen: dict[int, list[dict]] = {}
    for chunk in chunks:
        if (chunk.get("content") or "").strip():
            gruppen.setdefault(chunk["source_id"], []).append(chunk)
    return gruppen


def resolve(workspace_id, source_ids: list[int], instruction, budget: int) -> Resolution:
    """Decides the way, every fallback keeps the material as it is."""
    text = clean(instruction)
    if not text:
        return Resolution("", None, False, NONE)
    if classify(text) != SEARCH:
        return Resolution(text, None, False, STYLE)
    if not workspace_id:
        return Resolution(text, None, False, FILL)

    ids = _ready_ids(source_ids)
    if not ids:
        logger.info("Anweisung nennt ein Thema, aber nichts ist eingebettet, es wird aufgefuellt")
        return Resolution(text, None, False, FILL)

    try:
        abstand = probe(workspace_id, ids, text)
    except Exception as e:  # noqa: BLE001 - a failed measurement must not block
        logger.warning("Abstand der Anweisung nicht messbar: {}", e)
        abstand = 0.0
    if abstand > MAX_DIST:
        logger.info("Anweisung liegt neben dem Material (Abstand {:.2f}), sie faellt weg", abstand)
        return Resolution("", None, True, UNMATCHED)

    try:
        chunks = search(workspace_id, ids, text, budget)
    except Exception as e:  # noqa: BLE001 - a failed search is no reason to drop the tool
        logger.warning("Suche zur Anweisung fehlgeschlagen, es wird aufgefuellt: {}", e)
        return Resolution(text, None, False, FILL)
    # A hit without text is no material, so a search that finds only those counts as a miss.
    chunks = [c for c in chunks if (c.get("content") or "").strip()]
    if not chunks:
        logger.info("Suche zur Anweisung ohne Treffer, sie faellt weg")
        return Resolution("", None, True, UNMATCHED)

    logger.info("Anweisung gezielt, {} Stellen aus {} Quellen", len(chunks), len(ids))
    return Resolution(text, chunks, False, SEARCH)
