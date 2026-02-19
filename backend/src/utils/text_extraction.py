"""Shared text-extraction helpers used by TTS and Script routes."""

import re
from io import BytesIO

from docx import Document
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def extract_text_md(content: bytes) -> str:
    text = content.decode("utf-8")
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Convert links to just the link text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Remove headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_tex(content: bytes) -> str:
    text = content.decode("utf-8")
    # Remove comments
    text = re.sub(r"(?<!\\)%.*$", "", text, flags=re.MULTILINE)
    # Remove preamble (everything before \begin{document})
    match = re.search(r"\\begin\{document\}", text)
    if match:
        text = text[match.end():]
    # Remove \end{document}
    text = re.sub(r"\\end\{document\}", "", text)
    # Remove math environments
    text = re.sub(r"\$\$[\s\S]*?\$\$", "", text)
    text = re.sub(r"\$[^$]+\$", "", text)
    text = re.sub(r"\\\[[\s\S]*?\\\]", "", text)
    text = re.sub(r"\\\(.*?\\\)", "", text)
    # Remove verbatim/lstlisting environments
    text = re.sub(
        r"\\begin\{(verbatim|lstlisting|minted)\}[\s\S]*?\\end\{\1\}", "", text
    )
    # Convert common text commands to their content
    text = re.sub(r"\\(?:textbf|textit|emph|underline|texttt)\{([^}]*)\}", r"\1", text)
    # Convert section commands to their titles
    text = re.sub(
        r"\\(?:section|subsection|subsubsection|chapter|paragraph|subparagraph)\*?\{([^}]*)\}",
        r"\1",
        text,
    )
    # Remove remaining commands (but keep their mandatory argument text for some)
    text = re.sub(r"\\(?:label|ref|cite|url|href|includegraphics)\{[^}]*\}", "", text)
    # Remove \begin{...} and \end{...}
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", text)
    # Remove remaining backslash commands without braces
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    # Remove braces
    text = re.sub(r"[{}]", "", text)
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_docx(content: bytes) -> str:
    doc = Document(BytesIO(content))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_text_pptx(content: bytes) -> str:
    prs = Presentation(BytesIO(content))
    texts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            _collect_shape_text(shape, texts)
    return "\n".join(texts)


def _collect_shape_text(shape, texts: list) -> None:
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            text = paragraph.text.strip()
            if text:
                texts.append(text)
    if shape.has_table:
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        texts.append(text)
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for subshape in shape.shapes:
            _collect_shape_text(subshape, texts)


def extract_text_txt(content: bytes) -> str:
    return content.decode("utf-8", errors="replace")


def extract_text_srt(content: bytes) -> str:
    lines = []
    for line in content.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.match(r"^\d+$", stripped):
            continue
        if re.match(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}", stripped):
            continue
        lines.append(stripped)
    return " ".join(lines)


def extract_text_vtt(content: bytes) -> str:
    lines = []
    for line in content.decode("utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("WEBVTT") or stripped.startswith("NOTE"):
            continue
        if re.match(r"^\d+$", stripped):
            continue
        if re.match(r"[\d:]+\.\d{3}\s*-->\s*[\d:]+\.\d{3}", stripped):
            continue
        lines.append(stripped)
    return " ".join(lines)


EXTRACTORS = {
    ".txt": extract_text_txt,
    ".md": extract_text_md,
    ".tex": extract_text_tex,
    ".srt": extract_text_srt,
    ".vtt": extract_text_vtt,
    ".docx": extract_text_docx,
    ".pptx": extract_text_pptx,
}
