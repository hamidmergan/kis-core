# Citation Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every groundable bullet in a RAG chat answer carry a citation chip, and anchor every chip to the precise transcript segment (media) or page (PDF) of its claim.

**Architecture:** A deterministic, lexical post-stream pass. A shared matcher locates a claim's keyword in a source's *full* set of position-bearing units (transcript segments via `_load_transcript_segments`, page-chunks via `get_aia_chunks_by_source`). The existing resolver (`_resolve_citation_pages`) is upgraded to use it for precise positions; a new coverage pass fills uncited bullets. Each chip is tagged `exact|fuzzy|filled` and the non-exact ones get a subtle frontend cue.

**Tech Stack:** Python 3.11 (FastAPI backend, pytest), TypeScript/React (Next.js frontend, vitest/jest), PostgreSQL.

**Design spec:** `docs/superpowers/specs/2026-06-01-citation-grounding-design.md`

---

## Milestone 0 — Prototype gate (DE-RISK, do this first)

The make-or-break question is empirical: *can lexical token-overlap disambiguate this
repetitive corpus?* Build the matcher as a tested unit, then prove it on the 15 audited cases
against REAL source data. **Do not start Milestone 1 until the gate passes.**

### Task 1: Shared matcher module

**Files:**
- Create: `backend/src/features/ai_assistant/routes/_citation_match.py`
- Test: `backend/tests/test_citation_match.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_citation_match.py
from src.features.ai_assistant.routes._citation_match import Unit, match_query


def _seg(text, start):
    return Unit(page=None, start_time=start, end_time=start + 10, norm_text=None, raw_text=text)


def test_exact_substring_wins():
    units = [_seg("the scientific seminar is in the second semester", 227.0),
             _seg("citation styles apae and ieee", 60.0)]
    r = match_query("scientific seminar", units)
    assert r.match_type == "exact"
    assert r.unit.start_time == 227.0


def test_fuzzy_matches_paraphrase():
    units = [_seg("literature database management tools zotero citavi mendeley", 905.0),
             _seg("where to research web books journals", 60.0)]
    r = match_query("literature management software zotero citavi", units)
    assert r.match_type == "fuzzy"
    assert r.unit.start_time == 905.0


def test_ambiguous_below_margin_returns_none():
    units = [_seg("peer review feedback among students", 476.0),
             _seg("peer review feedback among students again", 1650.0)]
    r = match_query("peer review feedback students", units)
    assert r.match_type == "none"  # two near-equal hits -> not confident


def test_no_tokens_returns_none():
    units = [_seg("anything", 1.0)]
    assert match_query("", units).match_type == "none"


def test_typed_pos_disambiguates_exact_duplicates():
    units = [_seg("peer review", 476.0), _seg("peer review", 1650.0)]
    r = match_query("peer review", units, typed_pos=1600.0)
    assert r.unit.start_time == 1650.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_citation_match.py -v`
Expected: FAIL with `ModuleNotFoundError` / `ImportError` (module not created yet).

- [ ] **Step 3: Implement the matcher**

