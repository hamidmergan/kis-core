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
