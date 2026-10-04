"""Jeder eingereihte Auftrag merkt sich seine Celery-Nummer.

Der Aufseher erkennt einen wartenden Auftrag nur über diese Nummer beim Broker. Ohne sie
hält er einen Auftrag, der brav in der Schlange steht, nach zehn Minuten für verloren.
"""

import ast
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "src" / "routes"
# Einreihungen, die nicht zu einer Zeile in der Auftragstabelle gehören.
AUSNAHMEN = {
    ("admin/maintenance.py", "run_reindex_all_sources"),
    # The campus index has no row in the job table, its state lives in the settings.
    ("admin/campus.py", "run_crawl"),
    ("admin/campus.py", "run_index_document"),
    ("admin/campus.py", "run_sync_places_file"),
}


def _einreihungen(pfad: Path):
    baum = ast.parse(pfad.read_text())
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) or isinstance(knoten, ast.AsyncFunctionDef):
            quelltext = ast.get_source_segment(pfad.read_text(), knoten) or ""
            for aufruf in ast.walk(knoten):
                if (isinstance(aufruf, ast.Call) and isinstance(aufruf.func, ast.Attribute)
                        and aufruf.func.attr in ("delay", "apply_async")
                        and isinstance(aufruf.func.value, ast.Name)):
                    yield aufruf.func.value.id, quelltext


def test_jede_route_speichert_die_nummer_ihres_auftrags():
    fehlend = []
    for pfad in ROUTES.rglob("*.py"):
        rel = str(pfad.relative_to(ROUTES))
        for task, quelltext in _einreihungen(pfad):
            if (rel, task) in AUSNAHMEN:
                continue
            if "set_job_celery_task_id" not in quelltext:
                fehlend.append(f"{rel}: {task}")
    assert fehlend == []
