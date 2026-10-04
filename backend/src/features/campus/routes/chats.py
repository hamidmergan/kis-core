"""Chat history of one person: list, rename, delete, read messages, read limits."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.dependencies import get_current_user
from src.features.campus.repository import chats as chat_repo
from src.features.campus.services import settings as campus_settings
from src.i18n import get_locale, t
from src.limits import CAMPUS_MAX_QUESTIONS_PER_CHAT, CAMPUS_QUESTION_MAX_CHARS, CAMPUS_TITLE_MAX_CHARS

router = APIRouter(tags=["campus: chats"])


class RenameBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=CAMPUS_TITLE_MAX_CHARS)


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


@router.get("/config")
def campus_config(current_user: dict = Depends(get_current_user)):
    cfg = campus_settings.read()
    return {
        "map_url": cfg.shown_map_url,
        "retention_days": cfg.retention_days,
        "max_question_chars": CAMPUS_QUESTION_MAX_CHARS,
        "max_questions_per_chat": CAMPUS_MAX_QUESTIONS_PER_CHAT,
    }


@router.get("/chats")
def list_chats(current_user: dict = Depends(get_current_user)):
    return [
        {"id": c["id"], "title": c["title"], "question_count": c["question_count"],
         "created_at": _iso(c["created_at"]), "updated_at": _iso(c["updated_at"])}
        for c in chat_repo.list_chats(current_user["user_id"])
    ]


@router.patch("/chats/{chat_id}")
def rename_chat(chat_id: int, body: RenameBody, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    title = " ".join(body.title.split())
    if not title or not chat_repo.rename_chat(chat_id, current_user["user_id"], title):
        raise HTTPException(status_code=404, detail=t("campus.chatNotFound", locale))
    return {"id": chat_id, "title": title}


@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    if not chat_repo.delete_chat(chat_id, current_user["user_id"]):
        raise HTTPException(status_code=404, detail=t("campus.chatNotFound", locale))
    return {"deleted": True}


@router.get("/chats/{chat_id}/messages")
def list_messages(chat_id: int, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    chat = chat_repo.get_chat(chat_id, current_user["user_id"])
    if chat is None:
        raise HTTPException(status_code=404, detail=t("campus.chatNotFound", locale))
    return {
        "id": chat["id"], "title": chat["title"], "question_count": chat["question_count"],
        "messages": [
            {"id": m["id"], "role": m["role"], "content": m["content"], "sources": m["sources"] or [],
             "places": m["places"] or [], "no_source": m["no_source"],
             "created_at": _iso(m["created_at"])}
            for m in chat_repo.list_messages(chat_id)
        ],
    }
