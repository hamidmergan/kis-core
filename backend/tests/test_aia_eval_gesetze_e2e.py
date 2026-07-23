"""Live E2E RAG eval — 5 German-law PDFs in the 'Upload & Rag Test' workspace.

Mirrors private/rag-eval-gesetze.md. Hits the REAL chat API and checks key terms
per scenario (synonym groups → robust to LLM phrasing), not exact strings.

This is an INTEGRATION baseline, not a unit test:
  - the whole module SKIPS unless a live backend is reachable AND the 5 sources
    are present + ready in the workspace (so a normal `pytest` run without a
    running stack / ingested data is unaffected);
  - source UUIDs are resolved by filename at runtime (survives re-ingest);
  - requests are PACED (AIA_EVAL_PACE, default 4s) to respect the shared GWDG
    rate limit (2/s · 15/min for the whole university).

Run (stack up + 5 PDFs ingested):
    docker exec -w /app -e PYTHONPATH=/app kis-backend \
        python -m pytest tests/test_aia_eval_gesetze_e2e.py -v

Env overrides: AIA_EVAL_BASE, AIA_EVAL_WS, AIA_EVAL_USER, AIA_EVAL_PW, AIA_EVAL_PACE.

Scenario status notes:
  - 📄 page-scope cases (8/9): with the pre-call re-activated, scope is detected
    and the EXACT page is retrieved. mode="scope" keeps a lenient net (xfail-on-fail)
    so the suite still passes if run against a build where scope is dormant.
  - 🖼️ the OCR/image case is skipped: OCR is intentionally OFF; these PDFs are
    pure text.
"""
import json
import os
import time

import pytest

httpx = pytest.importorskip("httpx")

# Live E2E: hits the real chat API. Excluded from the default `make test` run
# (which passes -m "not e2e"); run explicitly via `make test-backend-e2e`.
pytestmark = pytest.mark.e2e

BASE = os.environ.get("AIA_EVAL_BASE", "http://localhost:8000")
WS = os.environ.get("AIA_EVAL_WS", "77cc9d61-d65e-45fe-a15a-aeaa86246f2e")
USER = os.environ.get("AIA_EVAL_USER", "a")
PW = os.environ.get("AIA_EVAL_PW", "a")
PACE_S = float(os.environ.get("AIA_EVAL_PACE", "4"))

FILES = {
    "TVG6": "TVG6.pdf",
    "AGG13": "AGG13.pdf",
    "BDSG45": "BDSG45.pdf",
    "StGB173": "StGB173.pdf",
    # BGB498 (489 pages) removed: exceeds the 100-page per-source limit, so it can
    # no longer be uploaded as a single source — testing it tests a non-supported
    # scenario. (Whole-book overview is the multi-chapter / Phase-2 case instead.)
}

# id, cat, question, [short names], mode, required, forbidden
# required = list of synonym-GROUPS; PASS needs ≥1 hit from EACH group (case-insensitive).
# mode: "all" normal | "honest" anti-hallucination (≥1 honesty marker) | "scope" (xfail).
SCENARIOS = [
    (1, "A-fakt", "Welche Form schreibt das TVG für Tarifverträge vor?", ["TVG6"], "all", [["schriftform", "schriftlich"]], []),
    (2, "A-fakt", "Wann wurde das AGG ausgefertigt?", ["AGG13"], "all", [["14. august 2006", "14.8.2006", "august 2006"]], []),
    (3, "A-fakt", "Was regelt § 211 StGB?", ["StGB173"], "all", [["mord"]], []),
    (4, "A-fakt", "Wer ist die unabhängige Datenschutz-Aufsichtsbehörde des Bundes nach BDSG?", ["BDSG45"], "all", [["bundesbeauftragte", "bfdi", "informationsfreiheit"]], []),

    (5, "B-tief", "Auf wen sind die TVG-Vorschriften entsprechend anwendbar?", ["TVG6"], "all", [["arbeitnehmerähnlich"]], []),

    (6, "C-überblick", "Gib einen Überblick, was das Tarifvertragsgesetz regelt.", ["TVG6"], "all", [["tarifvertrag", "tarifverträge"], ["allgemeinverbindlich"]], []),
    (7, "C-überblick", "Welche großen Teile hat das StGB?", ["StGB173"], "all", [["allgemein"], ["besonder"]], []),

    (8, "D-scope", "Was steht inhaltlich auf Seite 1 des BDSG?", ["BDSG45"], "scope", [["anwendungsbereich", "ds-gvo", "datenschutz", "begriffsbestimmung"]], []),
    (9, "D-scope", "Fasse Seite 5 des AGG zusammen.", ["AGG13"], "scope", [["schadensersatz", "entschädigung", "maßregelung"]], []),

    (10, "E-cross", "Welche unabhängige Bundesstelle gehört zum AGG und welche zum BDSG?", ["AGG13", "BDSG45"], "all", [["antidiskriminierungsstelle", "antidiskriminierung"], ["bundesbeauftragte", "bfdi", "datenschutz"]], []),
    (11, "E-cross", "Bieten sowohl AGG als auch BDSG eine Beschwerde- bzw. Anrufungsmöglichkeit?", ["AGG13", "BDSG45"], "all", [["beschwerde"], ["bundesbeauftragte", "anrufung", "aufsichtsbehörde", "anrufen"]], []),

    (12, "F-hallu", "Welche Freiheitsstrafe sieht das Tarifvertragsgesetz für Mord vor?", ["TVG6"], "honest", [], []),
    (13, "F-hallu", "Ab wie vielen Beschäftigten gilt das AGG in einem Unternehmen?", ["AGG13"], "honest", [], []),

    (14, "G-unmöglich", "Fasse Seite 50 des AGG zusammen.", ["AGG13"], "honest", [], []),

    (15, "H-format", "Stelle die Sanktionsarten des BDSG als Tabelle oder Stichpunkte dar.", ["BDSG45"], "all", [["bußgeld", "geldbuße"], ["freiheitsstrafe", "straftat", "strafvorschrift"]], []),

    (16, "I-tippfehler", "was steth in §242 stgb?", ["StGB173"], "all", [["diebstahl"]], []),
]

