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
