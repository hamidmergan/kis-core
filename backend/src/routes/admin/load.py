"""Auslastung: was die Maschine hergibt und wie voll sie gerade ist.

Ersetzt die fünf Zahlenfelder, die früher unter Einstellungen standen. Der
Unterschied ist nicht nur kosmetisch. Die Felder fragten den Menschen nach einer
Zahl, die er nicht wissen konnte, und gaben ihm danach keine Rückmeldung. Diese
Ansicht dreht das um: sie fragt nichts und zeigt alles.

Bewusst unter "Aufträge" und nicht unter "Einstellungen". Live-Zahlen sind keine
Einstellungen, und geschaut wird hier genau dann, wenn jemand meldet, dass es
hängt. Da will man die Auftragsliste daneben haben.
"""

import asyncio

from fastapi import APIRouter, Depends

from src.services import system_load
from src.services.system_capacity import capacity

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_TOOLS_JOBS, PERM_SET_SYSTEM

router = APIRouter(tags=["admin: load"])

# Die Auslastungskarte ist raus, die Route ruft niemand mehr auf.
_require = require_permission(PERM_SET_TOOLS_JOBS, PERM_SET_SYSTEM)


@router.get("/load")
async def get_load(_admin=Depends(_require)):
    """``async def``, weil die Prozessormessung zwei Messpunkte mit Abstand
    braucht und dafür wartet, ohne den Prozess anzuhalten.

    Alles Blockierende muss deshalb ausdrücklich in einen Thread. psycopg2 und
    redis-py warten blockierend, und in einer ``async def``-Route hält ein
    einziger solcher Aufruf den GANZEN Prozess an, also alle anderen Nutzer
    gleich mit (siehe limits.py, "Nebenläufigkeit im Web-Prozess"). Ausgerechnet
    die Auslastungsanzeige wäre damit selbst zur Last geworden, alle fünf
    Sekunden neu.
    """
    machine = capacity()
    return {
        "machine": machine.as_dict(),
        "cpu_percent": await system_load.cpu_percent(),
        "memory_used_bytes": system_load.memory_used_bytes(),
        "memory_total_bytes": machine.memory_bytes,
        "jobs": await asyncio.to_thread(system_load.job_slots),
        "uploads": await asyncio.to_thread(system_load.upload_slots),
    }
