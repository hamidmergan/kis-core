"""The title of a new chat is its first question, shortened."""
from src.limits import CAMPUS_TITLE_MAX_CHARS


def make_title(question: str, max_chars: int = CAMPUS_TITLE_MAX_CHARS) -> str:
    text = " ".join(question.split())
    if len(text) <= max_chars:
        return text or "Chat"
    cut = text[:max_chars]
    space = cut.rfind(" ")
    if space > max_chars // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:.!?") + "…"
