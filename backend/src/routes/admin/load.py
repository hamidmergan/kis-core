"""Load: what the machine offers and how full it currently is."""

import asyncio

from fastapi import APIRouter, Depends

from src.services import system_load
from src.services.system_capacity import capacity

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_TOOLS_JOBS, PERM_SET_SYSTEM

router = APIRouter(tags=["admin: load"])

# The load card is gone, nobody calls the route any more.
_require = require_permission(PERM_SET_TOOLS_JOBS, PERM_SET_SYSTEM)


@router.get("/load")
async def get_load(_admin=Depends(_require)):
    """async, because the CPU measurement needs two samples with a gap."""
    machine = capacity()
    return {
        "machine": machine.as_dict(),
        "cpu_percent": await system_load.cpu_percent(),
        "memory_used_bytes": system_load.memory_used_bytes(),
        "memory_total_bytes": machine.memory_bytes,
        "jobs": await asyncio.to_thread(system_load.job_slots),
        "uploads": await asyncio.to_thread(system_load.upload_slots),
    }
