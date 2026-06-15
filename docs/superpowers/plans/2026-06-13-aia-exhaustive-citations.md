# AIA Exhaustive Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bei aktiviertem Modus oder erkannter "alle Quellen"-Aufforderung jede Fundstelle eines Fakts als nav-only Chip zeigen, ueber die ganze aktive Dokumentauswahl, gedeckelt auf 10 pro Zeile.

**Architecture:** Die Chip-Attribution ist post-hoc (nach der Antwort, per Embedding-Suche) und kostet kein LLM-Kontext-Budget. Wir fuehren einen `exhaustive`-Schalter durch die Attribution-Pipeline, der (a) die 3er-Kappe auf 10 hebt, (b) das relative 0.08-Delta-Gate abschaltet, (c) den seen-Klammer ueberspringt, sodass die Suche die ganze Auswahl trifft. Ausgeloest wird er durch eine LLM-Erkennung in `_understand_query` ODER eine Per-User-Einstellung. Das Frontend faltet Chips bereits (CitationChipGroup), daher keine Chip-Render-Aenderung.

**Tech Stack:** Python/FastAPI Backend, pytest, pgvector hybrid_search, PostgreSQL, Next.js/React Frontend.

---

## File Structure

- `backend/src/features/ai_assistant/routes/_helpers.py` — Attribution-Logik (`_chips_for_line`, `_line_candidates`, `_attribute_generic_text`), neue Konstante.
- `backend/src/features/ai_assistant/routes/chat.py` — `_understand_query`/`_parse_understanding` (4-Tupel), Caller `_attribute_blocking`.
- `backend/src/tool_prompts.py` — `AIA_QUERY_UNDERSTANDING_SYSTEM` Prompt erweitern.
- `backend/src/core/db/schema.py` — Spalte `show_all_sources`.
- `backend/src/features/ai_assistant/repository/chat.py` — `upsert_aia_user_settings`.
- `backend/src/features/ai_assistant/schemas.py` — `UserSettingsBody`.
- `backend/src/features/ai_assistant/routes/messages.py` — Settings-Route.
- `backend/tests/test_attribution.py`, `backend/tests/test_chat_paths.py` — Tests.
- Frontend Chat-Settings-Komponente + Typen (Phase 3, in der Ausfuehrung lokalisiert).

---

## PHASE 1 — Exhaustive Attribution (Backend-Logik, rein unit-testbar)

### Task 1: `_chips_for_line` exhaustive (Kappe 10 + Delta-Gate aus)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (Konstante ~290, `_chips_for_line` ~566-605)
- Test: `backend/tests/test_attribution.py`

- [ ] **Step 1: Failing tests schreiben**

In `backend/tests/test_attribution.py` ans Ende anfuegen:

```python
# ── exhaustive mode: lift cap to 10, drop the relative delta gate ─────────────

def test_exhaustive_chips_all_distinct_sources_within_gate():
    # Five distinct sources, all within the 0.6 gate but spread wider than 0.08.
    # Normal mode keeps only the best (relative delta); exhaustive chips all five.
    line = "Die Abgabe der Hausarbeit ist am 03.07.2026 faellig und steht hier."
    hits = [_hit(1, 6, "Abgabe 03.07.2026", 0.20), _hit(2, 4, "Frist 03.07.2026", 0.34),
            _hit(3, 2, "Termin 03.07.2026", 0.41), _hit(4, 9, "Deadline 03.07.2026", 0.48),
            _hit(5, 1, "Abgabetermin 03.07.2026", 0.55)]
    search = _searcher({"Hausarbeit": hits})
    qmap = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
    out = _attribute_generic_text(line, search, qmap, max_distance=0.6, exhaustive=True)
    for q, p in [(1, 6), (2, 4), (3, 2), (4, 9), (5, 1)]:
        assert f"[{q}, S. {p}]" in out
    # normal mode: relative gate keeps only the closest
    out_norm = _attribute_generic_text(line, search, qmap, max_distance=0.6)
    assert "[1, S. 6]" in out_norm and "[5, S. 1]" not in out_norm


def test_exhaustive_caps_at_ten():
    line = "Eine inhaltlich substanzielle Aussage zum Thema die ueberall steht."
    hits = [_hit(i, i, f"Aussage zum Thema {i}", 0.2 + i * 0.01) for i in range(1, 16)]
    search = _searcher({"substanzielle": hits})
    qmap = {i: i for i in range(1, 16)}
    out = _attribute_generic_text(line, search, qmap, max_distance=0.9, exhaustive=True)
    import re as _re
    assert len(_re.findall(r"\[\d+, S\. \d+\]", out)) == 10


def test_exhaustive_still_respects_max_distance():
    # A source past the absolute gate is never chipped, even in exhaustive mode.
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier formuliert."
    search = _searcher({"substanzielle": [_hit(1, 5, "x", 0.2), _hit(2, 7, "y", 0.95)]})
    out = _attribute_generic_text(line, search, {1: 1, 2: 2}, max_distance=0.6, exhaustive=True)
    assert "[1, S. 5]" in out and "[2, S. 7]" not in out
```

