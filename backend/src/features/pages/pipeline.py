"""One run of a page: the summary's plan, blocks per section, the frame, then the page itself.

Every stage writes what it finished before the next one starts, like the summary run, so a
run handed back to the queue never pays twice for the same call. Pictures are drawn by the
task afterwards, this module only names them.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Callable, Protocol

from loguru import logger

from src.features.pages import schema
from src.features.pages.writing import write_blocks, write_frame
from src.features.summary import concurrency
from src.features.summary import pipeline as summary_pipeline
from src.features.summary import writing as summary_writing
from src.features.summary.models import Caller, Outline
from src.features.summary.templates import Template
from src.i18n import t
from src.limits import (
    MAP_MATERIAL_MAX_CHARS,
    MAP_PASSAGE_NEIGHBOURS,
    PAGES_SECTIONS,
    SUMMARY_SECTION_GROUP_CHARS,
    SUMMARY_WRITE_CONCURRENCY,
)
from src.services import anweisung
from src.services import text_map as tm
from src.services.openai_compat_llm.base import load_prompt
from src.services.source_reading import Source

PipelineInterrupted = summary_pipeline.PipelineInterrupted


class NoPlan(RuntimeError):
    """No planning call came back usable, the task names it in the person's language."""

# The build plan the summary's planner reads for a page, overridable in the prompt table.
TEMPLATE = Template(
    slug="pages",
    categories=("term and definition", "process", "example with figures", "comparison",
                "limit or common mistake"),
    name_de="Pages", name_en="Pages", hint_de="", hint_en="",
    headings=True,
    body=(
        "Plan a learning web page for students. The sections follow the subject's own "
        "structure: core ideas and terms, how something works or is done, examples with their "
        "figures, comparisons, limits and common mistakes. Each section covers one theme a "
        "student takes in at a glance. A heading names its subject only, never the kind of "
        "section such as example, comparison or overview. No section for exercises, questions "
        "or a quiz."
    ),
    sections=PAGES_SECTIONS,
)

# How the pictures look, a calm style in the colours of KIS, overridable in the prompt table.
IMAGE_STYLE = (
    "Editorial illustration, flat shapes with subtle paper grain, calm deep blue (#004261) and "
    "soft mist grey palette with a single warm amber accent. Clean, modern, generous negative "
    "space."
)
NO_TEXT = "No text, no letters, no numbers, no labels, no logos."
HERO_IMAGE = "img_0.webp"
SECTION_IMAGE = "img_1.webp"
HERO_SIZE = "1536x864"
SECTION_SIZE = "1152x864"
# Words a reader gets through per minute, for the reading time under the title.
WORDS_PER_MINUTE = 200
MIN_CLOUD_WORDS = 6
CLOUD_WORDS = 20


def image_prompt(subject: str) -> str:
    """The prompt the picture service gets, the style first, the subject after."""
    stil = load_prompt("pages_image_style", IMAGE_STYLE).strip()
    return f"{stil} Subject: {' '.join(subject.split())} {NO_TEXT}".strip()


class RunStore(summary_pipeline.RunStore, Protocol):
    def load_blocks(self) -> dict[int, dict]: ...
    def save_blocks(self, index: int, data: dict) -> None: ...
    def load_frame(self) -> dict | None: ...
    def save_frame(self, data: dict) -> None: ...


