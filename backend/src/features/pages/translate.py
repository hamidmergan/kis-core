"""A page in another language or in Leichte Sprache, text for text, so its layout stays as it is.

Every visible text of the page is sent with a key, the model answers with the same keys, and
the answer is put back at the same places. Pictures, numbers and the page's shape never change.
"""

from __future__ import annotations

import asyncio
import json

from loguru import logger

from src.features.pages import schema
from src.features.pages.writing import parse_json
from src.features.summary.models import Caller
from src.limits import (
    PAGES_MAX_ITEM_CHARS,
    PAGES_MAX_LONG_CHARS,
    PAGES_MAX_SHORT_CHARS,
    PAGES_TRANSLATE_BATCH,
)

# Every language a page can be shown in: the name the model reads and the label a reader picks,
# each label in its own language. "easy" is German in Leichte Sprache.
LANGUAGES: dict[str, dict] = {
    "de": {"name": "German", "label": "Deutsch", "lang": "de"},
    "en": {"name": "English", "label": "English", "lang": "en"},
    "easy": {"name": "German in Leichte Sprache", "label": "Leichte Sprache", "lang": "de"},
    "fr": {"name": "French", "label": "Français", "lang": "fr"},
    "es": {"name": "Spanish", "label": "Español", "lang": "es"},
    "it": {"name": "Italian", "label": "Italiano", "lang": "it"},
    "tr": {"name": "Turkish", "label": "Türkçe", "lang": "tr"},
    "uk": {"name": "Ukrainian", "label": "Українська", "lang": "uk"},
    "pl": {"name": "Polish", "label": "Polski", "lang": "pl"},
    "zh": {"name": "Simplified Chinese", "label": "中文", "lang": "zh"},
}

# Fields that are no text a reader sees, they stay as they are.
_KEEP = {"src", "prompt", "kind", "id", "icon", "to", "chart_type", "layout", "saved_at", "lang",
         "design", "version", "easy", "hidden", "hero", "cols", "max"}
_CONCURRENCY = 2
# A busy provider answers 429 or 5xx, each call tries again after these waits in seconds.
_WAITS = (3, 8, 20, 45)

_SYSTEM = (
    "You translate the texts of a learning web page for students into {target}.\n"
    "The user message is a JSON object. Each key holds one text and the most characters its "
    "answer may have.\n"
    "Answer with one JSON object that has exactly the same keys, each value the translated "
    "text as a plain string. Never merge, split, drop or add a key.\n"
    "Rules:\n"
    "- Translate faithfully, add nothing and leave nothing out.\n"
    "- Keep formulas, symbols, units, names and abbreviations of the field as they are.\n"
    "- Keep every number's value, write its decimal separator the way {target} does.\n"
    "- A heading stays a short heading, a label stays a label.\n"
    "- Stay within each text's max_chars.\n"
    "- Plain text only, no markdown, no quotes around the text.\n"
    "- Use the same term for the same thing in every text.\n"
)
_EASY = (
    "You rewrite the texts of a learning web page for students in German Leichte Sprache "
    "(easy-to-read German).\n"
    "The user message is a JSON object. Each key holds one text, in any language, and the most "
    "characters its answer may have.\n"
    "Answer with one JSON object that has exactly the same keys, each value the rewritten text "
    "as a plain string. Never merge, split, drop or add a key.\n"
    "Rules of Leichte Sprache:\n"
    "- Short sentences, one statement per sentence.\n"
    "- Common words. A technical term the subject needs stays, followed by a short explanation "
    "in simple words the first time it appears.\n"
    "- Active voice, no genitive, no subjunctive, no abbreviations, numbers as digits.\n"
    "- Keep the content, leave out details a reader does not need to understand the point.\n"
    "- A heading stays a short heading, a label stays a label, formulas stay as they are.\n"
    "- Stay within each text's max_chars.\n"
    "- Plain text only, no markdown, no quotes around the text.\n"
)


def texts(page: dict) -> list[tuple[tuple, str]]:
    """Every visible text of the page with its place, in reading order."""
    out: list[tuple[tuple, str]] = []

    def walk(node, path: tuple) -> None:
        if isinstance(node, str):
            if node.strip():
                out.append((path, node))
        elif isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, path + (i,))
        elif isinstance(node, dict):
            for k, x in node.items():
                if k not in _KEEP:
                    walk(x, path + (k,))

    walk(page.get("sections") or [], ("sections",))
    if (page.get("footer") or "").strip():
        out.append((("footer",), page["footer"]))
    return out


