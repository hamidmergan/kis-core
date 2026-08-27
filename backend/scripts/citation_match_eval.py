"""Checks whether the matcher puts every chip on the right spot."""
import json
import sys
from pathlib import Path

# Backend root on sys.path so src.* is importable.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from src.core.db.pool import get_connection
import psycopg2.extras
from src.features.ai_assistant.repository import chunks as chunk_repo
from src.features.ai_assistant.repository import sources as source_repo
from src.features.ai_assistant.routes._helpers import (
    _load_transcript_segments,
    _format_timestamp,
    _parse_ts,
)
from src.features.ai_assistant.routes._citation_match import Unit, match_query

CASES = json.loads((Path(__file__).parent / "citation_audit_cases.json").read_text())
TOLERANCE_S = 45.0

# Resolve sources only inside this workspace, otherwise equal file names mismatch.
WORKSPACE_UUID = "1ea7b2fa-b237-4bbd-801b-c9793d388984"


def _resolve_workspace_id(uuid: str) -> int:
    """Resolve the integer workspace_id from the workspace UUID."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id FROM aia_workspaces WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Workspace not found for UUID {uuid!r}")
    return row["id"]


def _time_ok(resolved_s, correct_str):
    return resolved_s is not None and abs(resolved_s - _parse_ts(correct_str)) <= TOLERANCE_S


def _media_units(source):
    return [Unit(page=None, start_time=s["start"], end_time=s["end"], raw_text=s["text"])
            for s in _load_transcript_segments(source)]


def _pdf_units(source_id):
    return [Unit(page=c["page_number"], start_time=None, end_time=None, raw_text=c["content"])
            for c in chunk_repo.get_aia_chunks_by_source(source_id) if c.get("content")]


def main() -> int:
    workspace_id = _resolve_workspace_id(WORKSPACE_UUID)
    print(f"Resolved workspace: uuid={WORKSPACE_UUID}  id={workspace_id}")
    all_sources = source_repo.list_all_sources_for_eval()
    workspace_sources = [s for s in all_sources if s["workspace_id"] == workspace_id]
    print(f"Sources in audited workspace: {len(workspace_sources)} (total in DB: {len(all_sources)})")
    by_name = {s["filename"]: s for s in workspace_sources}
    # Sanity-check: confirm VL1 transcript has ~137 segments (not 774 from wrong workspace)
    vl1_src = by_name.get("VL1_25-03-2026.webm")
    if vl1_src:
        vl1_units = _media_units(vl1_src)
        print(f"VL1 segment count in audited workspace: {len(vl1_units)} (expected ~137)")
    else:
        print("WARNING: VL1_25-03-2026.webm not found in audited workspace!")
    rows, regressions, fixes = [], 0, 0
    for case in CASES:
        src = by_name.get(case["filename"])
        if not src:
            print(f"SKIP (source not found): {case['filename']}")
            continue
        if "correct_time" in case:
            units = _media_units(src)
            r = match_query(case["keyword"], units, typed_pos=_parse_ts(case["cited"]))
            resolved_s = r.unit.start_time if r.unit else None
            got = _format_timestamp(resolved_s) if resolved_s is not None else "—"
            want, cited = case["correct_time"], case["cited"]
            ok = _time_ok(resolved_s, case["correct_time"])
            was_wrong = not _time_ok(_parse_ts(case["cited"]), case["correct_time"])
        else:
            units = _pdf_units(src["id"])
            r = match_query(case["keyword"], units, typed_pos=case["cited_page"])
            got = f"S.{r.unit.page}" if r.unit else "—"
            want, cited = f"S.{case['correct_page']}", f"S.{case['cited_page']}"
            ok = bool(r.unit) and r.unit.page == case["correct_page"]
            was_wrong = case["cited_page"] != case["correct_page"]
        if ok and was_wrong:
            fixes += 1
        if not ok and not was_wrong:
            regressions += 1
        rows.append((case["filename"][:18], cited, got, want, r.match_type, "OK" if ok else "XX"))

    print(f"\n{'source':20}{'cited':8}{'got':8}{'want':8}{'type':7}{'res'}")
    for r in rows:
        print(f"{r[0]:20}{r[1]:8}{r[2]:8}{r[3]:8}{r[4]:7}{r[5]}")
    print(f"\nfixes={fixes}  regressions={regressions}  total={len(rows)}")
    return 0 if regressions == 0 and fixes >= 6 else 1


if __name__ == "__main__":
    sys.exit(main())
