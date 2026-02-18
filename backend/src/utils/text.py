from src.services.translation import TranslationService

TAB_PLACEHOLDER = "\u27e8TAB\u27e9"
NL_PLACEHOLDER = "\u27e8NL\u27e9"


def _encode_whitespace(text: str) -> tuple[str, str, str]:
    """Extract leading/trailing whitespace and encode tabs and newlines."""
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]
    inner = text.strip()
    inner = inner.replace("\t", TAB_PLACEHOLDER).replace("\n", NL_PLACEHOLDER)
    return leading, inner, trailing


def _decode_whitespace(text: str, leading: str, trailing: str) -> str:
    """Restore tabs and newlines and re-attach surrounding whitespace."""
    text = text.replace(TAB_PLACEHOLDER, "\t").replace(NL_PLACEHOLDER, "\n")
    return leading + text + trailing


# ── Single-text helpers (used by Markdown, LaTeX, filename translation) ──────

def translate_run_text_preserve_linebreaks(
    text: str, source_lang: str, target_lang: str, service: TranslationService
) -> str:
    """Translate text preserving linebreaks, leading/trailing whitespace and tabs."""
    text_with_placeholder = text.replace("\t", TAB_PLACEHOLDER)
    lines = text_with_placeholder.split("\n")
    translated_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            leading_ws = line[: len(line) - len(line.lstrip())]
            trailing_ws = line[len(line.rstrip()) :]
            translated = service.translate_text(stripped, source_lang, target_lang)
            translated_lines.append(leading_ws + translated + trailing_ws)
        else:
            translated_lines.append(line)
    result = "\n".join(translated_lines)
    return result.replace(TAB_PLACEHOLDER, "\t")


def translate_text_preserve_linebreaks(
    text: str, source_lang: str, target_lang: str, service: TranslationService
) -> str:
    """Translate text preserving linebreaks, leading/trailing whitespace and tabs."""
    return translate_run_text_preserve_linebreaks(text, source_lang, target_lang, service)


# ── Batch helpers for PPTX / DOCX (1 DeepL call per document) ───────────────

class _RunRef:
    """Holds a reference to a run or paragraph and the encoded text to translate."""
    __slots__ = ("obj", "attr", "leading", "trailing", "encoded")

    def __init__(self, obj, attr: str, leading: str, encoded: str, trailing: str):
        self.obj = obj
        self.attr = attr
        self.leading = leading
        self.encoded = encoded
        self.trailing = trailing


def collect_paragraph_runs(paragraph, refs: list[_RunRef]) -> None:
    """
    Collect all translatable text pieces from a paragraph into refs.
    Newlines and tabs are encoded as placeholders so DeepL sees a single line.
    """
    runs = list(paragraph.runs)

    if not runs:
        text = paragraph.text
        if text and text.strip():
            leading, encoded, trailing = _encode_whitespace(text)
            refs.append(_RunRef(paragraph, "text", leading, encoded, trailing))
        return

    if len(runs) == 1:
        text = runs[0].text
        if text and text.strip():
            leading, encoded, trailing = _encode_whitespace(text)
            refs.append(_RunRef(runs[0], "text", leading, encoded, trailing))
        return

    for run in runs:
        text = run.text
        if text and text.strip():
            leading, encoded, trailing = _encode_whitespace(text)
            refs.append(_RunRef(run, "text", leading, encoded, trailing))


def apply_translations(refs: list[_RunRef], translated: list[str]) -> None:
    """Write translated strings back to their source objects."""
    for ref, t in zip(refs, translated):
        setattr(ref.obj, ref.attr, _decode_whitespace(t, ref.leading, ref.trailing))


# ── Legacy single-paragraph helper (used by Markdown / LaTeX translators) ───

def translate_paragraph_preserve_runs(
    paragraph, source_lang: str, target_lang: str, service: TranslationService
) -> None:
    """Translate a single paragraph in-place (one DeepL call per run)."""
    refs: list[_RunRef] = []
    collect_paragraph_runs(paragraph, refs)
    if not refs:
        return
    texts = [r.encoded for r in refs]
    translated = service.translate_batch(texts, source_lang, target_lang)
    apply_translations(refs, translated)
