import re
from typing import List

from src.services.translation import TranslationService

LATEX_MATH_ENVIRONMENTS = {
    "equation", "equation*", "align", "align*", "gather", "gather*",
    "multline", "multline*", "eqnarray", "eqnarray*", "math",
    "displaymath", "split", "flalign", "flalign*", "alignat", "alignat*",
}

LATEX_VERBATIM_ENVIRONMENTS = {
    "verbatim", "Verbatim", "verbatim*", "lstlisting", "minted",
}

LATEX_PROTECTED_ENVIRONMENTS = LATEX_MATH_ENVIRONMENTS | LATEX_VERBATIM_ENVIRONMENTS

LATEX_COMMAND_RULES = {
    "label": {"mandatory": ["protect"], "optional": "translate"},
    "ref": {"mandatory": ["protect"], "optional": "translate"},
    "eqref": {"mandatory": ["protect"], "optional": "translate"},
    "pageref": {"mandatory": ["protect"], "optional": "translate"},
    "autoref": {"mandatory": ["protect"], "optional": "translate"},
    "cref": {"mandatory": ["protect"], "optional": "translate"},
    "Cref": {"mandatory": ["protect"], "optional": "translate"},
    "cite": {"mandatory": ["protect"], "optional": "translate"},
    "citep": {"mandatory": ["protect"], "optional": "translate"},
    "citet": {"mandatory": ["protect"], "optional": "translate"},
    "citealt": {"mandatory": ["protect"], "optional": "translate"},
    "citealp": {"mandatory": ["protect"], "optional": "translate"},
    "citenum": {"mandatory": ["protect"], "optional": "translate"},
    "citeauthor": {"mandatory": ["protect"], "optional": "translate"},
    "citeyear": {"mandatory": ["protect"], "optional": "translate"},
    "citeyearpar": {"mandatory": ["protect"], "optional": "translate"},
    "url": {"mandatory": ["protect"], "optional": "protect"},
    "path": {"mandatory": ["protect"], "optional": "protect"},
    "href": {"mandatory": ["protect", "translate"], "optional": "translate"},
    "hyperref": {"mandatory": ["protect", "translate"], "optional": "translate"},
    "includegraphics": {"mandatory": ["protect"], "optional": "protect"},
    "input": {"mandatory": ["protect"], "optional": "protect"},
    "include": {"mandatory": ["protect"], "optional": "protect"},
    "includeonly": {"mandatory": ["protect"], "optional": "protect"},
    "bibliography": {"mandatory": ["protect"], "optional": "protect"},
    "bibliographystyle": {"mandatory": ["protect"], "optional": "protect"},
    "addbibresource": {"mandatory": ["protect"], "optional": "protect"},
    "documentclass": {"mandatory": ["protect"], "optional": "protect"},
    "usepackage": {"mandatory": ["protect"], "optional": "protect"},
    "lstinputlisting": {"mandatory": ["protect"], "optional": "protect"},
    "verbatiminput": {"mandatory": ["protect"], "optional": "protect"},
    "graphicspath": {"mandatory": ["protect"], "optional": "protect"},
}

LATEX_VERBATIM_COMMANDS = {"verb", "lstinline"}


def _latex_is_escaped(text: str, idx: int) -> bool:
    backslashes = 0
    j = idx - 1
    while j >= 0 and text[j] == "\\":
        backslashes += 1
        j -= 1
    return (backslashes % 2) == 1


def _latex_read_group(text: str, start_idx: int, open_char: str, close_char: str):
    if start_idx >= len(text) or text[start_idx] != open_char:
        return None, start_idx
    depth = 0
    i = start_idx
    while i < len(text):
        ch = text[i]
        if ch == open_char and not _latex_is_escaped(text, i):
            depth += 1
        elif ch == close_char and not _latex_is_escaped(text, i):
            depth -= 1
            if depth == 0:
                group = text[start_idx : i + 1]
                return group, i + 1
        i += 1
    return None, start_idx


def _latex_consume_whitespace(text: str, idx: int):
    start = idx
    while idx < len(text) and text[idx].isspace():
        idx += 1
    return text[start:idx], idx


def _latex_find_math_end(text: str, start_idx: int, delimiter: str):
    i = start_idx
    delim_len = len(delimiter)
    while i < len(text):
        if text.startswith(delimiter, i) and not _latex_is_escaped(text, i):
            return i + delim_len
        i += 1
    return len(text)


def _latex_find_environment_end(text: str, start_idx: int, env_name: str):
    end_tag = f"\\end{{{env_name}}}"
    pos = text.find(end_tag, start_idx)
    if pos == -1:
        return len(text)
    return pos + len(end_tag)


# Collects the pieces with placeholders and translates them in one batch.

_SLOT_RE = re.compile(r"__TX_(\d+)__")


