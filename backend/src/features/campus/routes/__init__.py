"""Routes of the campus assistant, every one behind the tool right."""
from fastapi import APIRouter, Depends

from src.dependencies_rbac import require_tool_access
from src.features.campus.routes import chat, chats

router = APIRouter(prefix="/campus", dependencies=[Depends(require_tool_access("campus"))])
for m in (chat, chats):
    router.include_router(m.router)
