"""GO/NO-GO gate for citation grounding. Loads the real units of the audited
workspace's sources and checks the matcher resolves each chip to the CORRECT
segment/page. Run from backend/:  python scripts/citation_match_eval.py

Timestamps are compared with a tolerance window (a claim spans 2-3 segments);
pages are compared exactly. Exit 0 if >=6 previously-wrong cases are fixed and
none regress; exit 1 otherwise."""
import json
import sys
from pathlib import Path

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


def _time_ok(resolved_s, correct_str):
    return resolved_s is not None and abs(resolved_s - _parse_ts(correct_str)) <= TOLERANCE_S


def _media_units(source):
    return [Unit(page=None, start_time=s["start"], end_time=s["end"], raw_text=s["text"])
            for s in _load_transcript_segments(source)]


def _pdf_units(source_id):
    return [Unit(page=c["page_number"], start_time=None, end_time=None, raw_text=c["content"])
            for c in chunk_repo.get_aia_chunks_by_source(source_id) if c.get("content")]


def main() -> int:
    by_name = {s["filename"]: s for s in source_repo.list_all_sources_for_eval()}
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
