"""Repairs the one JSON slip the LLM makes most often: a comma before a closing bracket."""

_SPACE = " \t\r\n"


def drop_trailing_commas(text: str) -> str:
    """Removes every comma that stands right before ] or } outside of a string."""
    out: list[str] = []
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == ",":
            j = i + 1
            while j < len(text) and text[j] in _SPACE:
                j += 1
            if j < len(text) and text[j] in "]}":
                continue
        out.append(ch)
    return "".join(out)


_CLOSER = {"[": "]", "{": "}"}


def close_brackets(text: str) -> str:
    """Adds the closing bracket the LLM forgot, measured 08.10.2026: a mind map lacked one ] before its last }."""
    out: list[str] = []
    stack: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in _CLOSER:
            stack.append(_CLOSER[ch])
        elif ch in "]}":
            if ch not in stack:
                # A closer without its opener stays out, the rest still parses.
                continue
            while stack[-1] != ch:
                out.append(stack.pop())
            stack.pop()
        out.append(ch)
    return "".join(out)


def loads_entries(text: str, key: str):
    """The answer as JSON, or its title and every complete entry of ``key`` when the whole breaks."""
    import json
    import re

    from loguru import logger

    try:
        return json.loads(text)
    except json.JSONDecodeError as fehler:
        start = text.find(f'"{key}"')
        klammer = text.find("[", start) if start >= 0 else -1
        if klammer < 0:
            raise
        decoder = json.JSONDecoder()
        eintraege: list[dict] = []
        stelle = klammer + 1
        while (anfang := text.find("{", stelle)) >= 0:
            try:
                eintrag, stelle = decoder.raw_decode(text, anfang)
            except json.JSONDecodeError:
                # A broken entry is skipped, the search goes on behind its opening brace.
                stelle = anfang + 1
                continue
            if isinstance(eintrag, dict):
                eintraege.append(eintrag)
        if not eintraege:
            raise fehler
        titel = re.search(r'"title"\s*:\s*("(?:[^"\\]|\\.)*")', text)
        logger.warning("JSON gebrochen ({}), {} vollstaendige Eintraege gerettet", fehler, len(eintraege))
        return {"title": json.loads(titel.group(1)) if titel else "", key: eintraege}