```python
# backend/src/features/ai_assistant/routes/_citation_match.py
"""Deterministic lexical matcher that locates a claim's keyword inside a source's
position-bearing units (transcript segments or page-chunks). Language-agnostic,
no embeddings, identical on every model tier. See the citation-grounding design spec."""
from __future__ import annotations

from dataclasses import dataclass

from ._helpers import _norm_for_match  # existing normalizer used by the resolver


@dataclass
class Unit:
    """One position-bearing piece of a source.

    Exactly one of (page) / (start_time) is set: page for PDF/doc/pptx, start_time
    for audio/video segments. ``norm_text`` is filled lazily from ``raw_text``.
    """
    page: int | None
    start_time: float | None
    end_time: float | None
    raw_text: str
    norm_text: str | None = None

    def normalized(self) -> str:
        if self.norm_text is None:
            self.norm_text = _norm_for_match(self.raw_text)
        return self.norm_text


@dataclass
class MatchResult:
    unit: Unit | None
    score: float
    match_type: str  # "exact" | "fuzzy" | "none"


# Calibrated in Task 2 against the audit eval; these are starting values.
FUZZY_THRESHOLD = 0.6   # min token-containment for a fuzzy hit
UNIQUENESS_MARGIN = 0.15  # best must beat 2nd-best by this much


def _tokens(norm: str) -> set[str]:
    return set(norm.split())


def _containment(query_tokens: set[str], unit_tokens: set[str]) -> float:
    """Fraction of the QUERY's tokens present in the unit. Robust to long units."""
    if not query_tokens:
        return 0.0
    return len(query_tokens & unit_tokens) / len(query_tokens)


def _nearest(units: list[Unit], typed_pos: float | None) -> Unit:
    """Pick the unit whose position is closest to the model's typed position."""
    if typed_pos is None:
        return units[0]

    def dist(u: Unit) -> float:
        pos = u.start_time if u.start_time is not None else (u.page or 0)
        return abs(pos - typed_pos)

    return min(units, key=dist)


def match_query(
    query: str,
    units: list[Unit],
    *,
    typed_pos: float | None = None,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    margin: float = UNIQUENESS_MARGIN,
) -> MatchResult:
    """Locate ``query`` in ``units``. typed_pos (a timestamp/page the model typed)
    is used ONLY as a tie-breaker among otherwise-equal hits, never as truth."""
    nq = _norm_for_match(query)
    if not nq:
        return MatchResult(None, 0.0, "none")

    # 1) exact normalized substring
    exact = [u for u in units if nq in u.normalized()]
    if exact:
        return MatchResult(_nearest(exact, typed_pos), 1.0, "exact")

    # 2) token-containment fuzzy
    qtok = _tokens(nq)
    scored = sorted(
        ((_containment(qtok, _tokens(u.normalized())), u) for u in units),
        key=lambda t: t[0],
        reverse=True,
    )
    if not scored or scored[0][0] < fuzzy_threshold:
        return MatchResult(None, scored[0][0] if scored else 0.0, "none")

    best_score = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if best_score - second < margin:
        # near-tie among different units -> not confident enough
        ties = [u for s, u in scored if best_score - s < margin]
        if typed_pos is not None:
            return MatchResult(_nearest(ties, typed_pos), best_score, "fuzzy")
        return MatchResult(None, best_score, "none")

    return MatchResult(scored[0][1], best_score, "fuzzy")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_citation_match.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_citation_match.py backend/tests/test_citation_match.py
git commit -m "feat(rag): deterministic lexical citation matcher (exact + fuzzy + uniqueness margin)"
```

### Task 2: Audit eval gate (GO / NO-GO)

Prove the matcher resolves the 15 audited chips against the REAL "Wiss. Seminar" sources.
This is a standalone script (needs the dev DB + storage), run manually.

**Files:**
- Create: `backend/scripts/citation_match_eval.py`
- Create: `backend/scripts/citation_audit_cases.json`

- [ ] **Step 1: Encode the 15 audited cases**