- [ ] **Step 2: Tests laufen, Fehlschlag bestaetigen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "exhaustive" -v`
Expected: FAIL — `_attribute_generic_text() got an unexpected keyword argument 'exhaustive'`

- [ ] **Step 3: Konstante ergaenzen**

In `_helpers.py` direkt nach `_MAX_CHIPS_PER_LINE = 3` (Zeile 290):

```python
# Exhaustive mode ("alle Quellen"): per-line chip cap raised from 3 to 10 and the
# relative MULTI_CHIP delta gate is dropped, so EVERY distinct source/page within the
# absolute distance gate is chipped (not just co-sources hugging the best). 10 is plenty
# for "wo ueberall steht das" without exploding a line.
_EXHAUSTIVE_MAX_CHIPS_PER_LINE = 10
```

- [ ] **Step 4: `_chips_for_line` Signatur + Logik**

Signatur (Zeile 566) erweitern um `exhaustive`:

```python
def _chips_for_line(cands: list[dict], source_id_to_qnum: dict,
                    max_distance: float,
                    guarantee_dist: float = _GUARANTEE_MAX_DIST,
                    exhaustive: bool = False) -> list[str]:
```

Im Schleifenkoerper das relative Gate und die Kappe modusabhaengig machen. Ersetze den Block:

```python
        if primary_d is None:
            if d > guarantee_dist:  # closest seen chunk too far → no chip at all
                break
            primary_d = d                # the guarantee chip; anchors the relative gate
        elif d > min(max_distance, primary_d + _MULTI_CHIP_MAX_DELTA):
            break                        # additional sources must be CLOSE to the best
```

durch:

```python
        if primary_d is None:
            if d > guarantee_dist:  # closest seen chunk too far → no chip at all
                break
            primary_d = d                # the guarantee chip; anchors the relative gate
        elif exhaustive:
            if d > max_distance:         # exhaustive: every distinct source within the
                break                    # absolute gate, NO relative delta restriction
        elif d > min(max_distance, primary_d + _MULTI_CHIP_MAX_DELTA):
            break                        # additional sources must be CLOSE to the best
```

Und die Kappe (Zeile 603) ersetzen:

```python
        if len(chips) >= _MAX_CHIPS_PER_LINE:
            break
```

durch:

```python
        cap = _EXHAUSTIVE_MAX_CHIPS_PER_LINE if exhaustive else _MAX_CHIPS_PER_LINE
        if len(chips) >= cap:
            break
```

- [ ] **Step 5: `exhaustive` in `_attribute_generic_text` durchreichen (nur an `_chips_for_line`)**

In `_attribute_generic_text` (Zeile 699) die Signatur um `exhaustive: bool = False` erweitern (vor `scope_chunks`):

```python
def _attribute_generic_text(text: str, search_one, source_id_to_qnum: dict, offset_fn=None, *,
                            seen_pages_by_source=None, context_chunks=None, overview: bool = False,
                            max_distance: float = _GENERIC_ATTRIB_MAX_DIST,
                            refusal_lines: Optional[set] = None,
                            exhaustive: bool = False,
                            scope_chunks: Optional[list[dict]] = None) -> str:
```

Und beim Aufruf von `_chips_for_line` (Zeile 793) `exhaustive=exhaustive` ergaenzen:

```python
            chips = _chips_for_line(agg, source_id_to_qnum, max_distance,
                                    guarantee_dist=guarantee, exhaustive=exhaustive)
