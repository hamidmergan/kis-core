from src.services.translation import TranslationService

TAB_PLACEHOLDER = "\u27e8TAB\u27e9"


def translate_run_text_preserve_linebreaks(
    text: str, source_lang: str, target_lang: str, service: TranslationService
) -> str:
    """Translates text preserving linebreaks, leading/trailing whitespace and tabs."""
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
    """Translates text preserving linebreaks, leading/trailing whitespace and tabs."""
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


def translate_paragraph_preserve_runs(
    paragraph, source_lang: str, target_lang: str, service: TranslationService
):
    """Translates a paragraph (docx/pptx) preserving per-run formatting."""
    runs = list(paragraph.runs)
    if not runs:
        paragraph.text = translate_text_preserve_linebreaks(
            paragraph.text, source_lang, target_lang, service
        )
        return

    if len(runs) == 1:
        runs[0].text = translate_text_preserve_linebreaks(
            runs[0].text, source_lang, target_lang, service
        )
        return

    for run in runs:
        if run.text.strip():
            run.text = translate_run_text_preserve_linebreaks(
                run.text, source_lang, target_lang, service
            )