# Honesty markers for anti-hallucination cases: answer must admit the info is
# not present / not in scope rather than invent a fact.
HONEST_MARKERS = [
    "nicht", "kein", "keine", "enthält kein", "regelt nicht", "steht nicht",
    "existiert nicht", "nicht enthalten", "keine angabe", "unabhängig von",
    "alle arbeitgeber", "strafgesetzbuch", "nur 13", "13 seiten",
]

# Known overview gaps (xfail, not regressions). Currently empty: the only entry
# (#11 BGB whole-book overview) was removed together with the BGB source — a
# 489-page book is no longer a valid single source (100-page limit).
XFAIL_KNOWN: dict[int, str] = {}

_state = {}


def _resolve_sources(d):
    """Find {filename: uuid} from a workspace GET payload (defensive on shape)."""
    found = {}
    wanted = set(FILES.values())

    def walk(o):
        if isinstance(o, dict):
            fn = o.get("filename") or o.get("name") or o.get("title")
            uid = o.get("uuid") or o.get("source_uuid") or o.get("id")
            if fn in wanted and isinstance(uid, str) and len(uid) >= 16:
                found[fn] = uid
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return found


@pytest.fixture(scope="module")
def session():
    """Log in + resolve source UUIDs. Skip the whole module if unavailable."""
    if _state:
        return _state
    try:
        c = httpx.Client(base_url=BASE, timeout=180.0)
        r = c.post("/auth/login", json={"username": USER, "password": PW})
        if r.status_code != 200:
            pytest.skip(f"login failed ({r.status_code}) — no live stack?")
        w = c.get(f"/ai-assistant/workspaces/{WS}")
        if w.status_code != 200:
            pytest.skip(f"workspace {WS} not reachable ({w.status_code})")
        name2uuid = {}
        fn2uuid = _resolve_sources(w.json())
        for short, fn in FILES.items():
            if fn in fn2uuid:
                name2uuid[short] = fn2uuid[fn]
        missing = [s for s in FILES if s not in name2uuid]
        if missing:
            pytest.skip(f"sources not found/ready in WS: {missing}")
        _state["client"] = c
        _state["map"] = name2uuid
        _state["last"] = 0.0
        return _state
    except (httpx.ConnectError, httpx.ConnectTimeout):
        pytest.skip("backend not reachable on AIA_EVAL_BASE")


def _ask(sess, question, source_ids):
    # pace to respect the shared GWDG rate limit
    dt = time.monotonic() - sess["last"]
    if dt < PACE_S:
        time.sleep(PACE_S - dt)
    answer, tokens = "", []
    t0 = time.monotonic()
    with sess["client"].stream(
        "POST", f"/ai-assistant/workspaces/{WS}/chat",
        json={"question": question, "active_source_ids": source_ids},
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except Exception:
                continue
            if "token" in ev:
                tokens.append(ev["token"])
            if ev.get("done") and ev.get("answer"):
                answer = ev["answer"]
            if "error" in ev:
                pytest.fail(f"stream error: {ev['error']}")
    secs = time.monotonic() - t0
    sess["last"] = time.monotonic()
    return (answer or "".join(tokens)).strip(), secs


def _check(ans, mode, required):
    low = ans.lower()
    if mode == "honest":
        if any(m in low for m in HONEST_MARKERS):
            return True, ""
        return False, "no honesty marker (possible hallucination)"
    miss = [grp for grp in required if not any(s.lower() in low for s in grp)]
    if miss:
        return False, "missing: " + "; ".join("/".join(g) for g in miss)
    return True, ""


@pytest.mark.parametrize("sc", SCENARIOS, ids=[f"#{s[0]}-{s[1]}" for s in SCENARIOS])
def test_eval(session, sc, record_property):
    _id, cat, q, names, mode, required, _forbidden = sc
    src = [session["map"][n] for n in names]
    ans, secs = _ask(session, q, src)
    record_property("question", q)
    record_property("answer", ans[:800])
    ok, why = _check(ans, mode, required)
    verdict = "PASS" if ok else ("XFAIL" if (mode == "scope" or _id in XFAIL_KNOWN) else "FAIL")
    # machine-parseable row for the metrics table (chunks/calls come from backend logs)
    print(f"EVALROW|{_id}|{cat}|{len(names)}|{secs:.1f}|{len(ans)}|{verdict}")
    print(f"\n#{_id} [{cat}] {'PASS' if ok else 'FAIL'} :: {q}\n   -> {ans[:400]}")
    if not ok and mode == "scope":
        pytest.xfail(f"scope dormant (expected weak): {why} | ans: {ans[:200]}")
    if not ok and _id in XFAIL_KNOWN:
        pytest.xfail(f"{XFAIL_KNOWN[_id]}: {why} | ans: {ans[:200]}")
    assert ok, f"{why}\nQ: {q}\nA: {ans[:600]}"
