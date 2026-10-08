"""The two kinds of call of a page: the blocks of a run of sections, and the frame around them.

The plan comes from the summary pipeline. Here each planned section is turned into blocks
the frontend draws, the model picks the kind of block that fits the content.
"""

from __future__ import annotations

import json
import re

from loguru import logger

from src.features.summary.models import GROUND_RULES, Caller, Outline, Section
from src.features.summary.writing import _strip_thinking
from src.limits import SUMMARY_WRITE_MAX_TOKENS
from src.services import anweisung

_BLOCKS_GUIDE = """BLOCK KINDS, pick per section what fits its content:
- bullets: {"kind":"bullets","items":["statement","statement"]} two to eight statements, each one sentence.
- highlight: {"kind":"highlight","key":"y = a + bx","text":"what it means"} only for a formula or a rule of a few words that the whole section turns on, at most one on the whole run of sections you write, most sections have none. key is at most 5 words or a formula, under 40 characters, everything else goes into text.
- cards: {"kind":"cards","cards":[{"icon":"info","title":"term","text":"one or two sentences"}]} two to six parallel things such as terms with their definitions, kinds or options. icon is check for what applies or is right, x for what does not apply or is wrong, warning for a caveat, idea for a tip, info otherwise.
- steps: {"kind":"steps","steps":[{"title":"step","text":"one sentence"}]} two to eight steps, only where the material gives an order.
- figures: {"kind":"figures","figures":[{"value":"3,9","label":"what the number is"}]} two to four key figures exactly as the material states them.
- table: {"kind":"table","caption":"what is compared","header":["","A","B"],"rows":[["attribute","value","value"]]} only where several things are compared along the same attributes. At most 6 columns and 12 rows, short cells.
- chart: {"kind":"chart","chart_type":"bar","caption":"what it shows","x_label":"","y_label":"unit","categories":["a","b","c"],"series":[{"name":"","values":[1,2,3]}]} wherever the material states at least three numbers of the same quantity, such as measured values, value pairs or a series over time. Such numbers belong in a chart, not in a list. line for a development along an ordered axis such as time or hours, bar to compare things. At most 10 categories, at most 2 series for line, 1 for bar.
- bars: {"kind":"bars","max":1,"bars":[{"label":"thing","value":0.62,"text":"one sentence on the value"}]} two to ten things measured on one scale, such as shares. max is the top of the scale, 1 for shares, 100 for percent. Each text says something of its own about its value.

EXAMPLE of one section:
{"section_index":2,"map_label":"Vorgehen","lead":"So kommt man von den Punkten zur fertigen Geraden.","blocks":[{"kind":"steps","steps":[{"title":"Punkte eintragen","text":"Jedes Wertepaar wird ein Punkt."},{"title":"Steigung berechnen","text":"Durch den Schwerpunkt ergibt sich b = 3,9."}]},{"kind":"highlight","key":"y = a + bx","text":"Jede Vorhersage folgt dieser Gleichung."}],"keywords":["Steigung","Achsenabschnitt","Schwerpunkt"]}"""


def _blocks_system(language: str, count: int) -> str:
    return (
        f"You turn passages of teaching material into {count} section(s) of a learning web page "
        "for students. The page condenses, it never asks questions and holds no quiz.\n"
        + GROUND_RULES.format(language=language) + "\n"
        "Rule 8: Each section gets one to three blocks. Pick the kinds that show its content "
        "best and vary them across sections. A page is meant to be seen, not read like a list: "
        "key numbers with their unit, such as hours, minutes, euros or percent, become figures, "
        "parallel things become cards, an order becomes steps, a comparison becomes a table. "
        "bullets is only for what fits none of these, at most one bullets block per section. "
        "Never force a chart or a table onto content that is not numbers or a comparison.\n"
        "Rule 9: Never invent a number, a value in a chart, bars or figures block comes from "
        "the material as it stands.\n"
        "Rule 10: Every text is short and stands on its own. No Markdown, no asterisks, no "
        "headings inside the texts.\n"
        "Rule 11: lead is one or two sentences saying what the section shows. map_label names "
        "the section in one to three words. keywords are two to four technical terms of the "
        "section, each one to three words, written as they appear in the material.\n"
        "Rule 12: Write only what belongs under the heading. The other sections are listed so "
        "you stay off their ground, and a figure belongs to the one section whose scope it "
        "concerns, it never appears in two.\n"
        "Rule 13: Never cite a page, a slide or a file.\n"
        "Rule 14: Answer with one JSON object and nothing else: "
        '{"sections":[ one object per section, in the given order ]}.\n\n'
        + _BLOCKS_GUIDE
    )


def _blocks_user(group: list[Section], indices: list[int], others: list[Section],
                 material: list[str], names: dict[str, str], instructions: str) -> str:
    fremd = "\n".join(f"- {a.title}: {a.scope}" for a in others) or "- none"
    namen = ("DOCUMENT NAMES, use these and never a file name:\n"
             + "\n".join(f"- {d} = {k}" for d, k in names.items()) + "\n\n") if names else ""
    teile = [f"=== SECTION section_index {i} ===\nHEADING: {a.title}\nSCOPE: {a.scope}\n"
             f"MATERIAL:\n{m}" for i, a, m in zip(indices, group, material)]
    zusatz = ("\n" + anweisung.schreib_zusatz(instructions, anweisung.STIL)
              if instructions.strip() else "")
    return (f"/no_think\nOther sections of the page, stay off these:\n{fremd}\n\n{namen}"
            "YOUR SECTIONS:\n\n" + "\n\n".join(teile) + zusatz)