def _parse_latex(
    text: str,
    source_lang: str,
    target_lang: str,
    service: TranslationService,
    translate_slots: list,
    out: list,
) -> None:
    """Recursive parser. Emits __TX_n__ placeholders for translatable text."""

    buffer: List[str] = []

    def flush_buffer():
        if not buffer:
            return
        chunk = "".join(buffer)
        if chunk.strip():
            idx = len(translate_slots)
            translate_slots.append(chunk)
            out.append(f"__TX_{idx}__")
        else:
            out.append(chunk)
        buffer.clear()

    i = 0
    while i < len(text):
        ch = text[i]

        # Comments
        if ch == "%" and not _latex_is_escaped(text, i):
            flush_buffer()
            end = text.find("\n", i)
            if end == -1:
                out.append(text[i:])
                return
            out.append(text[i : end + 1])
            i = end + 1
            continue

        # Inline/display math $$...$$ or $...$
        if ch == "$" and not _latex_is_escaped(text, i):
            flush_buffer()
            if i + 1 < len(text) and text[i + 1] == "$":
                end = _latex_find_math_end(text, i + 2, "$$")
                out.append(text[i:end])
                i = end
            else:
                end = _latex_find_math_end(text, i + 1, "$")
                out.append(text[i:end])
                i = end
            continue

        # Math delimiters \(...\) and \[...\]
        if text.startswith("\\(", i) or text.startswith("\\[", i):
            flush_buffer()
            closing = "\\)" if text.startswith("\\(", i) else "\\]"
            end = text.find(closing, i + 2)
            if end == -1:
                out.append(text[i:])
                return
            out.append(text[i : end + 2])
            i = end + 2
            continue

        # Braces
        if ch in "{}":
            flush_buffer()
            out.append(ch)
            i += 1
            continue

        # Commands
        if ch == "\\":
            flush_buffer()
            cmd_start = i
            i += 1
            if i >= len(text):
                out.append("\\")
                break
            if text[i].isalpha():
                j = i
                while j < len(text) and text[j].isalpha():
                    j += 1
                cmd_name = text[i:j]
                cmd_token = text[cmd_start:j]

                # Verbatim-like inline commands
                if cmd_name in LATEX_VERBATIM_COMMANDS:
                    k = j
                    if k < len(text) and text[k] == "*":
                        k += 1
                        cmd_token = text[cmd_start:k]
                    if k >= len(text):
                        out.append(cmd_token)
                        i = k
                        continue
                    delim = text[k]
                    end = text.find(delim, k + 1)
                    if end == -1:
                        out.append(text[cmd_start:])
                        return
                    out.append(text[cmd_start : end + 1])
                    i = end + 1
                    continue

                # \begin{env} / \end{env}
                if cmd_name in ("begin", "end"):
                    out.append(cmd_token)
                    ws, pos = _latex_consume_whitespace(text, j)
                    if ws:
                        out.append(ws)
                    group, end_pos = _latex_read_group(text, pos, "{", "}")
                    if not group:
                        i = j
                        continue
                    out.append(group)
                    i = end_pos
                    if cmd_name == "begin":
                        env_name = group[1:-1]
                        if env_name in LATEX_PROTECTED_ENVIRONMENTS:
                            end_env = _latex_find_environment_end(text, i, env_name)
                            out.append(text[i:end_env])
                            i = end_env
                    continue

                # Commands with argument rules
                rule = LATEX_COMMAND_RULES.get(cmd_name)
                out.append(cmd_token)
                i = j
                if rule:
                    # Optional args
                    while True:
                        ws, i = _latex_consume_whitespace(text, i)
                        if ws:
                            out.append(ws)
                        if i < len(text) and text[i] == "[":
                            group, end_pos = _latex_read_group(text, i, "[", "]")
                            if not group:
                                break
                            if rule.get("optional") == "protect":
                                out.append(group)
                            else:
                                inner = group[1:-1]
                                inner_out: list = []
                                _parse_latex(inner, source_lang, target_lang, service, translate_slots, inner_out)
                                out.append("[" + "".join(inner_out) + "]")
                            i = end_pos
                            continue
                        break

                    # Mandatory args
                    arg_modes = rule.get("mandatory", [])
                    for mode in arg_modes:
                        ws, i = _latex_consume_whitespace(text, i)
                        if ws:
                            out.append(ws)
                        if i < len(text) and text[i] == "{":
                            group, end_pos = _latex_read_group(text, i, "{", "}")
                            if not group:
                                break
                            if mode == "protect":
                                out.append(group)
                            else:
                                inner = group[1:-1]
                                inner_out = []
                                _parse_latex(inner, source_lang, target_lang, service, translate_slots, inner_out)
                                out.append("{" + "".join(inner_out) + "}")
                            i = end_pos
                        else:
                            break
                continue

            # Single-character command
            out.append(text[cmd_start : i + 1])
            i += 1
            continue

        buffer.append(ch)
        i += 1

    flush_buffer()


def translate_latex_preserve_structure(
    text: str, source_lang: str, target_lang: str, service: TranslationService
) -> str:
    if not text or not text.strip():
        return text

    translate_slots: list = []
    out: list = []

    _parse_latex(text, source_lang, target_lang, service, translate_slots, out)

    if not translate_slots:
        return "".join(out)

    # Single batch call for all collected text chunks
    translated_chunks = service.translate_batch(translate_slots, source_lang, target_lang)

    # Rebuild: replace __TX_n__ placeholders with translated text
    result = "".join(out)
    def _replace(m):
        idx = int(m.group(1))
        chunk = translated_chunks[idx]
        # Preserve linebreaks that were in the original chunk
        original = translate_slots[idx]
        leading = original[: len(original) - len(original.lstrip())]
        trailing = original[len(original.rstrip()) :]
        return leading + chunk.strip() + trailing

    return _SLOT_RE.sub(_replace, result)
