"""Keine Route hält den Faden an, der die Seiten für alle ausliefert.

Eine `async def`-Route läuft direkt in der Ereignisschleife. Wartet sie auf nichts,
macht sie ihre ganze Arbeit dort, jeder Datenbank- und Speicherzugriff hält dann alle
anderen Anfragen dieses Prozesses an. Lasttest 26.09.: bei 20 Leuten luden Seiten ewig.
Eine normale `def`-Route lässt FastAPI in seinem Fadenpool laufen.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
# Needs the running loop itself, it starts a background task with asyncio.create_task.
AUSNAHMEN = {("routes/admin/maintenance.py", "get_maintenance")}


def _async_routen_ohne_warten():
    for pfad in list((SRC / "routes").rglob("*.py")) + list((SRC / "features").rglob("routes/**/*.py")):
        baum = ast.parse(pfad.read_text())
        for knoten in baum.body:
            if not isinstance(knoten, ast.AsyncFunctionDef):
                continue
            ist_route = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                            and d.func.attr in ("get", "post", "put", "patch", "delete")
                            for d in knoten.decorator_list)
            wartet = any(isinstance(n, (ast.Await, ast.AsyncFor, ast.AsyncWith, ast.AsyncFunctionDef))
                         and n is not knoten for n in ast.walk(knoten))
            rel = str(pfad.relative_to(SRC))
            if ist_route and not wartet and (rel, knoten.name) not in AUSNAHMEN:
                yield f"{rel}:{knoten.lineno} {knoten.name}"


def test_keine_async_route_ohne_warten():
    assert list(_async_routen_ohne_warten()) == []
