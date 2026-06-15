# Highlight-Rework: Offset-Anchoring (Architektur B)

**Goal:** Die Quellen-Markierung deterministisch machen: der Backend berechnet die
exakte Zeichen-Spanne der zitierten Aussage auf der Seite und schickt sie als
`@start-end`-Offset im Chip. Das Frontend zeichnet genau diese Spanne — **kein**
Sentence-/Paragraph-Raten mehr.

**Architecture:** Backend öffnet die Quell-PDF von der Platte
(`aia_sources.file_path`), liest den `get_text_range()` der zitierten Seite
(gleiche pdfium-Engine + gleiche Datei wie der EmbedPDF-Viewer → Zeichen-Indizes
sind deckungsgleich), lokalisiert die Aussage, expandiert auf **Satz-Grenze** und
hängt `@start-end` + kurzen Verify-Anchor an den Chip. Frontend löst Offsets →
Geometrie direkt auf (`applyInstantSelection`), mit Verify-und-Fallback-Kette.
Keine DB-Migration, keine Re-Ingestion.

**Tech Stack:** pypdfium2 (Backend), EmbedPDF/pdfium-WASM (Frontend), FastAPI,
Postgres, Next.js/React, pytest, vitest, Playwright.

---

## Warum B die Qualität hebt

Heute: Chip trägt ein kurzes Keyword. Das Frontend (`_highlight.ts`, 660 Z.)
**sucht** das Keyword neu und **rät** Satz-/Absatz-/Bullet-Grenzen. Das Raten ist
die Hauptquelle für "markiert zu viel / falsche Stelle".

B: Die Grenzen werden **einmal, serverseitig, deterministisch** berechnet — dort
liegen die volle Aussage (Chat-Zeile) und der volle, saubere Seitentext vor. Der
Chip trägt die fertige Spanne. Das Frontend zeichnet sie nur noch.

## Chip-Format (rückwärtskompatibel)

```
[Q1, S. 8 @123-187 | anchor]
```
- `@123-187` = Zeichen-Offsets [start,end] in den `get_text_range()`-Text der Seite.
- `anchor` = kurzer Verify-Text (erste ~6 Wörter ab `start`, verbatim vom Seitentext).
- Fehlt `@…` (OCR-Seite, Tabelle, kein Treffer) → alter Chip `[Q1, S. 8 | kw]`
  bzw. positions-only `[Q1, S. 8]`. Voll abwärtskompatibel.

## Koordinaten-Räume

- Backend `get_text_range()` → String `T`. Offsets sind Indizes in `T`.
- Frontend `getTextSlices(0..totalChars)` → `R`. Bei gleicher Engine/Datei `R == T`.
- `applyInstantSelection` will Geometrie-Index → vorhandenes `findGeo(rawIdx)`
  mappt `R`-Index → Geometrie-Index (Phantom-Chars). Backend liefert `R`-Index.
- **Drift-Schutz:** Frontend verifiziert `anchor` bei `start`. Stimmt es nicht,
  `R.indexOf(foldedAnchor)` → Delta → Spanne verschieben (gleiche Länge). Anchor
  gar nicht in `R` → Legacy-Keyword-Pfad.

---

## File Structure

**Backend (neu):** `backend/src/features/ai_assistant/routes/_page_geometry.py`
- `get_page_text(source, page_number, *, cache) -> str | None`
- `locate_claim_span(page_text, claim_text) -> tuple[int,int] | None`
- `offset_anchor(page_text, start, end) -> str`
- `build_offset_suffix(...) -> str` (`" @s-e"` + Anchor-Keyword)

**Backend (ändern):** `_helpers.py`
- `_CITE_RESOLVE_RE`: optional `@\d+-\d+` nach der Seite tolerieren.
- `resolve_citation_positions._sub`: PDF-Zweige → Offset-Suffix anhängen.
- `fill_uncited_lines`: gefüllte PDF-Zeile → Offset-Suffix anhängen.
- `SourceUnitLoader`: Per-Request-Cache für Seitentext durchreichen.

**Frontend (ändern):**
- `_components/chat/_citations.tsx`: Regex `@(\d+)-(\d+)`, `offsets` durchreichen.
- `_hooks/useViewerActions.ts`: `pillClick`/`openViewer` → `highlightOffsets`.
- `_types.ts`: `ViewerState.highlightOffsets?: [number, number]`.
- `_components/viewer/PdfViewer.tsx`: Offsets an `doHighlightSearch`.
- `_components/viewer/_highlight.ts`: `tryHighlightByOffsets` + Fallback.

