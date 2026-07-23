"""Live E2E RAG eval — many German-law PDFs in the 'Test 2' workspace.

STRESS TEST for the SPECIFIC relevance-concentration budget at scale: EVERY question is
asked with ALL of the workspace's sources active (the count is NOT hardcoded — it is
whatever the workspace holds, capped by the admin setting `aia_workspace_max_sources`,
currently 30 and raisable to 50+). A single-target question ("Was schützt Art. 1 GG?")
must still surface the ONE relevant law among all the other active laws (the multi-source
flood fix at scale); a two-law question must keep BOTH relevant sources represented.

Mirrors private/rag-eval-30-gesetze.md. All expected key terms are grounded against the
real chunks (ILIKE). Synonym GROUPS → PASS needs ≥1 hit per group (case-insensitive).

Like the 5-law eval this is an INTEGRATION baseline, not a unit test:
  - the whole module SKIPS unless a live backend is reachable AND the workspace has the
    sources ready;
  - requests are PACED (AIA_EVAL_PACE, default 4s) for the shared GWDG rate limit.

Run (stack up + 30 PDFs ingested):
    docker exec -w /app -e PYTHONPATH=/app kis-backend \
        python -m pytest tests/test_aia_eval_30gesetze_e2e.py -v

Env overrides: AIA_EVAL_BASE, AIA_EVAL_WS, AIA_EVAL_USER, AIA_EVAL_PW, AIA_EVAL_PACE.
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
WS = os.environ.get("AIA_EVAL_WS", "a11ea669-30a5-409e-b336-7864f2a331e1")  # "Test 2"
USER = os.environ.get("AIA_EVAL_USER", "a")
PW = os.environ.get("AIA_EVAL_PW", "a")
PACE_S = float(os.environ.get("AIA_EVAL_PACE", "4"))

# id, cat, question, mode, required(synonym-groups) — each asked with ALL active sources.
SCENARIOS = [
    # A — single-source fact (must beat 29 distractors)
    ("S1", "A-single", "Was schützt Artikel 1 des Grundgesetzes?", "all", [["würde des menschen", "menschenwürde"]]),
    ("S2", "A-single", "Nach welcher Wartezeit greift der allgemeine Kündigungsschutz?", "all", [["sechs monate", "6 monate"]]),
    ("S3", "A-single", "Wie lang darf die werktägliche Arbeitszeit höchstens sein?", "all", [["acht stunden", "8 stunden"]]),
    ("S4", "A-single", "Wie lange wird das Arbeitsentgelt im Krankheitsfall fortgezahlt?", "all", [["sechs wochen", "6 wochen"]]),
    ("S5", "A-single", "Wie hoch ist das Mindeststammkapital einer GmbH?", "all", [["25 000", "25.000", "fünfundzwanzigtausend"]]),
    # "Werke der Literatur" (UrhG §1 umbrella) OR the §2 enumeration term "Sprachwerke"
    # (Schriftwerke …) — both are the correct legal answer; don't demand the §1 wording.
    ("S6", "A-single", "Welche Werke schützt das Urheberrechtsgesetz?", "all", [["literatur", "sprachwerke", "schriftwerke"], ["kunst"]]),
    ("S7", "A-single", "Was ermöglicht die Restschuldbefreiung in der Insolvenzordnung?", "all", [["restschuldbefreiung", "gläubiger"]]),
    ("S8", "A-single", "Welche zwei Stimmen hat der Wähler bei der Bundestagswahl?", "all", [["erststimme"], ["zweitstimme"]]),
    ("S9", "A-single", "Wer ist unbeschränkt einkommensteuerpflichtig?", "all", [["wohnsitz", "gewöhnlichen aufenthalt", "gewöhnlicher aufenthalt"]]),
    ("S10", "A-single", "Was ist der Rechtsanwalt nach der Bundesrechtsanwaltsordnung?", "all", [["organ der rechtspflege"]]),
    ("S11", "A-single", "Was ist ein Verwaltungsakt nach dem Verwaltungsverfahrensgesetz?", "all", [["verfügung", "entscheidung", "maßnahme"], ["öffentlichen rechts", "behörde"]]),
    ("S12", "A-single", "Welche Pflichten haben Verpflichtete nach dem Geldwäschegesetz?", "all", [["sorgfaltspflicht"], ["identifiz"]]),
    ("S13", "A-single", "Was kann als Marke geschützt werden?", "all", [["marke"], ["zeichen", "wörter", "abbildung"]]),
    ("S14", "A-single", "Was verbietet das Gesetz gegen den unlauteren Wettbewerb?", "all", [["unlauter"]]),
    ("S15", "A-single", "Was sind Arzneimittel im Sinne des Arzneimittelgesetzes?", "all", [["arzneimittel"]]),
    ("S16", "A-single", "Was muss in die Handwerksrolle eingetragen werden?", "all", [["handwerksrolle", "handwerk"]]),
    ("S17", "A-single", "Was regelt die Abgabenordnung?", "all", [["besteuerung", "steuer"], ["finanzbehörde", "festsetzung"]]),
    ("S18", "A-single", "Was schützt das Bundesnaturschutzgesetz?", "all", [["naturschutz", "landschaftspflege", "natur"]]),

    # B — multi-source (two laws must both be represented)
    ("M1", "B-multi", "Welches Gesetz schützt die Menschenwürde und welches regelt die Kündigung von Arbeitsverhältnissen?", "all", [["würde des menschen", "menschenwürde", "grundgesetz"], ["kündigung"]]),
    ("M2", "B-multi", "Was schützt das Urheberrechtsgesetz und was das Markengesetz?", "all", [["urheber", "werk"], ["marke"]]),
    ("M3", "B-multi", "Welche Themen regeln das Arbeitszeitgesetz und das Entgeltfortzahlungsgesetz?", "all", [["arbeitszeit"], ["entgeltfortzahlung", "krankheit", "lohnfortzahlung"]]),
    ("M4", "B-multi", "Was regelt die Zivilprozessordnung und was die Insolvenzordnung?", "all", [["zivilprozess", "klage", "prozess"], ["insolvenz"]]),
    ("M5", "B-multi", "Welche Stelle ist für die Steuerfestsetzung zuständig (Abgabenordnung) und welche Stellung hat der Rechtsanwalt (BRAO)?", "all", [["finanzbehörde", "steuer"], ["rechtspflege", "rechtsanwalt"]]),

    # C — anti-hallucination
    ("H1", "C-honest", "Wie hoch ist die Hundesteuer nach dem Einkommensteuergesetz?", "honest", []),
    ("H2", "C-honest", "Welche Höchstgeschwindigkeit auf Autobahnen schreibt das Grundgesetz vor?", "honest", []),
]

HONEST_MARKERS = [
    "nicht", "kein", "keine", "enthält kein", "regelt nicht", "steht nicht",
    "existiert nicht", "nicht enthalten", "keine angabe", "lässt sich nicht",
    "keine information", "nicht hervor", "nicht genannt", "nicht vorgesehen",
]

_state = {}


def _resolve_all_sources(d):
    """Collect ALL source uuids in the workspace payload (defensive on shape)."""
    found = {}

    def walk(o):
        if isinstance(o, dict):
            fn = o.get("filename") or o.get("name")
            uid = o.get("uuid") or o.get("source_uuid") or o.get("id")
            if fn and isinstance(fn, str) and fn.lower().endswith(".pdf") \
                    and isinstance(uid, str) and len(uid) >= 16:
                found[uid] = fn
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    return found


@pytest.fixture(scope="module")
def session():
    if _state:
        return _state
    try:
        c = httpx.Client(base_url=BASE, timeout=240.0)
        r = c.post("/auth/login", json={"username": USER, "password": PW})
        if r.status_code != 200:
            pytest.skip(f"login failed ({r.status_code}) — no live stack?")
        w = c.get(f"/ai-assistant/workspaces/{WS}")
        if w.status_code != 200:
            pytest.skip(f"workspace {WS} not reachable ({w.status_code})")
        ids = _resolve_all_sources(w.json())
        # Count is NOT hardcoded: the eval activates whatever sources the workspace has
        # (the per-workspace cap is the admin setting `aia_workspace_max_sources`, currently
        # 30, may be raised to 50+). Only skip when there are too few for a multi-source test.
        if len(ids) < 2:
            pytest.skip(f"need >=2 sources for a multi-source eval, found {len(ids)}")
        _state["client"] = c
        _state["all_ids"] = list(ids.keys())
        _state["last"] = 0.0
        return _state
    except (httpx.ConnectError, httpx.ConnectTimeout):
        pytest.skip("backend not reachable on AIA_EVAL_BASE")


def _ask(sess, question, source_ids):
    dt = time.monotonic() - sess["last"]
    if dt < PACE_S:
        time.sleep(PACE_S - dt)
    answer, tokens = "", []
    t0 = time.monotonic()
    t_first = None  # when the FIRST token arrives = time-to-first-visible-text (stream START)
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
                if t_first is None:
                    t_first = time.monotonic()
                tokens.append(ev["token"])
            if ev.get("done") and ev.get("answer"):
                answer = ev["answer"]
            if "error" in ev:
                pytest.fail(f"stream error: {ev['error']}")
    secs = time.monotonic() - t0                       # stream END = full answer written
    first = (t_first - t0) if t_first is not None else secs  # stream START = first token
    sess["last"] = time.monotonic()
    return (answer or "".join(tokens)).strip(), secs, first


def _check(ans, mode, required):
    low = ans.lower()
    if mode == "honest":
        return (any(m in low for m in HONEST_MARKERS), "no honesty marker")
    miss = [grp for grp in required if not any(s.lower() in low for s in grp)]
    if miss:
        return False, "missing: " + "; ".join("/".join(g) for g in miss)
    return True, ""


@pytest.mark.parametrize("sc", SCENARIOS, ids=[f"{s[0]}-{s[1]}" for s in SCENARIOS])
def test_eval_30(session, sc, record_property):
    _id, cat, q, mode, required = sc
    ans, secs, first = _ask(session, q, session["all_ids"])   # ALL 30 active
    record_property("question", q)
    record_property("answer", ans[:800])
    ok, why = _check(ans, mode, required)
    # EVALROW| id | cat | n_sources | start(1st token) | end(full) | answer_len | PASS/FAIL
    print(f"EVALROW|{_id}|{cat}|{len(session['all_ids'])}|{first:.1f}|{secs:.1f}|{len(ans)}|{'PASS' if ok else 'FAIL'}")
    print(f"\n{_id} [{cat}] {'PASS' if ok else 'FAIL'} :: {q}\n   -> {ans[:400]}")
    assert ok, f"{why}\nQ: {q}\nA: {ans[:600]}"