```

- [ ] **Step 6: Tests laufen, jetzt gruen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "exhaustive" -v`
Expected: PASS (3 Tests)

- [ ] **Step 7: Volle Attribution-Suite (keine Regression)**

Run: `cd backend && python -m pytest tests/test_attribution.py -v`
Expected: PASS (alle, inkl. bisherige multi_chip/overview Tests unveraendert)

---

### Task 2: `_line_candidates` exhaustive (Exakt-Kurzschluss ueberspringen)

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (`_line_candidates` ~538-563, `_attribute_generic_text` ~761)
- Test: `backend/tests/test_attribution.py`

- [ ] **Step 1: Failing test**

```python
def test_exhaustive_does_not_short_circuit_on_exact_match():
    # A line whose tokens appear verbatim in ONE context chunk would normally collapse to
    # that single exact source. Exhaustive must instead surface ALL semantic/hybrid hits
    # so every occurrence across the selection is chipped.
    line = "Die Abgabe der Hausarbeit ist am 03.07.2026 faellig."
    ctx = [{"source_id": 1, "page_number": 6,
            "content": "Die Abgabe der Hausarbeit ist am 03.07.2026 faellig.", "vec_distance": None}]
    search = _searcher({"Hausarbeit": [_hit(1, 6, "Abgabe 03.07.2026", 0.20),
                                       _hit(2, 4, "Frist 03.07.2026", 0.30)]})
    out = _attribute_generic_text(line, search, {1: 1, 2: 2}, max_distance=0.6,
                                  context_chunks=ctx, exhaustive=True)
    assert "[1, S. 6]" in out and "[2, S. 4]" in out
    # normal mode: exact match collapses to the single source 1 only
    out_norm = _attribute_generic_text(line, search, {1: 1, 2: 2}, max_distance=0.6,
                                       context_chunks=ctx)
    assert "[2, S. 4]" not in out_norm
```

- [ ] **Step 2: Fehlschlag bestaetigen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "short_circuit" -v`
Expected: FAIL (`[2, S. 4]` fehlt im exhaustive-Output, weil der Exakt-Kurzschluss nur Quelle 1 liefert)

- [ ] **Step 3: `_line_candidates` Signatur + Kurzschluss-Bypass**

Signatur (Zeile 538) erweitern:

```python
def _line_candidates(line: str, search_one, context_chunks: Optional[list[dict]],
                     seen_pages_by_source: Optional[dict],
                     scope_ids: Optional[set] = None,
                     exhaustive: bool = False) -> list[dict]:
```

Den Exakt-Kurzschluss-Block (Zeilen 551-556) nur ausserhalb von exhaustive ausfuehren. Ersetze:

```python
    exact = _exact_attribution_chunk(line, context_chunks) if context_chunks else None
    if (exact is not None and _is_seen(exact, seen_pages_by_source)
            and _in_scope(exact, scope_ids)):
        e = dict(exact)
        e["vec_distance"] = 0.0  # verbatim presence == certain
        return [e]
```

durch:

```python
    # Exhaustive ("alle Quellen") wants EVERY occurrence, so the single exact-match
    # short-circuit (which suppresses other sources) is skipped — fall through to the
    # full hybrid candidate list below.
    if not exhaustive:
        exact = _exact_attribution_chunk(line, context_chunks) if context_chunks else None
        if (exact is not None and _is_seen(exact, seen_pages_by_source)
                and _in_scope(exact, scope_ids)):
            e = dict(exact)
            e["vec_distance"] = 0.0  # verbatim presence == certain
            return [e]
```

- [ ] **Step 4: `exhaustive` an `_line_candidates` weiterreichen**

In `_attribute_generic_text` den Aufruf (Zeile 761) erweitern:

```python
        cands = _line_candidates(line, search_one, context_chunks, seen_pages_by_source,
                                 scope_ids, exhaustive=exhaustive)
```

- [ ] **Step 5: Test gruen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "short_circuit" -v`
Expected: PASS

- [ ] **Step 6: Suite gruen**

Run: `cd backend && python -m pytest tests/test_attribution.py -v`
Expected: PASS

---

