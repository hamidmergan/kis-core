"""Takes finished summary and presentation runs over as the demo results, safe to run again.

    docker exec kis-backend python scripts/demo_ergebnis_uebernehmen.py <job_uuid> [<job_uuid> ...]
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from src import database as db  # noqa: E402
from src.features.praesentation import store  # noqa: E402
from src.features.summary.models import INSTRUCTIONS_FILE  # noqa: E402
from src.routes.praesentation.media import _bildplaetze  # noqa: E402
from src.services import sources  # noqa: E402
from src.storage import get_file, get_job_file, job_file_exists  # noqa: E402

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
FERTIG = ("completed", "success")


def _schreiben(pfad: Path, daten: bytes) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(daten)


def zusammenfassung(job: dict, workspace: str) -> str:
    """The Markdown and Word result into the folder of its template, the material into demo.json."""
    uid, uuid = job["user_id"], job["job_uuid"]
    slug = json.loads(get_job_file(uid, uuid, "summary_params.json"))["template_slug"]
    ordner = DEMO_DIR / "zusammenfassung" / slug
    shutil.rmtree(ordner, ignore_errors=True)
    stamm = Path(job["result_filename"] or f"{slug}.md").stem
    _schreiben(ordner / f"{stamm}.md", get_file(job["result_path"]))
    _schreiben(ordner / f"{stamm}.docx", get_job_file(uid, uuid, "output.docx"))
    anweisung = get_job_file(uid, uuid, INSTRUCTIONS_FILE).decode() if job_file_exists(uid, uuid, INSTRUCTIONS_FILE) else ""
    material = {"workspace": workspace, "dateien": [q.dateiname for q in sources.load_sources(uid, uuid)],
                "anweisung": anweisung}
    (DEMO_DIR / "zusammenfassung" / "demo.json").write_text(json.dumps(material, ensure_ascii=False, indent=2),
                                                            encoding="utf-8")
    return f"Zusammenfassung {slug}"


def praesentation(job: dict, workspace: str) -> str:
    """Outline, slides, pictures, previews and the file, as the demo route reads them."""
    uid, uuid = job["user_id"], job["job_uuid"]
    params = store.load_params(uid, uuid)
    outline = store.load_outline(uid, uuid)
    slides = store.load_slides(uid, uuid)
    ordner = DEMO_DIR / "praesentation"
    shutil.rmtree(ordner, ignore_errors=True)
    for s in slides:
        if store.has_preview(uid, uuid, s.id):
            _schreiben(ordner / store.preview_name(s.id), store.get_preview(uid, uuid, s.id))
        for slot in _bildplaetze(s):
            if store.has_image(uid, uuid, s.id, slot):
                _schreiben(ordner / store.image_name(s.id, slot), store.get_image(uid, uuid, s.id, slot))
    _schreiben(ordner / store.DECK_FILE, store.get_deck(uid, uuid))

    dateien: list[str] = []
    if params and params.workspace_id:
        workspace = (db.get_aia_workspace_by_id(params.workspace_id) or {}).get("title") or workspace
        namen = {q["uuid"]: q["filename"] for q in db.get_aia_sources_by_workspace(params.workspace_id)}
        dateien = [namen[u] for u in params.source_uuids if u in namen]
    ansicht = {
        "params": params.model_dump() if params else None,
        "outline": outline.model_dump() if outline else None,
        "slides": [s.model_dump() for s in slides],
        "workspace": workspace,
        "dateien": dateien,
    }
    (ordner / "ansicht.json").write_text(json.dumps(ansicht, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"Präsentation mit {len(slides)} Folien"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("jobs", nargs="+", help="UUIDs fertiger Läufe")
    parser.add_argument("--workspace", default="Projektmanagement",
                        help="Name des Workspace, falls der Lauf ihn nicht kennt")
    args = parser.parse_args()

    for uuid in args.jobs:
        job = db.get_job(uuid)
        if not job or job["status"] not in FERTIG:
            print(f"{uuid}: kein fertiger Lauf", file=sys.stderr)
            return 1
        if job["tool"] == "summary":
            print(f"{uuid}: {zusammenfassung(job, args.workspace)}")
        elif job["tool"] == "praesentation":
            print(f"{uuid}: {praesentation(job, args.workspace)}")
        else:
            print(f"{uuid}: {job['tool']} hat keine Demo", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