def _bullets_from_prose(text: str) -> list[dict]:
    """A section the block call could not shape, its prose turned into one list."""
    zeilen = [re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", z).strip() for z in text.split("\n")]
    punkte = [z for z in zeilen if z and not z.startswith("#") and not z.startswith("|")]
    return [{"kind": "bullets", "items": punkte}] if punkte else []


async def _blocks(caller: Caller, *, language: str, plan: Outline, karte: tm.Karte,
                  store: RunStore, should_stop, instructions: str) -> dict[int, dict]:
    """Every section as blocks, several sections per call, one at a time when that fails."""
    fertig = dict(store.load_blocks())
    gruppen = summary_writing.group_sections(plan.sections, summary_pipeline._costs(plan.sections),
                                             SUMMARY_SECTION_GROUP_CHARS)
    offen = [g for g in ([i for i in alle if i not in fertig] for alle in gruppen) if g]

    async def schreibe(gruppe: list[int]) -> None:
        abschnitte = [plan.sections[i] for i in gruppe]
        andere = [a for j, a in enumerate(plan.sections) if j not in gruppe]
        je = MAP_MATERIAL_MAX_CHARS // max(1, len(abschnitte))
        stoff = [karte.passagen(a.stellen, vorrang=a.genannt, nachbarn=MAP_PASSAGE_NEIGHBOURS,
                                budget=je) for a in abschnitte]
        ergebnis = await write_blocks(caller, language=language, group=abschnitte, indices=gruppe,
                                      others=andere, material=stoff, names=plan.names,
                                      instructions=instructions)
        if ergebnis is None:
            ergebnis = []
            for i in gruppe:
                einzeln = await write_blocks(
                    caller, language=language, group=[plan.sections[i]], indices=[i],
                    others=andere, material=[stoff[gruppe.index(i)]], names=plan.names,
                    instructions=instructions)
                ergebnis.append((einzeln or [None])[0])
        for i, teil in zip(gruppe, ergebnis):
            if teil is None or not any(schema.clean_block(b) for b in teil["blocks"]):
                # Prose is the fallback, a section never goes missing for its shape.
                logger.warning("Pages: Abschnitt {} ohne Bloecke, er wird als Liste geschrieben", i)
                prosa = await summary_writing.write_sections(
                    caller, language=language, template_body=TEMPLATE.body,
                    group=[plan.sections[i]], others=andere, written=None,
                    material=[stoff[gruppe.index(i)]], budget=SUMMARY_SECTION_GROUP_CHARS,
                    names=plan.names, instructions=instructions)
                teil = {"lead": (teil or {}).get("lead", ""), "map_label": "",
                        "blocks": _bullets_from_prose((prosa or [""])[0]),
                        "keywords": (teil or {}).get("keywords", [])}
            fertig[i] = teil
            store.save_blocks(i, teil)
        store.progress("section", len(fertig), len(plan.sections))

    darf = (lambda: not should_stop()) if should_stop else None
    store.progress("section", len(fertig), len(plan.sections))
    ergebnisse = await concurrency.run_limited([lambda g=g: schreibe(g) for g in offen],
                                               SUMMARY_WRITE_CONCURRENCY, may_start=darf)
    if any(e is concurrency.SKIPPED for e in ergebnisse):
        raise PipelineInterrupted
    return fertig


async def run(caller: Caller, *, sources: list[Source], store: RunStore,
              should_stop: Callable[[], bool] | None = None, instructions: str = "") -> dict:
    """Plan, blocks and frame, laid down as a draft the task finishes with pictures."""
    language = store.load_language()
    if not language:
        language = summary_pipeline.detect_language(sources)
        store.save_language(language)
    karte = tm.Karte(sources)
    if not len(karte):
        raise RuntimeError("Keine Quelle traegt Text.")

    plan = await summary_pipeline._outline(caller, language=language, vorlage=TEMPLATE,
                                           sources=sources, karte=karte, store=store,
                                           instructions=instructions)
    if not plan.sections:
        raise NoPlan("no outline")
    wirksam = "" if anweisung.faellt_weg(plan.instruction_way) else instructions

    frame = store.load_frame()
    if frame is None:
        frame = await write_frame(caller, language=language, plan=plan, instructions=wirksam)
        store.save_frame(frame)
    bloecke = await _blocks(caller, language=language, plan=plan, karte=karte, store=store,
                            should_stop=should_stop, instructions=wirksam)
    return draft(plan, bloecke, frame, sources=sources, language=language)


def page_locale(language: str) -> str:
    """German pages get German fixed texts, every other language the English ones."""
    return "de" if (language or "").casefold().startswith(("german", "deutsch")) else "en"


def _count(term: str, text: str) -> int:
    return len(re.findall(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))


def word_cloud(keywords: list[str], material: str) -> list[list]:
    """The terms of the sections, weighted by how often the material itself uses them."""
    gezaehlt: dict[str, list] = {}
    for w in keywords:
        schluessel = w.casefold()
        if schluessel not in gezaehlt:
            n = _count(w, material)
            if n:
                gezaehlt[schluessel] = [w, n]
    return sorted(gezaehlt.values(), key=lambda e: -e[1])[:CLOUD_WORDS]


def _short_title(titel: str) -> str:
    """The title's first part for the middle of the mind map, a subtitle after a colon or dash drops."""
    return re.split(r"\s*[:\u2013\u2014]\s*|\s+-\s+", titel, maxsplit=1)[0].strip() or titel


def draft(plan: Outline, bloecke: dict[int, dict], frame: dict, *, sources: list[Source],
          language: str) -> dict:
    """The page with its pictures only named, cleaned to the limits of the schema."""
    loc = page_locale(language)
    titel = plan.title or Path(sources[0].dateiname).stem
    gist = [g for g in (frame.get("gist") or []) if isinstance(g, str) and g.strip()]
    if not gist and plan.intro:
        gist = [s.strip() for s in re.split(r"(?<=[.!?])\s+", plan.intro) if s.strip()][:4]
    lead = str(frame.get("lead") or "").strip()
    if not lead and plan.intro:
        lead = re.split(r"(?<=[.!?])\s+", plan.intro.strip())[0]

    hero = {"id": "top", "hero": True, "title": titel, "lead": lead, "meta": "", "blocks": []}
    if str(frame.get("hero_prompt") or "").strip():
        hero["blocks"].append({"kind": "image", "src": HERO_IMAGE, "alt": frame.get("hero_alt") or "",
                               "prompt": image_prompt(frame["hero_prompt"]), "caption": ""})
    seiten = [hero]

    kurz_bloecke: list[dict] = []
    if gist:
        kurz_bloecke.append({"kind": "bullets", "items": gist[:4]})
    key = frame.get("key")
    if isinstance(key, dict) and (key.get("key") or "").strip():
        kurz_bloecke.append({"kind": "highlight", "key": key.get("key"), "text": key.get("text")})
    if kurz_bloecke:
        seiten.append({"id": "gist", "title": t("pages.gistTitle", loc), "lead": "",
                       "blocks": kurz_bloecke})

    inhalt = []
    for i, abschnitt in enumerate(plan.sections):
        teil = bloecke.get(i)
        if not teil:
            continue
        inhalt.append((i, {"id": f"s{i + 1}", "title": abschnitt.title, "lead": teil.get("lead", ""),
                           "blocks": list(teil.get("blocks") or [])}, teil))

    bild = frame.get("section_image")
    if isinstance(bild, dict) and str(bild.get("prompt") or "").strip():
        ziel = next((s for i, s, _ in inhalt if i == bild.get("section_index")), None)
        if ziel is not None:
            ziel["blocks"].insert(0, {"kind": "image", "src": SECTION_IMAGE,
                                      "alt": bild.get("alt") or "", "caption": bild.get("caption") or "",
                                      "prompt": image_prompt(bild["prompt"])})

    if len(inhalt) >= 3:
        seiten.append({"id": "map", "title": t("pages.mapTitle", loc), "lead": t("pages.mapLead", loc),
                       "blocks": [{"kind": "mindmap", "center": _short_title(titel), "caption": t("pages.mapCaption", loc),
                                   "branches": [{"title": teil.get("map_label") or s["title"],
                                                 "to": s["id"], "leaves": teil.get("keywords", [])[:3]}
                                                for _, s, teil in inhalt[:schema.MAX_BRANCHES]]}]})
    seiten.extend(s for _, s, _ in inhalt)

    stoff = "\n".join(q.text for q in sources)
    woerter = word_cloud([w for _, _, teil in inhalt for w in teil.get("keywords", [])], stoff)
    if len(woerter) >= MIN_CLOUD_WORDS:
        seiten.append({"id": "words", "title": t("pages.wordsTitle", loc), "lead": t("pages.wordsLead", loc),
                       "blocks": [{"kind": "wordcloud", "caption": t("pages.wordsCaption", loc),
                                   "words": woerter}]})

    # The line under the title is the page's one AI notice, so there is no footer repeating it.
    return schema.clean_page({"lang": loc, "sections": seiten, "footer": ""})


def _words_on(page: dict) -> int:
    n = 0

    def zaehle(v) -> None:
        nonlocal n
        if isinstance(v, str):
            n += len(v.split())
        elif isinstance(v, list):
            for x in v:
                zaehle(x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k not in ("src", "prompt", "kind", "id", "icon", "to", "chart_type"):
                    zaehle(x)

    zaehle(page.get("sections"))
    return n


def finish(page: dict, *, today: date) -> dict:
    """The line under the title, the page's one AI notice. The sources stay with the owner."""
    loc = page.get("lang") or "de"
    minuten = max(1, round(_words_on(page) / WORDS_PER_MINUTE))
    datum = today.strftime("%d.%m.%Y") if loc == "de" else today.strftime("%d %B %Y").lstrip("0")
    meta = t("pages.meta", loc, date=datum, minutes=minuten)
    for s in page["sections"]:
        if s.get("hero"):
            s["meta"] = meta
    return page