### Task 3: exhaustive umgeht Overview-Unterdrueckungen

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/_helpers.py` (`_attribute_generic_text` ~780, ~791)
- Test: `backend/tests/test_attribution.py`

- [ ] **Step 1: Failing test**

```python
def test_exhaustive_overrides_overview_suppression():
    # An enumeration line that overview mode would leave chip-free must still be chipped
    # when the user explicitly asked for all sources (exhaustive), even with overview=True.
    line = "- Regelungen zur Form (ZPO), zu Marken (MarkenG) und zur Anwaltschaft (BRAO)."
    search = _searcher({"Regelungen": [_hit(1, 98, "Regelungen Form Urteilen", 0.2)]})
    out_ov = _attribute_generic_text(line, search, {1: 1}, max_distance=0.6, overview=True)
    assert out_ov == line  # overview suppresses
    out_ex = _attribute_generic_text(line, search, {1: 1}, max_distance=0.6,
                                     overview=True, exhaustive=True)
    assert "[1, S. 98]" in out_ex  # exhaustive shows it anyway
```

- [ ] **Step 2: Fehlschlag bestaetigen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "overrides_overview" -v`
Expected: FAIL (out_ex == line, weil `_names_many_laws` weiter unterdrueckt)

- [ ] **Step 3: Guards mit `not exhaustive` versehen**

In `_attribute_generic_text` die zwei Overview-Guards aendern. Zeile 780:

```python
            if overview and _names_many_laws(block_text):
                continue
```

zu:

```python
            if overview and not exhaustive and _names_many_laws(block_text):
                continue
```

Und Zeile 791:

```python
            if overview and _enum_chip_unbacked(block_text, agg[0].get("content") or ""):
                continue
```

zu:

```python
            if overview and not exhaustive and _enum_chip_unbacked(block_text, agg[0].get("content") or ""):
                continue
```

- [ ] **Step 4: Test gruen**

Run: `cd backend && python -m pytest tests/test_attribution.py -k "overrides_overview" -v`
Expected: PASS

- [ ] **Step 5: Suite gruen**

Run: `cd backend && python -m pytest tests/test_attribution.py -v`
Expected: PASS (alle)

---

## PHASE 2 — Erkennung der "alle Quellen"-Aufforderung

### Task 4: `exhaustive` in Prompt + Parser (4-Tupel)

**Files:**
- Modify: `backend/src/tool_prompts.py` (`AIA_QUERY_UNDERSTANDING_SYSTEM` ~427)
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (`_parse_understanding` ~469-495, `_understand_query` ~498-528)
- Test: `backend/tests/test_chat_paths.py`

- [ ] **Step 1: Failing tests + Anpassung bestehender Unpacks**

In `backend/tests/test_chat_paths.py` neue Tests anfuegen:

```python
def test_parse_understanding_exhaustive_true():
    _i, _s, _subs, exhaustive = _parse_understanding(
        '{"intent": "SPECIFIC", "scope": {"unit": null, "intervals": []}, '
        '"subqueries": [], "exhaustive": true}')
    assert exhaustive is True


def test_parse_understanding_exhaustive_defaults_false():
    _i, _s, _subs, exhaustive = _parse_understanding(
        '{"intent": "SPECIFIC", "scope": {"unit": null, "intervals": []}}')
    assert exhaustive is False
```

Bestehende Unpacks in dieser Datei auf 4 Werte erweitern (jede Zeile, die `_parse_understanding`/`_understand_query` auspackt): aus `intent, scope, _subs = ...` wird `intent, scope, _subs, _exh = ...`; aus `_i, _s, subs = ...` wird `_i, _s, subs, _exh = ...`; analog fuer die `_understand_query`-Aufrufe.

- [ ] **Step 2: Fehlschlag bestaetigen**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -k "understanding or understand_query" -v`
Expected: FAIL — `not enough values to unpack (expected 4, got 3)`

- [ ] **Step 3: Prompt erweitern**

In `backend/src/tool_prompts.py` im String `AIA_QUERY_UNDERSTANDING_SYSTEM` das JSON-Schema und die Regeln um ein `exhaustive`-Feld ergaenzen. Ans Ende der Feldbeschreibung (vor dem Schluss des Strings) anfuegen, sprach-agnostisch:

```
- "exhaustive": true ONLY when the user explicitly wants to see ALL sources / every place
  a fact appears (e.g. "zeige alle Quellen", "wo ueberall steht das", "alle Stellen",
  "list every source", "show all references", in ANY language). Otherwise false. This is
  about wanting an exhaustive list of LOCATIONS, not the depth of the answer.
