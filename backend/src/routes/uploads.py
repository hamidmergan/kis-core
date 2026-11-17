"""HTTP side of the direct uploads, one set of routes for every tool.

The rules table says per tool which files fit and who may send them. A tool that takes
large files gets one entry here and then accepts an upload token besides the classic file.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.dependencies import get_current_user
from src.dependencies_rbac import get_user_permissions, require_tool_access
from src.i18n import get_locale, t
from src.permissions import Permissions
from src.security.rate_limit import check_upload_limit
from src.services import direct_upload as du
from src.services.tool_limits import max_upload_bytes
from src.utils.file_validation import TRANSCRIPTION_EXTENSIONS

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _tool_access(tool: str):
    """The same check the tool's own routes run, so the upload grants nothing extra."""
    check = require_tool_access(tool)

    async def authorize(user: dict, perms: Permissions, context: dict, locale: str) -> None:
        await check(user=user, perms=perms, locale=locale)
    return authorize


# One entry per tool that takes files above the proxy limit.
RULES: dict[str, du.UploadRule] = {
    "transcription": du.UploadRule(TRANSCRIPTION_EXTENSIONS, lambda: max_upload_bytes(), _tool_access("transcription")),
}


def rule_for(tool: str, locale: str) -> du.UploadRule:
    rule = RULES.get(tool)
    if rule is None:
        raise HTTPException(status_code=403, detail=t("auth.toolForbidden", locale))
    return rule


class StartBody(BaseModel):
    tool: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=500)
    size: int = Field(ge=0)
    context: dict[str, str] = Field(default_factory=dict)


class PartNumbers(BaseModel):
    parts: list[int] = Field(min_length=1, max_length=du.MAX_URLS_PER_CALL)


@router.post("")
async def start_upload(
    body: StartBody,
    request: Request,
    current_user: dict = Depends(get_current_user),
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
):
    """Opens a direct upload, or answers direct False when the classic route fits better."""
    rule = rule_for(body.tool, locale)
    await _maybe_await(rule.authorize(current_user, perms, body.context, locale))
    user_id = current_user["user_id"]
    check_upload_limit(user_id, locale=locale)
    await _maybe_await(rule.precheck(current_user, body.context, body.filename, body.size, locale))
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return du.start(body.tool, rule, body.filename, body.size, user_id, body.context,
                    request.headers.get("origin") or "", host, locale)


@router.get("/{token}")
def upload_status(token: str, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Which parts already arrived, so a broken upload goes on where it stopped."""
    return du.status(token, current_user["user_id"], locale)


@router.post("/{token}/urls")
def upload_urls(token: str, body: PartNumbers, current_user: dict = Depends(get_current_user),
                locale: str = Depends(get_locale)):
    """Signs a small batch of parts."""
    return du.urls(token, body.parts, current_user["user_id"], locale)


@router.post("/{token}/complete")
def complete_upload(token: str, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Joins the parts and checks the file, the tool then takes it by the token."""
    return du.complete(token, current_user["user_id"], locale)


@router.delete("/{token}")
def abort_upload(token: str, current_user: dict = Depends(get_current_user), locale: str = Depends(get_locale)):
    """Drops an upload and everything already sent."""
    return du.abort(token, current_user["user_id"], locale)


async def _maybe_await(value):
    """Rules may be plain functions or coroutines."""
    if hasattr(value, "__await__"):
        return await value
    return value