def parse_json(raw: str | None) -> dict | None:
    """The first JSON object in an answer, None when there is none."""
    text = _strip_thinking(raw)
    treffer = re.search(r"\{.*\}", text, re.S)
    if not treffer:
        return None
    try:
        daten = json.loads(treffer.group(0))
    except ValueError:
        return None
    return daten if isinstance(daten, dict) else None


def _words(value, most: int) -> list[str]:
    raus = []
    for w in value if isinstance(value, list) else []:
        s = " ".join(str(w or "").split())
        if s and len(s) <= 40 and s.casefold() not in (r.casefold() for r in raus):
            raus.append(s)
    return raus[:most]


async def write_blocks(caller: Caller, *, language: str, group: list[Section],
                       indices: list[int], others: list[Section], material: list[str],
                       names: dict[str, str], instructions: str = "") -> list[dict] | None:
    """The blocks of a run of sections, None when the answer cannot be matched to them."""
    antwort = await caller.create(
        messages=[
            {"role": "system", "content": _blocks_system(language, len(group))},
            {"role": "user", "content": _blocks_user(group, indices, others, material, names,
                                                     instructions)},
        ],
        temperature=0.3, name=f"blocks:{len(group)}:{group[0].title}",
        response_format={"type": "json_object"}, max_tokens=SUMMARY_WRITE_MAX_TOKENS,
    )
    daten = parse_json(antwort.choices[0].message.content)
    rohe = (daten or {}).get("sections")
    if not isinstance(rohe, list):
        return None
    nach_index = {e.get("section_index"): e for e in rohe if isinstance(e, dict)}
    # By the index the model echoed, by position only when the count is exactly right.
    if not all(i in nach_index for i in indices):
        if len(rohe) != len(indices) or not all(isinstance(e, dict) for e in rohe):
            return None
        nach_index = dict(zip(indices, rohe))
    raus = []
    for i in indices:
        e = nach_index[i]
        raus.append({
            "lead": " ".join(str(e.get("lead") or "").split()),
            "map_label": " ".join(str(e.get("map_label") or "").split())[:40],
            "blocks": e.get("blocks") if isinstance(e.get("blocks"), list) else [],
            "keywords": _words(e.get("keywords"), 4),
        })
    return raus


_FRAME_SYSTEM = (
    "You write the frame of a learning web page whose sections are already planned.\n"
    + GROUND_RULES + "\n"
    "Rule 8: lead is one or two sentences under the title that say what the page is about "
    "and why it matters, under 220 characters.\n"
    "Rule 9: gist holds the three or four most important statements of the whole material, "
    "each one sentence with its figures, taken from the opening summary.\n"
    "Rule 10: key is the one formula, rule or core statement everything turns on, with a "
    "sentence on what it means. Leave key as null when there is none.\n"
    "Rule 11: hero_prompt describes in English a calm illustration for the top of the page: "
    "objects or a scene that stand for the subject. It never asks for text, letters, numbers, "
    "labels, logos or diagrams with writing. hero_alt describes the picture in {language} "
    "in one short sentence.\n"
    "Rule 12: section_image picks the one section an illustration helps most, by its "
    "section_index, with an English prompt as in Rule 11, a caption and an alt text in "
    "{language}. Leave it as null when no section gains from a picture.\n"
    "Rule 13: Answer with one JSON object and nothing else, in this shape: "
    '{{"lead":"","gist":["",""],"key":{{"key":"","text":""}},"hero_prompt":"","hero_alt":"",'
    '"section_image":{{"section_index":0,"prompt":"","caption":"","alt":""}}}}'
)


async def write_frame(caller: Caller, *, language: str, plan: Outline,
                      instructions: str = "") -> dict:
    """Lead, key statements and the picture wishes of the page, {} when the call failed."""
    abschnitte = "\n".join(f"{i}. {a.title}: {a.scope}" for i, a in enumerate(plan.sections))
    zusatz = ("\n" + anweisung.schreib_zusatz(instructions, anweisung.STIL)
              if instructions.strip() else "")
    try:
        antwort = await caller.create(
            messages=[
                {"role": "system", "content": _FRAME_SYSTEM.format(language=language)},
                {"role": "user", "content": (
                    f"/no_think\nTITLE: {plan.title}\n\nOPENING SUMMARY:\n{plan.intro}\n\n"
                    f"SECTIONS (section_index. heading: scope):\n{abschnitte}" + zusatz)},
            ],
            temperature=0.3, name="frame", response_format={"type": "json_object"},
            max_tokens=2_000,
        )
    except Exception as e:  # noqa: BLE001 - a page without its frame still has its sections
        from src.features.summary import concurrency
        if concurrency.overloaded(e):
            raise
        logger.warning("Pages: Rahmen nicht geschrieben ({})", e)
        return {}
    return parse_json(antwort.choices[0].message.content) or {}