```

Im Beispiel-JSON des Prompts das Feld `"exhaustive": false` ergaenzen, damit das Modell die Form kennt. (Konkrete Einfuegestelle: dort wo `subqueries` im Schema/Beispiel steht — direkt daneben.)

- [ ] **Step 4: `_parse_understanding` 4-Tupel**

In `chat.py` `_parse_understanding` (Zeile 469) Rueckgabetyp und alle Return-Pfade auf 4 Elemente bringen. Die Funktion komplett ersetzen:

```python
def _parse_understanding(content: str) -> tuple[str, dict, list[str], bool]:
    """Parse the combined query-understanding reply into
    ``(intent, scope, subqueries, exhaustive)``.

    Tolerant: strips <think>/code-fences, takes the first JSON object. ``intent``
    defaults to SPECIFIC; ``scope`` is validated by ``_parse_scope_response``;
    ``subqueries`` is the question split into its distinct asks; ``exhaustive`` is the
    "show me ALL sources" flag (defaults False). Any garbage →
    ``("SPECIFIC", {"unit": None, "intervals": []}, [], False)``."""
    import json
    raw = re.sub(r"<think>.*?</think>", "", content or "", flags=re.DOTALL)
    raw = raw.replace("```json", "").replace("```", "")
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return "SPECIFIC", {"unit": None, "intervals": []}, [], False
    try:
        obj = json.loads(m.group(0))
    except Exception:
        cleaned = re.sub(r"[^A-Za-z]+", " ", raw).upper().split()
        return ("GENERIC" if "GENERIC" in cleaned else "SPECIFIC"), {"unit": None, "intervals": []}, [], False
    intent = "GENERIC" if "GENERIC" in str(obj.get("intent", "")).upper() else "SPECIFIC"
    scope_obj = obj.get("scope")
    scope = _parse_scope_response(json.dumps(scope_obj)) if scope_obj else {"unit": None, "intervals": []}
    subs_raw = obj.get("subqueries")
    subqueries = ([s.strip() for s in subs_raw if isinstance(s, str) and s.strip()][:3]
                  if isinstance(subs_raw, list) else [])
    exhaustive = bool(obj.get("exhaustive", False))
    return intent, scope, subqueries, exhaustive
```

- [ ] **Step 5: `_understand_query` 4-Tupel**

In `chat.py` `_understand_query` (Zeile 498) Rueckgabetyp auf `tuple[str, dict, list[str], bool]`, beide Return-Pfade anpassen:
- Fehlerpfad: `return "SPECIFIC", {"unit": None, "intervals": []}, [], False`
- Erfolgspfad: `intent, scope, subqueries, exhaustive = _parse_understanding(raw)` und `return intent, scope, subqueries, exhaustive`
- Log-Zeile um `exhaustive={}` erweitern.

- [ ] **Step 6: Tests gruen**

Run: `cd backend && python -m pytest tests/test_chat_paths.py -v`
Expected: PASS (alle, inkl. neue exhaustive-Tests)

---

### Task 5: Caller in chat.py verdrahten

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (Routing ~1093-1101, `_attribute_blocking` ~1711-1766)
- Test: manuell (Integration; Logik ist in Phase 1 unit-getestet)

- [ ] **Step 1: Routing-Unpack auf 4-Tupel**

Im `chat`-Handler die zwei Stellen anpassen. Zeile 1094:

```python
        intent, scope_raw, subqueries = "SPECIFIC", None, []
```

zu:

```python
        intent, scope_raw, subqueries, exhaustive_q = "SPECIFIC", None, [], False
```

Zeile 1100:

```python
        intent, scope_raw, subqueries = await _understand_query(llm, body.question)
```

zu:

```python
        intent, scope_raw, subqueries, exhaustive_q = await _understand_query(llm, body.question)
