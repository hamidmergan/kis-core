"""The job list and the SSE stream."""

import json as json_lib
import time

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale
from src.security import presence

from src.routes.jobs._shared import (
    _REDIS_URL,
    _expand_tool_filter,
    _format_job_rows,
    _tools_matching_query,
)


router = APIRouter()

_KEEPALIVE_SECONDS = 20


@router.get("/my")
def get_my_jobs(
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    tool_filter: str = Query(default=""),
):
    """Return jobs for the current user with optional search and date filters."""
    user_id = current_user.get("user_id", 0)
    extra_tools = _tools_matching_query(q, locale) if q else None
    tool_filter_list = _expand_tool_filter(tool_filter)
    jobs, total = db.get_jobs_by_user(
        user_id, limit=limit, offset=offset, q=q,
        date_from=date_from, date_to=date_to,
        extra_tools=extra_tools, tool_filter=tool_filter_list,
    )
    return {"jobs": _format_job_rows(jobs, locale, is_admin_user(current_user)), "total": total}


@router.get("/stream")
async def job_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """SSE endpoint: streams job list updates whenever a job status changes."""
    import redis.asyncio as aioredis

    user_id = current_user.get("user_id", 0)
    is_admin = is_admin_user(current_user)

    async def event_generator():
        # Send initial snapshot immediately on connect
        jobs, total = db.get_jobs_by_user(user_id, limit=20)
        yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs, locale, is_admin), 'total': total})}\n\n"

        r = aioredis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"jobs:{user_id}")
        last_sent = time.monotonic()
        # The hour is written rarely, the heartbeat often.
        last_hour = 0.0
        presence.touch(user_id)
        presence.mark_hour(user_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg["type"] == "message":
                    jobs, total = db.get_jobs_by_user(user_id, limit=20)
                    yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs, locale, is_admin), 'total': total})}\n\n"
                    last_sent = time.monotonic()
                elif time.monotonic() - last_sent >= _KEEPALIVE_SECONDS:
                    # A heartbeat so intermediaries do not cut the idle connection.
                    yield ": ping\n\n"
                    last_sent = time.monotonic()
                    # The same loop records presence, at no extra cost.
                    presence.touch(user_id)
                    if time.monotonic() - last_hour >= 300:
                        presence.mark_hour(user_id)
                        last_hour = time.monotonic()
        finally:
            await pubsub.unsubscribe(f"jobs:{user_id}")
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
