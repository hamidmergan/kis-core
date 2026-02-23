import re
from typing import List, Tuple

from src.services.translation import TranslationService


def _split_markdown_by_code_fences(text: str) -> List[Tuple[bool, str]]:
    if not text:
        return [(False, text)]
    lines = text.splitlines(keepends=True)
    parts: List[Tuple[bool, str]] = []
    in_block = False
    fence_char = ""
    fence_len = 0
    buffer: List[str] = []

    for line in lines:
        if not in_block:
            match = re.match(r"^[ \t]{0,3}([`~]{3,})", line)
            if match:
                if buffer:
                    parts.append((False, "".join(buffer)))
                    buffer = []
                in_block = True
                fence_seq = match.group(1)
                fence_char = fence_seq[0]
                fence_len = len(fence_seq)
                buffer = [line]
            else:
                buffer.append(line)
        else:
            buffer.append(line)
            fence_pattern = (
                r"^[ \t]{0,3}" + re.escape(fence_char) + "{" + str(fence_len) + r",}\s*$"
            )
            if re.match(fence_pattern, line.rstrip("\n")):
                parts.append((True, "".join(buffer)))
                buffer = []
                in_block = False
                fence_char = ""
                fence_len = 0

    if buffer:
        parts.append((in_block, "".join(buffer)))

    return parts


def translate_markdown_preserve_code_blocks(
    text: str, source_lang: str, target_lang: str, service: TranslationService
) -> str:
    parts = _split_markdown_by_code_fences(text)

    # Collect all non-code chunks and their indices
    indices: List[int] = []
    texts_to_translate: List[str] = []
    for i, (is_code, chunk) in enumerate(parts):
        if not is_code and chunk and chunk.strip():
            indices.append(i)
            texts_to_translate.append(chunk)

    # Single batch call for all translatable chunks
    if texts_to_translate:
        translated = service.translate_batch(texts_to_translate, source_lang, target_lang)
        parts_list = list(parts)
        for i, t in zip(indices, translated):
            is_code, original = parts_list[i]
            parts_list[i] = (is_code, t)
        parts = parts_list  # type: ignore

    return "".join(chunk for _, chunk in parts)