```json
// backend/scripts/citation_audit_cases.json
// filename matches aia_sources.filename; "keyword" = the chip keyword Hilde used (source language);
// "correct" = the position the claim actually lives at (from the manual audit);
// "cited" = what the chip showed (for reference). time = "MM:SS", page = integer.
[
  {"filename": "VL1_25-03-2026.webm", "keyword": "wissenschaftliche Seminar zweiten Semester Projekt dritten Semester", "cited": "03:47", "correct_time": "03:47"},
  {"filename": "VL2_01-04-2026.webm", "keyword": "kein Inhaltsverzeichnis Abbildungs Tabellenverzeichnis", "cited": "00:01", "correct_time": "02:59"},
  {"filename": "VL1_25-03-2026.webm", "keyword": "Präsentationstermine individuell Einzeltermine", "cited": "12:48", "correct_time": "09:28"},
  {"filename": "VL1_25-03-2026.webm", "keyword": "Peer Review Extended Abstract gegenseitig bewerten Feedback", "cited": "07:56", "correct_time": "08:12"},
  {"filename": "VL1_25-03-2026.webm", "keyword": "3. Juli finale Deadline Prüfungsleistung", "cited": "08:58", "correct_time": "08:58"},
  {"filename": "VL2_01-04-2026.webm", "keyword": "realistisch drei Monate erarbeiten Forschungsfrage", "cited": "00:01", "correct_time": "09:41"},
  {"filename": "VL2_01-04-2026.webm", "keyword": "Notizen Markierungen System Tools Software Quellen", "cited": "20:13", "correct_time": "20:34"},
  {"filename": "VL3_15-04-2026.webm", "keyword": "roter Faden Gliederung prüfen anpassen", "cited": "20:59", "correct_time": "02:21"},
  {"filename": "VL3_15-04-2026.webm", "keyword": "Unterschrift Abbildung Tabelle Nummerierung beschreiben", "cited": "24:17", "correct_time": "24:17"},
  {"filename": "VL3_15-04-2026.webm", "keyword": "Sekundärzitate vermeiden Primärzitate Originalquelle", "cited": "13:05", "correct_time": "16:26"},
  {"filename": "VL2_01-04-2026.webm", "keyword": "Unternehmen Forschung Entwicklung Universitäten Hochschulen", "cited": "36:04", "correct_time": "36:04"},
  {"filename": "VL2_01-04-2026.webm", "keyword": "Chairs Programmkomitee Verantwortliche Tagung", "cited": "43:07", "correct_time": "46:15"},
  {"filename": "VL1_25-03-2026.webm", "keyword": "freiwillig online dringend raten teilnehmen Review Prozess", "cited": "27:30", "correct_time": "27:30"},
  {"filename": "01_Einführung_WissenschaftlichesSeminar.pdf", "keyword": "Forum Kurs Fragen Mentorin Kontakt", "cited_page": 2, "correct_page": 2},
  {"filename": "01_Einführung_WissenschaftlichesSeminar.pdf", "keyword": "Literaturverwaltung Zotero Citavi Mendeley", "cited_page": 13, "correct_page": 15}
]
```

- [ ] **Step 2: Write the eval script**