---

## Tasks

### Task 1: Backend `_page_geometry.py`
- `get_page_text`: pypdfium2 öffnen (nur PDF, nicht-Media), Seite `page-1`,
  `get_text_range()`, in Request-Cache `{(source_id,page): text}`. None bei
  Fehler/leer (OCR-Seite).
- `locate_claim_span(T, claim)`: längst-zusammenhängender Token-Lauf des `claim`
  der verbatim (fold-normalisiert, längenerhaltend) in `T` vorkommt → Kern [a,b];
  auf Satzgrenze in `T` expandieren (`.!?`, Newline, Bullet; Abkürzungs-Guard wie
  Frontend). [start,end] in `T`-Koordinaten oder None.
- `offset_anchor(T, start, end)`: erste ≤6 Wörter ab `start`, ohne `[]|❘\n`.
- Sprach-agnostisch (nur Punktuation/Whitespace/Unicode-Case), keine Wortlisten.

### Task 2: Resolver/Fill verdrahten
- Helfer `_with_offsets(meta, page_n, anchor_or_line, kw_suffix) -> suffix_str`
  zentral: holt `get_page_text`, `locate_claim_span` über die **Chat-Zeile**
  (model) bzw. die gefüllte Zeile; baut `" @s-e | <anchor>"`. Fällt auf
  bestehendes `kw_suffix` zurück, wenn keine Offsets.
- In `resolve_citation_positions._sub` an allen PDF-Rückgaben einsetzen
  (matched keyword, regrounded, position-only).
- In `fill_uncited_lines` für PDF (nicht-Media): Offsets statt nur `kw`.
- `_CITE_RESOLVE_RE` + `_HAS_CITE` erweitern, damit `@s-e` nicht stört.

### Task 3: Backend-Tests (`test_citation_offsets.py`)
- `locate_claim_span`: Satz-Lokalisierung, Satzgrenzen, Abkürzung, kein-Treffer.
- Chip-Format: `@s-e` erscheint; ohne Seitentext → alter Chip.
- Bestehende 85 Citation-Tests bleiben grün (Fallback intakt).

### Task 4: Frontend Parsing + Threading
- `_citations.tsx` Regex: `(?:@(\d+)-(\d+))?` zwischen Seite und `|`.
  `offsets = start>=0 ? [start,end] : undefined`. An `onChipClick` anhängen.
- `CitationChipClickHandler`, `pillClick`, `openViewer`, `setViewerSource`,
  `ViewerState` um `offsets`/`highlightOffsets` erweitern.
- `PdfViewer.tsx`: `doHighlightSearch(..., source.highlightOffsets)`.

### Task 5: Frontend `_highlight.ts`
- `doHighlightSearch(refs, reg, page, text, exactSelection=false, offsets?)`.
- `tryHighlightByOffsets`: Seitentext via `getTextSlices`. Verify `anchor` (= `text`)
  fold-gleich bei `start`; sonst `indexOf` → shift; sonst → `tryHighlightOnPage`
  (Legacy). `findGeo(start/end)` → `applyInstantSelection` → scroll. **Keine**
  Expansion.
- Offsets fehlen → unverändert `tryHighlightOnPage`.

### Task 6: Frontend-Tests (vitest)
- `_citations` Regex parst `@s-e` korrekt, alte Chips unverändert, `offsets`
  korrekt durchgereicht.

### Task 7: Live-Test (Playwright) + Iteration
- Test-Bed: Frontend :3000, Login a/a. PDF-Workspace öffnen.
- **specific**-Frage, **generic**-Frage, **popupaction** je einmal; Chip klicken;
  Markierung prüfen (richtige Seite, exakter Satz, kein Footer/Überschuss).
- Bei Abweichung: Backend-Lokalisierung/Frontend-Verify nachschärfen, erneut testen.

## Out of Scope (YAGNI)
- Multi-Span pro Chip (Textmarker-Tupfen) — bewusst gestrichen.
- Geometrie-Persistenz in DB / Re-Ingestion — lazy aus Datei genügt.
- OCR-Seiten mit Box-Geometrie — bleiben positions-only.