```

- [ ] **Step 2: Effektives Flag berechnen**

Direkt nach dem Routing-Block (nach der Log-Zeile um Zeile 1102) einfuegen. Vorerst nur die erkannte Aufforderung (Per-User-Toggle kommt in Phase 3):

```python
    # "alle Quellen"-Modus: durch die erkannte Aufforderung (Per-User-Toggle ergaenzt
    # diese Bedingung in Phase 3). Post-hoc, daher kein Kontext-Risiko.
    exhaustive_cites = bool(exhaustive_q)
```

- [ ] **Step 3: `_attribute_blocking` nutzt das Flag**

In `_search_one` (Zeile 1743) das Limit modusabhaengig machen:

```python
                            return db.hybrid_search_chunks(workspace["id"], _line, _qv,
                                                           source_ids=source_ids,
                                                           limit=30 if exhaustive_cites else 10)
```

Und im Aufruf von `_attribute_generic_text` (Zeile 1749): `seen_pages_by_source` im exhaustive-Fall auf `None` setzen (ganze Auswahl, nicht nur geholte Seiten) und `exhaustive=` durchreichen:

```python
                    return _attribute_generic_text(_stripped, _search_one, source_id_to_qnum,
                                                   seen_pages_by_source=(None if exhaustive_cites else seen_pages_by_source),
                                                   overview=(intent == "GENERIC" and not scope_chunks),
                                                   context_chunks=chunks,
                                                   refusal_lines=_refusals,
                                                   exhaustive=exhaustive_cites,
                                                   scope_chunks=scope_chunks)
```

- [ ] **Step 4: Backend-Suite (keine Regression)**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS (gesamte Suite)

- [ ] **Step 5: Live-Smoke im Browser**

Frontend :3000, Workspace oeffnen, "Wann muss ich die Hausarbeit abgeben? Zeige mir alle Quellen" fragen. Erwartung: erste Quelle als Chip sichtbar, weitere hinter dem Chevron, mehr als bisher. Screenshot.

---

## PHASE 3 — Per-User-Einstellung (Toggle, Default aus)

### Task 6: DB-Spalte + Repository

**Files:**
- Modify: `backend/src/core/db/schema.py` (Tabelle ~604, Migrationszeilen ~615)
- Modify: `backend/src/features/ai_assistant/repository/chat.py` (`upsert_aia_user_settings` ~108)

- [ ] **Step 1: Spalte in CREATE TABLE + Migration**

In `schema.py` der `CREATE TABLE aia_user_settings` eine Spalte hinzufuegen (nach `language_training_active`):

```sql
                    show_all_sources     BOOLEAN NOT NULL DEFAULT FALSE,
```

Und bei den `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`-Zeilen (nach studio_enabled, ~615) ergaenzen:

```python
            cur.execute("ALTER TABLE aia_user_settings ADD COLUMN IF NOT EXISTS show_all_sources BOOLEAN NOT NULL DEFAULT FALSE")
