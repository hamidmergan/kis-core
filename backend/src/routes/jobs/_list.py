"""GET /jobs/my und /jobs/stream - Jobliste + SSE-Stream."""

import json as json_lib

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from src import database as db
from src.dependencies import get_current_user

from src.routes.jobs._shared import (
    _REDIS_URL,
    _expand_tool_filter,
    _format_job_rows,
    _tools_matching_query,
)


router = APIRouter()


@router.get("/my")
async def get_my_jobs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=20, le=200),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    tool_filter: str = Query(default=""),
):
    """Return jobs for the current user with optional search and date filters."""
    user_id = current_user.get("user_id", 0)
    extra_tools = _tools_matching_query(q) if q else None
    tool_filter_list = _expand_tool_filter(tool_filter)
    jobs, total = db.get_jobs_by_user(
        user_id, limit=limit, offset=offset, q=q,
        date_from=date_from, date_to=date_to,
        extra_tools=extra_tools, tool_filter=tool_filter_list,
    )
    return {"jobs": _format_job_rows(jobs), "total": total}


@router.get("/stream")
async def job_stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """SSE endpoint: streams job list updates whenever a job status changes."""
    import redis.asyncio as aioredis

    user_id = current_user.get("user_id", 0)

    async def event_generator():
        # Send initial snapshot immediately on connect
        jobs, total = db.get_jobs_by_user(user_id, limit=20)
        yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs), 'total': total})}\n\n"

        r = aioredis.from_url(_REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"jobs:{user_id}")
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if msg and msg["type"] == "message":
                    jobs, total = db.get_jobs_by_user(user_id, limit=20)
                    yield f"data: {json_lib.dumps({'jobs': _format_job_rows(jobs), 'total': total})}\n\n"
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
