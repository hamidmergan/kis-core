"""A page in its other language, German or English, text for text, so its layout stays as it is.

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
    PAGES_TRANSLATE_BATCH_CHARS,
)

# Every language a page can be shown in: the name the model reads and the label a reader picks,
# each label in its own language. A page is written in one and translated into the other.
LANGUAGES: dict[str, dict] = {
    "de": {"name": "German", "label": "Deutsch", "lang": "de"},
    "en": {"name": "English", "label": "English", "lang": "en"},
}

# Fields that are no text a reader sees, they stay as they are.
_KEEP = {"src", "prompt", "kind", "id", "icon", "to", "chart_type", "layout", "saved_at", "lang",
         "design", "version", "hidden", "hero", "cols", "max", "pos", "tone", "heading"}
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
    art = page["sections"][path[1]]["blocks"][path[3]].get("kind") if "blocks" in keys and len(path) > 3 else ""
    if ("categories" in keys or keys[-2:] == ["figures", "value"] or last in ("date", "sym")
            or (art in ("scale", "matrix") and last == "label")):
        return schema.CHART_LABEL_CHARS
    if "branches" in keys or "words" in keys or last in ("center", "root"):
        return schema.MAP_LABEL_CHARS
    if art == "checklist" or (art in ("venn", "formula") and last in ("both", "example")):
        return PAGES_MAX_SHORT_CHARS
    if last in ("lead", "meta", "footer"):
        return PAGES_MAX_LONG_CHARS
    if keys[-2:] == ["blocks", "text"]:
        block = page["sections"][path[1]]["blocks"][path[3]]
        return PAGES_MAX_LONG_CHARS if block.get("kind") == "text" else PAGES_MAX_ITEM_CHARS
    if last in ("items", "text"):
        return PAGES_MAX_ITEM_CHARS
    return PAGES_MAX_SHORT_CHARS


def _max_chars(text: str, limit: int) -> int:
    """Room for the answer, a translation runs a little longer than its original."""
    return min(limit, max(40, int(len(text) * 1.4)))


def _batches(items: list[tuple[tuple, str]]) -> list[list[tuple[tuple, str]]]:
    """Whole sections packed into few calls, a section stays in one call so its context stays."""
    gruppen: dict[object, list] = {}
    for path, text in items:
        gruppen.setdefault(path[:2], []).append((path, text))
    out: list[list] = []
    laufend: list = []
    zeichen = 0
    for gruppe in gruppen.values():
        for i in range(0, len(gruppe), PAGES_TRANSLATE_BATCH):
            teil = gruppe[i:i + PAGES_TRANSLATE_BATCH]
            groesse = sum(len(t) for _, t in teil)
            if laufend and (zeichen + groesse > PAGES_TRANSLATE_BATCH_CHARS
                            or len(laufend) + len(teil) > PAGES_TRANSLATE_BATCH):
                out.append(laufend)
                laufend, zeichen = [], 0
            laufend += teil
            zeichen += groesse
    if laufend:
        out.append(laufend)
    return out


async def create_patiently(caller: Caller, waits: tuple[int, ...] = _WAITS, **kwargs):
    """One call, again after a wait while the provider is only busy."""
    from src.features.summary import concurrency

    for warten in (*waits, None):
        try:
            return await caller.create(**kwargs)
        except Exception as e:  # noqa: BLE001 - only a busy provider is worth waiting for
            if warten is None or not concurrency.overloaded(e):
                raise
            logger.info("Pages: Anbieter ausgelastet ({}), neuer Versuch in {} s", e.__class__.__name__, warten)
            await asyncio.sleep(warten)


async def _ask(caller: Caller, system: str, page: dict, batch: list[tuple[tuple, str]]) -> dict[str, str]:
    payload = {str(i): {"text": text, "max_chars": _max_chars(text, _limit(page, path))}
               for i, (path, text) in enumerate(batch, 1)}
    title = schema.title_of(page)
    antwort = await create_patiently(caller,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"/no_think\nPAGE TITLE: {title}\n\n"
                                        + json.dumps(payload, ensure_ascii=False)},
        ],
        # No enforced JSON mode: under it the model often answers {} or runs on in blank lines.
        temperature=0.2, name="translate",
        max_tokens=min(16_000, 1_000 + sum(len(t) for _, t in batch) * 2),
    )
    daten = parse_json(antwort.choices[0].message.content) or {}
    # The model often answers in the shape it was sent, the text then sits under "text".
    texte = {k: (v.get("text") if isinstance(v, dict) else v) for k, v in daten.items()}
    return {k: v.strip() for k, v in texte.items() if isinstance(v, str) and v.strip()}


def other_language(page: dict) -> str:
    """The language a page gets beside its own, English for a German page and German otherwise."""
    return "en" if (page.get("lang") or "de") == "de" else "de"


async def translate(caller: Caller, page: dict, key: str) -> dict:
    """The page in the language behind ``key``, every text the model left out stays as it was."""
    ziel = LANGUAGES[key]
    system = _SYSTEM.format(target=ziel["name"])
    neu = json.loads(json.dumps(page))
    gate = asyncio.Semaphore(_CONCURRENCY)
    fehlend = 0

    async def eins(batch: list[tuple[tuple, str]]) -> None:
        nonlocal fehlend
        async with gate:
            antwort = await _ask(caller, system, page, batch)
            offen = [(i, b) for i, b in enumerate(batch, 1) if str(i) not in antwort]
            # Every key the model dropped goes again in one call, merged texts come apart there.
            if offen:
                nach = await _ask(caller, system, page, [b for _, b in offen])
                for k, (i, _) in enumerate(offen, 1):
                    if str(k) in nach:
                        antwort[str(i)] = nach[str(k)]
            # What still is missing then gets a call of its own, the last resort.
            for i, (path, text) in [(i, b) for i, b in offen if str(i) not in antwort]:
                einzeln = await _ask(caller, system, page, [(path, text)])
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
    neu.pop("saved_at", None)
    return schema.clean_page(neu)