```

- [ ] **Step 2: `upsert_aia_user_settings` erweitern**

Funktion (Zeile 108) ersetzen, neuer Parameter `show_all_sources: bool = False`:

```python
def upsert_aia_user_settings(
    workspace_id: int, user_id: int, chat_lang: str, studio_enabled: bool,
    language_training_active: bool, show_all_sources: bool = False,
) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aia_user_settings (workspace_id, user_id, chat_lang, studio_enabled, language_training_active, show_all_sources)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (workspace_id, user_id)
                   DO UPDATE SET chat_lang = EXCLUDED.chat_lang,
                                 studio_enabled = EXCLUDED.studio_enabled,
                                 language_training_active = EXCLUDED.language_training_active,
                                 show_all_sources = EXCLUDED.show_all_sources""",
                (workspace_id, user_id, chat_lang, studio_enabled, language_training_active, show_all_sources),
            )
        conn.commit()
```

`get_aia_user_settings` macht `SELECT *`, liefert die Spalte also automatisch mit.

- [ ] **Step 3: Schema-Init smoke**

Run: `cd backend && python -c "from src.core.db import schema; print('schema import ok')"`
Expected: kein Fehler. (Migration laeuft beim App-Start; idempotent durch IF NOT EXISTS.)

---

### Task 7: Schema + Route

**Files:**
- Modify: `backend/src/features/ai_assistant/schemas.py` (`UserSettingsBody` ~72)
- Modify: `backend/src/features/ai_assistant/routes/messages.py` (`update_user_settings` ~126-142)

- [ ] **Step 1: `UserSettingsBody` Feld**

```python
class UserSettingsBody(BaseModel):
    chat_lang: str
    studio_enabled: bool = True
    language_training_active: bool
    show_all_sources: bool = False
```

- [ ] **Step 2: Route reicht Feld durch**

In `messages.py` `update_user_settings` den `db.upsert_aia_user_settings(...)`-Aufruf um `show_all_sources=body.show_all_sources` ergaenzen.

- [ ] **Step 3: Backend-Suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS

---

### Task 8: chat.py liest die Einstellung

**Files:**
- Modify: `backend/src/features/ai_assistant/routes/chat.py` (Flag-Berechnung aus Task 5 Step 2)

- [ ] **Step 1: Toggle in die Flag-Bedingung aufnehmen**

`chat_lang` wird bereits aus `db.get_aia_user_settings(...)` gelesen (Zeile 1053). Dort die Settings in einer Variable halten und das Flag erweitern. Den Block aus Task 5 Step 2 ersetzen durch:

```python
    _user_settings = db.get_aia_user_settings(workspace["id"], user_id) or {}
    # "alle Quellen"-Modus: Per-User-Toggle ODER erkannte Aufforderung. Post-hoc, kein
    # Kontext-Risiko.
    exhaustive_cites = bool(_user_settings.get("show_all_sources")) or bool(exhaustive_q)
```

(Falls `chat_lang` an Zeile 1053 separat geladen wird, dort `_user_settings` wiederverwenden statt doppelt zu lesen.)

- [ ] **Step 2: Backend-Suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS

---

### Task 9: Frontend-Toggle

**Files:**
- Locate + Modify: Chat-Settings-Komponente (`frontend/src/app/[locale]/workspace/[uuid]/_components/chat/`), Settings-Typ, i18n-Strings.

- [ ] **Step 1: Settings-UI + State finden**

Run: `cd frontend && grep -rn "language_training_active\|studio_enabled\|UserSettings\|chat_lang" src --include="*.tsx" --include="*.ts" | grep -iv test`
Die Komponente identifizieren, die die User-Settings rendert und per PUT speichert.

- [ ] **Step 2: Checkbox/Toggle ergaenzen**

Analog zu `studio_enabled` ein `show_all_sources` Toggle mit Label "Alle Quellen anzeigen" (i18n) hinzufuegen, in den Settings-Typ aufnehmen und beim Speichern mit ans Backend senden.

- [ ] **Step 3: Frontend-Build/Lint**

Run: `cd frontend && npm run lint && npx tsc --noEmit`
Expected: keine neuen Fehler.

- [ ] **Step 4: Live-Verifikation im Browser**

Frontend :3000: Toggle an, normale Frage stellen (ohne "alle Quellen"), pruefen dass jetzt alle Fundstellen als Chips (1 + Chevron) erscheinen. Toggle aus, pruefen dass wieder maximal 3. Screenshots.

---

## Self-Review

- **Spec-Abdeckung:** Problem 2 (Erkennung + alle Stellen) → Tasks 4,5 + Phase 1. Problem 1 (Toggle, Default aus, 1 sichtbar + Rest eingeklappt) → Tasks 6-9; Falt-UI existiert bereits (CitationChipGroup). Deckel 10 → Task 1. Ganze Auswahl statt nur geholte Chunks → Task 5 (seen=None) + Task 2. Kein Kontext-Risiko → Architektur (post-hoc), unveraendertes Budget.
- **Platzhalter:** keine; jeder Code-Schritt zeigt den konkreten Code. Task 3/9 Einfuegestellen sind im laufenden Code zu lokalisieren (Prompt-Beispiel, Frontend-Settings), das ist bei diesen zwei bewusst so.
- **Typkonsistenz:** `exhaustive` ist ueberall bool; `_attribute_generic_text(..., exhaustive=...)`, `_chips_for_line(..., exhaustive=...)`, `_line_candidates(..., exhaustive=...)` konsistent benannt; 4-Tupel `(intent, scope, subqueries, exhaustive)` in Parser, Query und beiden Callern.
