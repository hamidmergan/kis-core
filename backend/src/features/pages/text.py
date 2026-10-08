"""A page as plain text, one part per section, so the learning assistant can read and cite it."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.pages import schema


@dataclass
class Part:
    """One section of the page as text, ``anchor`` is the section's id on the live page."""

    anchor: str
    title: str
    text: str


def _num(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _block(b: dict) -> list[str]:
    """The lines a reader would take from one block, charts and tables spelled out."""
    k = b.get("kind")
    if k == "text":
        return [b["text"]]
    if k == "bullets":
        return [f"- {x}" for x in b["items"]]
    if k == "highlight":
        return [": ".join(x for x in (b.get("key"), b.get("text")) if x)]
    if k == "cards":
        return [": ".join(x for x in (c["title"], c["text"]) if x) for c in b["cards"]]
    if k == "steps":
        return [f"{i + 1}. " + ": ".join(x for x in (s["title"], s["text"]) if x)
                for i, s in enumerate(b["steps"])]
    if k == "figures":
        return [f"{f['value']} {f['label']}".strip() for f in b["figures"]]
    if k == "bars":
        return [f"{x['label']}: {_num(x['value'])}" + (f", {x['text']}" if x.get("text") else "")
                for x in b["bars"]]
    if k == "table":
        zeilen = [b["caption"]] if b.get("caption") else []
        zeilen.append(" | ".join(b["header"]))
        zeilen += [" | ".join(r) for r in b["rows"]]
        return zeilen
    if k == "chart":
        zeilen = [b["caption"]] if b.get("caption") else []
        for s in b["series"]:
            werte = ", ".join(f"{c}: {_num(v)}" for c, v in zip(b["categories"], s["values"]))
            zeilen.append(f"{s['name']}: {werte}" if s.get("name") else werte)
        return zeilen
    if k == "image":
        return [b["caption"]] if b.get("caption") else []
    if k == "mindmap":
        return [f"{br['title']}: {', '.join(br['leaves'])}" for br in b["branches"]]
    if k == "wordcloud":
        return [", ".join(w for w, _ in b["words"])]
    return []


def parts(page: dict) -> list[Part]:
    """Every section others may see, in page order, without the frame's map and cloud."""
    raus: list[Part] = []
    for s in schema.for_viewers(page)["sections"]:
        if s.get("id") in ("map", "words"):
            continue
        zeilen = [x for x in (s.get("lead"), s.get("meta") if not s.get("hero") else "") if x]
        for b in s.get("blocks") or []:
            zeilen += [z for z in _block(b) if z]
        text = "\n".join(zeilen).strip()
        if s.get("title") or text:
            raus.append(Part(anchor=s["id"], title=s.get("title") or "", text=text))
    return raus


def as_text(page: dict) -> str:
    """The whole page as one text, each section under its heading."""
    return "\n\n".join(f"{p.title}\n{p.text}".strip() for p in parts(page))