def put(page: dict, path: tuple, value: str) -> None:
    node = page
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value


def _limit(page: dict, path: tuple) -> int:
    """The most characters the schema keeps at this place, so no answer is cut afterwards."""
    keys = [k for k in path if isinstance(k, str)]
    last = keys[-1]
    if "categories" in keys or keys[-2:] == ["figures", "value"]:
        return schema.CHART_LABEL_CHARS
    if "branches" in keys or "words" in keys or last == "center":
        return schema.MAP_LABEL_CHARS
    if last in ("lead", "meta", "footer"):
        return PAGES_MAX_LONG_CHARS
    if keys[-2:] == ["blocks", "text"]:
        block = page["sections"][path[1]]["blocks"][path[3]]
        return PAGES_MAX_LONG_CHARS if block.get("kind") == "text" else PAGES_MAX_ITEM_CHARS
    if last in ("items", "text"):
        return PAGES_MAX_ITEM_CHARS
    return PAGES_MAX_SHORT_CHARS


def _max_chars(text: str, limit: int, easy: bool) -> int:
    """Room for the answer: a translation runs a little longer, Leichte Sprache longer still."""
    return min(limit, max(40, int(len(text) * (2.0 if easy else 1.4))))


def _batches(items: list[tuple[tuple, str]]) -> list[list[tuple[tuple, str]]]:
    """The texts of one section together, so the model sees their context, cut to the batch size."""
    gruppen: dict[object, list] = {}
    for path, text in items:
        gruppen.setdefault(path[:2], []).append((path, text))
    out = []
    for gruppe in gruppen.values():
        for i in range(0, len(gruppe), PAGES_TRANSLATE_BATCH):
            out.append(gruppe[i:i + PAGES_TRANSLATE_BATCH])
    return out


async def _create(caller: Caller, **kwargs):
    """One call, again after a wait while the provider is only busy."""
    from src.features.summary import concurrency

    for warten in (*_WAITS, None):
        try:
            return await caller.create(**kwargs)
        except Exception as e:  # noqa: BLE001 - only a busy provider is worth waiting for
            if warten is None or not concurrency.overloaded(e):
                raise
            logger.info("Pages: Anbieter ausgelastet ({}), neuer Versuch in {} s", e.__class__.__name__, warten)
            await asyncio.sleep(warten)


async def _ask(caller: Caller, system: str, page: dict, batch: list[tuple[tuple, str]],
               easy: bool) -> dict[str, str]:
    payload = {str(i): {"text": text, "max_chars": _max_chars(text, _limit(page, path), easy)}
               for i, (path, text) in enumerate(batch, 1)}
    title = schema.title_of(page)
    antwort = await _create(caller,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\nPAGE TITLE: {title}\n\n"
                                        + json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=0.2, name="translate", response_format={"type": "json_object"},
        max_tokens=min(16_000, 1_000 + sum(len(t) for _, t in batch) * (3 if easy else 2)),
    )
    daten = parse_json(antwort.choices[0].message.content) or {}
    return {k: v.strip() for k, v in daten.items() if isinstance(v, str) and v.strip()}


async def translate(caller: Caller, page: dict, key: str) -> dict:
    """The page in the language behind ``key``, every text the model left out stays as it was."""
    ziel = LANGUAGES[key]
    easy = key == "easy"
    system = _EASY if easy else _SYSTEM.format(target=ziel["name"])
    neu = json.loads(json.dumps(page))
    gate = asyncio.Semaphore(_CONCURRENCY)
    fehlend = 0

    async def eins(batch: list[tuple[tuple, str]]) -> None:
        nonlocal fehlend
        async with gate:
            antwort = await _ask(caller, system, page, batch, easy)
            offen = [(i, b) for i, b in enumerate(batch, 1) if str(i) not in antwort]
            # A key the model dropped gets one more call of its own, merged texts come apart there.
            for i, (path, text) in offen:
                einzeln = await _ask(caller, system, page, [(path, text)], easy)
                if "1" in einzeln:
                    antwort[str(i)] = einzeln["1"]
            for i, (path, _) in enumerate(batch, 1):
                if str(i) in antwort:
                    put(neu, path, antwort[str(i)])
                else:
                    fehlend += 1

    await asyncio.gather(*(eins(b) for b in _batches(texts(page))))
    if fehlend:
        logger.warning("Pages: {} Texte blieben in der Ausgangssprache ({})", fehlend, key)
    neu["lang"] = ziel["lang"]
    neu["easy"] = easy
    neu.pop("saved_at", None)
    return schema.clean_page(neu)