```python
# backend/scripts/citation_match_eval.py
"""GO/NO-GO gate for citation grounding. Loads the real units of the audited
workspace's sources and checks the matcher resolves each chip to the CORRECT
segment/page. Run from backend/:  python scripts/citation_match_eval.py

Exit 0 if every previously-wrong case is now correct AND no previously-correct
case regresses; exit 1 otherwise."""
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

# A claim usually spans 2-3 transcript segments, so the "correct" time is a region, not
# an exact value. Accept a resolved timestamp within this many seconds of the audited spot.
# Pages are compared exactly. The previously-WRONG chips were grossly off (>170s / wrong page),
# so this window cleanly separates "fixed" from "still wrong".
TOLERANCE_S = 45.0


def _time_ok(resolved_s, correct_str):
    return resolved_s is not None and abs(resolved_s - _parse_ts(correct_str)) <= TOLERANCE_S


def _media_units(source: dict) -> list[Unit]:
    return [
        Unit(page=None, start_time=s["start"], end_time=s["end"], raw_text=s["text"])
        for s in _load_transcript_segments(source)
    ]


def _pdf_units(source_id: int) -> list[Unit]:
    return [
        Unit(page=c["page_number"], start_time=None, end_time=None, raw_text=c["content"])
        for c in chunk_repo.get_aia_chunks_by_source(source_id)
        if c.get("content")
    ]


def main() -> int:
    # Resolve each filename -> source row. Adjust the lookup to your repo's API;
    # source_repo must expose a way to fetch a source by filename in the dev workspace.
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
            want = case["correct_time"]
            cited = case["cited"]
            ok = _time_ok(resolved_s, case["correct_time"])          # resolved near the truth
            was_wrong = not _time_ok(_parse_ts(case["cited"]), case["correct_time"])  # chip was off
        else:
            units = _pdf_units(src["id"])
            r = match_query(case["keyword"], units, typed_pos=case["cited_page"])
            got = f"S.{r.unit.page}" if r.unit else "—"
            want = f"S.{case['correct_page']}"
            cited = f"S.{case['cited_page']}"
            ok = bool(r.unit) and r.unit.page == case["correct_page"]  # exact page
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
    # ~7 cases are 'was_wrong' under the tolerance window (the two 00:01, roter-Faden 20:59,
    # Sekundärzitate 13:05, Forschungsfrage, Verantwortliche 43:07, and PDF S.13). Gate = fix
    # at least 6 of them and regress none.
    return 0 if regressions == 0 and fixes >= 6 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Add the eval-only source lookup if missing**

If `source_repo` has no "list all sources" helper, add a thin one used only by the eval:

```python
# backend/src/features/ai_assistant/repository/sources.py  (append)
def list_all_sources_for_eval() -> list[dict]:
    """Eval/diagnostics only: every source row (id, filename, file_path)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, filename, file_path FROM aia_sources")
            return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 4: Run the gate**

Run: `cd backend && python scripts/citation_match_eval.py`
Expected: a table; `regressions=0` and `fixes>=6`. The two `[2] 00:01`, the `[3] 20:59`,
and the `[4] S.13` rows must flip to `OK`.

- [ ] **Step 5: GATE DECISION (write the result, do not skip)**

- **Pass** (`regressions=0`, `fixes>=6`): append a one-line "Gate passed YYYY-MM-DD,
  fixes=N" note to the spec's Validation section, commit, continue to Milestone 1.
- **Fail:** STOP. Tune `FUZZY_THRESHOLD` / `UNIQUENESS_MARGIN` and re-run. If it still
  fails (lexical overlap can't disambiguate), do NOT build the pipeline — report back and
  reconsider Approach C (segment-level re-chunking) from the spec.

```bash
git add backend/scripts/citation_match_eval.py backend/scripts/citation_audit_cases.json backend/src/features/ai_assistant/repository/sources.py docs/superpowers/specs/2026-06-01-citation-grounding-design.md
git commit -m "test(rag): citation grounding audit eval gate (15 real cases)"
```

---

## Milestone 1 — Phase 1: Coverage (a chip on every groundable bullet)

### Task 3: Unit loader (full set per source, cached per request)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py`
- Test: `backend/tests/test_citation_units.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_citation_units.py
from src.features.ai_assistant.routes._helpers import SourceUnitLoader


def test_loader_caches_per_source(monkeypatch):
    calls = {"n": 0}

    def fake_chunks(sid):
        calls["n"] += 1
        return [{"page_number": 5, "content": "hello world", "start_time": None}]

    monkeypatch.setattr(
        "src.features.ai_assistant.repository.chunks.get_aia_chunks_by_source", fake_chunks
    )
    loader = SourceUnitLoader()
    src = {"id": 1, "filename": "x.pdf", "file_path": "x.pdf"}
    u1 = loader.units(src, is_media=False)
    u2 = loader.units(src, is_media=False)
    assert calls["n"] == 1            # cached
    assert u1[0].page == 5 and u1[0].raw_text == "hello world"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_citation_units.py -v`
Expected: FAIL (`ImportError: cannot import name 'SourceUnitLoader'`).

- [ ] **Step 3: Implement the loader**

```python
# backend/src/features/ai_assistant/routes/_helpers.py  (append)
from ._citation_match import Unit


class SourceUnitLoader:
    """Loads a source's FULL set of position-bearing units once per request.

    PDF/doc/pptx -> page-chunks via get_aia_chunks_by_source (each chunk is one page).
    Media -> transcript segments via _load_transcript_segments.
    NOTE: deliberately NOT source_index (which holds only context-budgeted chunks)."""

    def __init__(self) -> None:
        self._cache: dict[int, list[Unit]] = {}

    def units(self, source: dict, *, is_media: bool) -> list[Unit]:
        sid = source["id"]
        if sid in self._cache:
            return self._cache[sid]
        if is_media:
            units = [
                Unit(page=None, start_time=s["start"], end_time=s["end"], raw_text=s["text"])
                for s in _load_transcript_segments(source)
            ]
        else:
            from src.features.ai_assistant.repository import chunks as chunk_repo
            units = [
                Unit(page=c["page_number"], start_time=None, end_time=None, raw_text=c["content"])
                for c in chunk_repo.get_aia_chunks_by_source(sid)
                if c.get("content")
            ]
        self._cache[sid] = units
        return units
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_citation_units.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/tests/test_citation_units.py
git commit -m "feat(rag): per-request source unit loader (full set, cached)"
```

### Task 4: Line classifier (which lines may receive a filled chip)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py`
- Test: `backend/tests/test_citation_lines.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_citation_lines.py
from src.features.ai_assistant.routes._helpers import is_citable_line


def test_classifier():
    assert is_citable_line("- Das Paper hat 6-7 Seiten.", in_summary=False)
    assert is_citable_line("| Themenfindung | bis April |", in_summary=False)  # table row
    assert not is_citable_line("## Prüfungsleistung", in_summary=False)        # heading
    assert not is_citable_line("Die Prüfungsleistung besteht aus:", in_summary=False)  # intro
    assert not is_citable_line("- Recap point.", in_summary=True)              # summary block
    assert not is_citable_line("", in_summary=False)                          # blank
    assert not is_citable_line("|---|---|", in_summary=False)                 # table separator
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_citation_lines.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement the classifier**

```python
# backend/src/features/ai_assistant/routes/_helpers.py  (append)
import re as _re

_HEADING = _re.compile(r"^\s{0,3}#{1,6}\s")
_TABLE_SEP = _re.compile(r"^\s*\|?\s*:?-{2,}")
_LIST_OR_TEXT = _re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\S)")


def is_citable_line(line: str, *, in_summary: bool) -> bool:
    """True if a filled citation may be appended to this line."""
    s = line.strip()
    if not s or in_summary:
        return False
    if _HEADING.match(line):
        return False
    if s.startswith("|") and _TABLE_SEP.match(s):
        return False
    if s.endswith(":"):           # intro/parent line, e.g. "... besteht aus:"
        return False
    if s.startswith("|"):          # table data row -> citable
        return True
    return bool(_LIST_OR_TEXT.match(line))
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_citation_lines.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/tests/test_citation_lines.py
git commit -m "feat(rag): citable-line classifier for coverage fill"
```

### Task 5: Coverage-fill pass + wiring

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py`
- Modify: `backend/src/features/ai_assistant/routes/chat.py:929-937` (pipeline)
- Test: `backend/tests/test_citation_coverage.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_citation_coverage.py
from src.features.ai_assistant.routes._helpers import fill_uncited_lines
from src.features.ai_assistant.routes._citation_match import Unit


class _FakeLoader:
    def __init__(self, units): self._u = units
    def units(self, source, *, is_media): return self._u


def test_fills_only_uncited_groundable_lines():
    text = (
        "## Überblick\n"
        "- Das Paper hat sechs bis sieben Seiten.\n"
        "- Schon zitiert. [2, S. 5 | foo]\n"
    )
    units = [Unit(page=5, start_time=None, end_time=None,
                  raw_text="das Paper hat sechs bis sieben Seiten plus Literaturverzeichnis")]
    sources = {2: {"source": {"id": 2, "filename": "x.pdf"}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[2, S. 5 |" in out.splitlines()[1]   # first bullet now cited
    assert out.splitlines()[0] == "## Überblick"  # heading untouched
    assert out.count("[2, S. 5 |") == 2           # second bullet kept its own, first added
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_citation_coverage.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement the coverage pass**

```python
# backend/src/features/ai_assistant/routes/_helpers.py  (append)
from ._citation_match import match_query

# A line "already has a citation" if it ends with a chip token.
_HAS_CITE = _re.compile(r"\[(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*$")
_SUMMARY = _re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*[ \t]*)?"
    r"(?:Zusammenfassung|Zusammengefasst|Fazit|Summary|Conclusion)[ \t]*(?:\*\*)?[ \t]*:?[ \t]*$"
)


def _kw_from_unit(unit, n_words: int = 4) -> str:
    """A short verbatim snippet from the matched unit for the highlight anchor."""
    return " ".join(unit.raw_text.split()[:n_words])


def fill_uncited_lines(text: str, sources: dict, loader) -> str:
    """Append a citation to each groundable line that lacks one.

    sources: {qnum: {"source": <row dict>, "is_media": bool}}
    loader:  SourceUnitLoader (or any object with .units(source, is_media=...))."""
    out_lines, in_summary = [], False
    for line in text.split("\n"):
        if _SUMMARY.match(line):
            in_summary = True
        if not is_citable_line(line, in_summary=in_summary) or _HAS_CITE.search(line.rstrip()):
            out_lines.append(line)
            continue
        best = None  # (score, qnum, unit, is_media)
        for qnum, meta in sources.items():
            units = loader.units(meta["source"], is_media=meta["is_media"])
            r = match_query(line, units)
            if r.unit and (best is None or r.score > best[0]):
                best = (r.score, qnum, r.unit, meta["is_media"])
        if best is None:
            out_lines.append(line)          # below threshold -> deliberately no chip
            continue
        _, qnum, unit, is_media = best
        kw = _kw_from_unit(unit)
        pos = _format_timestamp(unit.start_time) if is_media else f"S. {unit.page}"
        out_lines.append(f"{line.rstrip()} [{qnum}, {pos} | {kw}]")  # plain in M1; Task 7 switches to "[~{qnum}, ..."
    return "\n".join(out_lines)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_citation_coverage.py -v`
Expected: PASS. (The test's `[2, S. 5 |` substring is contained in the emitted `[~2, S. 5 |`.)

- [ ] **Step 5: Wire it into the pipeline**

In `backend/src/features/ai_assistant/routes/chat.py`, build a `coverage_sources` map next to
`source_index` (reuse `qnum_to_source_id`, `all_sources_list`, and each entry's `is_media`),
construct one `SourceUnitLoader()` per request, and insert the fill between resolve and
summary-strip:

```python
# chat.py — replace the resolve/strip block at ~929-937
from ._helpers import SourceUnitLoader, fill_uncited_lines  # add to imports near line 412

coverage_sources = {
    qn: {"source": all_sources_list[qnum_to_source_id[qn]],
         "is_media": source_index[qn]["is_media"]}
    for qn in source_index if qnum_to_source_id.get(qn) in all_sources_list
}
_unit_loader = SourceUnitLoader()

answer = _strip_summary_citations(
    fill_uncited_lines(
        _resolve_citation_pages(
            _chipify_inline_refs(
                _sanitize_citations("".join(answer_parts).strip()),
                source_qmap,
            ),
            source_index,
        ),
        coverage_sources,
        _unit_loader,
    )
)
```

- [ ] **Step 6: Run the full backend suite + commit**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS (no regressions).

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/src/features/ai_assistant/routes/chat.py backend/tests/test_citation_coverage.py
git commit -m "feat(rag): coverage pass fills uncited groundable bullets with a source"
```

---

## Milestone 2 — Phase 2: Accuracy (segment/page-precise re-grounding)

### Task 6: Precise re-grounding in the resolver

Replace the position logic inside `_resolve_citation_pages` so a matched MEDIA citation uses
the transcript **segment** time (not the chunk start), a PDF citation prefers a real matched
page over the model-typed page, and a valid model mid-chunk timestamp is kept.

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (`_resolve_citation_pages`)
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (pass the loader + source rows in)
- Test: `backend/tests/test_citation_resolve.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_citation_resolve.py
from src.features.ai_assistant.routes._helpers import resolve_citation_positions
from src.features.ai_assistant.routes._citation_match import Unit


class _Loader:
    def __init__(self, m): self._m = m
    def units(self, source, *, is_media): return self._m[source["id"]]


def test_media_uses_segment_not_chunk_start():
    text = "Kein Verzeichnis nötig. [2, 00:01 | kein Inhaltsverzeichnis]"
    units = {2: [
        Unit(None, 1.0, 16.0, "herzlich willkommen heute"),
        Unit(None, 179.0, 197.0, "was Sie weglassen kein Inhaltsverzeichnis Tabellenverzeichnis"),
    ]}
    src = {2: {"source": {"id": 2}, "is_media": True}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[2, 02:59 | kein Inhaltsverzeichnis]" in out  # 179s -> 02:59, not 00:01


def test_pdf_prefers_matched_page_over_typed():
    text = "Tools wie Zotero. [4, S. 13 | Literaturverwaltung Zotero Citavi]"
    units = {4: [
        Unit(13, None, None, "Literaturrecherche Überblick Schneeballprinzip"),
        Unit(15, None, None, "Umgang mit Literatur Literaturverwaltung Tools Zotero Citavi Mendeley"),
    ]}
    src = {4: {"source": {"id": 4}, "is_media": False}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[4, S. 15 |" in out  # not S. 13


def test_keeps_valid_model_time_when_no_keyword_hit():
    text = "Etwas Vages. [2, 05:00 | unauffindbares keyword xyz]"
    units = {2: [Unit(None, 1.0, 600.0, "ganz anderer text")]}  # chunk spans 0-600
    src = {2: {"source": {"id": 2}, "is_media": True}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[2, 05:00 |" in out  # 300s is inside [1,600], model time kept
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_citation_resolve.py -v`
Expected: FAIL (`ImportError: resolve_citation_positions`).

- [ ] **Step 3: Implement `resolve_citation_positions`**

Add a new function that supersedes the position logic of `_resolve_citation_pages` using the
loader + matcher. Reuse the existing citation regex `_CITE_RESOLVE_RE`, `_format_timestamp`,
`_parse_ts`.

```python
# backend/src/features/ai_assistant/routes/_helpers.py  (append)
def resolve_citation_positions(text: str, sources: dict, loader) -> str:
    """Re-anchor each [N, pos | kw] to the precise unit located by the matcher.

    sources: {qnum: {"source": row, "is_media": bool}} — same shape as coverage."""
    def _sub(m: "re.Match") -> str:
        qnum = int(m.group(1)) if m.group(1) else min(sources) if sources else None
        page_str, time_str, kw_raw = m.group(2), m.group(3), m.group(4)
        kw = (kw_raw or "").strip().strip("\"'").strip()
        meta = sources.get(qnum)
        if meta is None:
            return ""  # unknown source -> drop
        units = loader.units(meta["source"], is_media=meta["is_media"])
        kw_suffix = f" | {kw}" if kw else ""
        typed = _parse_ts(time_str) if time_str else (int(page_str) if page_str else None)
        r = match_query(kw, units, typed_pos=typed) if kw else None
        if r and r.unit:
            if meta["is_media"]:
                return f"[{qnum}, {_format_timestamp(r.unit.start_time)}{kw_suffix}]"
            return f"[{qnum}, S. {r.unit.page}{kw_suffix}]"
        # no keyword hit -> keep a valid model-typed position
        if meta["is_media"] and time_str is not None:
            t = _parse_ts(time_str)
            for u in units:                       # keep only if inside some chunk's span
                if u.start_time is not None and u.start_time <= t <= (u.end_time or u.start_time):
                    return f"[{qnum}, {time_str}{kw_suffix}]"
            return f"[{qnum}, {_format_timestamp(units[0].start_time)}{kw_suffix}]" if units else ""
        if (not meta["is_media"]) and page_str is not None and \
                any(u.page == int(page_str) for u in units):
            return f"[{qnum}, S. {page_str}{kw_suffix}]"
        return ""  # unverifiable -> drop

    return _CITE_RESOLVE_RE.sub(_sub, text)
```

- [ ] **Step 4: Run to verify they pass**

Run: `cd backend && python -m pytest tests/test_citation_resolve.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Swap the resolver in the pipeline**

In `chat.py`, replace `_resolve_citation_pages(..., source_index)` with
`resolve_citation_positions(..., coverage_sources, _unit_loader)` (the loader/sources already
built in Task 5). Keep `_resolve_citation_pages` for now (used by `notes.py`); a follow-up can
migrate it. Run the audit eval again:

Run: `cd backend && python scripts/citation_match_eval.py`
Expected: same or better than the Task 2 gate (`regressions=0`).

- [ ] **Step 6: Full suite + commit**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS.

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/src/features/ai_assistant/routes/chat.py backend/tests/test_citation_resolve.py
git commit -m "feat(rag): segment/page-precise citation re-grounding (fixes wrong page & 00:01)"
```

---

## Milestone 3 — Trust cue (fuzzy/filled chips look approximate)

### Task 7: In-token match-type marker (backend + frontend)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (emit `~` for fuzzy)
- Modify: `backend/src/features/ai_assistant/routes/chat.py:58-70` (history-strip tolerates `~`)
- Modify: `frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citations.tsx`
- Test: `backend/tests/test_citation_resolve.py` (extend); `frontend` parser test

- [ ] **Step 1: Backend — emit `~` on non-exact chips (both emitters) + recognise it**

Two emitters must mark non-exact chips, and the "already cited" detector must accept the marker
(or the coverage pass would double-chip a fuzzy-resolved line):

```python
# (a) resolve_citation_positions (Task 6): replace the two "r.unit" return lines
prefix = "" if r.match_type == "exact" else "~"
if meta["is_media"]:
    return f"[{prefix}{qnum}, {_format_timestamp(r.unit.start_time)}{kw_suffix}]"
return f"[{prefix}{qnum}, S. {r.unit.page}{kw_suffix}]"

# (b) fill_uncited_lines (Task 5): filled chips are always approximate -> add the marker
out_lines.append(f"{line.rstrip()} [~{qnum}, {pos} | {kw}]")

# (c) _HAS_CITE (Task 5): allow an optional leading ~ so a fuzzy-resolved line is seen as cited
_HAS_CITE = _re.compile(r"\[~?(?:Q?\d+,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)[^\]]*\]\s*$")
```

Add a backend test asserting a paraphrased keyword yields `[~N, ...]`, an exact one yields
`[N, ...]`, and that `fill_uncited_lines` does NOT append a second chip to a line already
ending in `[~N, ...]`.

- [ ] **Step 2: Backend — every citation regex tolerates `~`**

Add an optional leading `~?` to EVERY regex that matches a citation token, or a `~`-marked chip
leaks as raw text / survives where it should be stripped: `_CITATION_RE` and `_CITATION_FIX_*`
(chat.py:60-69), the citation regex inside `_strip_summary_citations` (`_helpers.py:333`), and
the frontend pattern. Example for the frontend regex (`_citations.tsx`, the `pattern`):

```js
// add optional ~ capture right after the opening bracket:
const pattern = /[[【]~?(?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*[|❘]\s*([^\]】]+))?\s*[\]】]/g;
const approximate = m[0].startsWith("[~") || m[0].startsWith("【~");
```

- [ ] **Step 3: Frontend — render the cue**

In `CitationChip`, when `approximate`, add a dotted underline + tooltip. Keep colour/size:

```tsx
// add prop `approximate?: boolean` to CitationChip; in the span:
className={`... ${approximate ? "underline decoration-dotted underline-offset-2" : ""}`}
title={approximate ? `${filename}, ${label} — ungefähre Stelle` : `${filename}, ${label}`}
```

- [ ] **Step 4: Tests**

- Backend: `cd backend && python -m pytest tests/test_citation_resolve.py -v` → PASS.
- Frontend: add a parser test asserting `[~1, 03:47 | x]` parses to a chip with
  `approximate=true` and `[1, 03:47 | x]` to `approximate=false`, and that a legacy
  `[1, 03:47]` (no `~`) still renders. Run: `cd frontend && npx vitest run _citations`.
- [ ] **Step 5: Commit**

```bash
git add backend/src/features/ai_assistant/routes/_helpers.py backend/src/features/ai_assistant/routes/chat.py "frontend/src/app/[locale]/workspace/[uuid]/_components/chat/_citations.tsx"
git commit -m "feat(rag): subtle 'approximate' cue for fuzzy/filled citation chips"
```

---

## Milestone 4 — Regression guard

### Task 8: Promote the audit eval to a CI-able regression test

**Files:**
- Create: `backend/tests/test_citation_audit_regression.py`

- [ ] **Step 1: Wrap the eval as a test (skipped without dev data)**

```python
# backend/tests/test_citation_audit_regression.py
import os
import pytest

requires_data = pytest.mark.skipif(
    os.getenv("AIA_AUDIT_DB") != "1",
    reason="needs the seeded Wiss.Seminar workspace; set AIA_AUDIT_DB=1 to run",
)


@requires_data
def test_audit_cases_resolve_correctly():
    from scripts.citation_match_eval import main
    assert main() == 0
```

- [ ] **Step 2: Run (locally, with data) + commit**

Run: `cd backend && AIA_AUDIT_DB=1 python -m pytest tests/test_citation_audit_regression.py -v`
Expected: PASS. Without the env var: SKIPPED.

```bash
git add backend/tests/test_citation_audit_regression.py
git commit -m "test(rag): audit-case regression guard for citation grounding"
```

---

## Self-review notes (for the implementer)

- **Threshold values** (`FUZZY_THRESHOLD`, `UNIQUENESS_MARGIN`) are starting points — Task 2 is
  where you calibrate them against real data before building further.
- **`_resolve_citation_pages` is left in place** for `notes.py`; only the chat pipeline switches
  to `resolve_citation_positions`. A later cleanup can unify them.
- **Manual end-to-end check** after Milestone 3: re-run "fasse zusammen" in the Wiss. Seminar
  workspace and confirm every bullet has a chip, the four previously-wrong chips now land on the
  right spot, and fuzzy/filled chips show the dotted underline.
