# LLM-Chunk-Citations — Design

**Datum:** 2026-06-03
**Branch:** `feat/aia-llm-chunk-citations`
**Status:** approved (Brainstorming), in Umsetzung

## Problem

Wir wissen heute **nicht**, aus welchen Chunks die KI ihre Antwort bezieht. Das
Modell tippt eine Seite/einen Timestamp, den es **rät** — die Hauptfehlerquelle
(falsche Seite, gedroppte Chips bei Cross-Page-Ties). Das nachgelagerte
lexikalische Matching rekonstruiert die Position nur, es *weiß* sie nicht.

## Idee

Das Modell gibt pro Aussage/Zeile **alle genutzten Chunk-IDs** zurück — **nur
Chunk-IDs**, keine Seiten. Seite/Offset/Timestamp leiten **wir** aus dem Chunk
ab. Die genannte Chunk-ID wird **lexikalisch verifiziert**, bevor wir sie
übernehmen (lieber keine als die falsche Quelle).

## Design

1. **Chunk-IDs im Kontext** — jeder `<document>`-Block bekommt zusätzlich eine
   eindeutige, kurze ID: `<document index="N" id="C">` (N = Quelle, C = Chunk,
   global `1..K` in Kontext-Reihenfolge). Eine `chunk_registry: cid -> {qnum,
   source, is_media, page|start_time/end_time, content}` wird beim Kontextbau
   aus den ohnehin gesammelten `source_index[qn]["chunks"]` aufgebaut.

2. **Prompt (nur RAG-Antwortpfad)** — Chip-Position ist die Chunk-ID:
   `[N, #C | keyword]`. Das Modell kopiert das `id`-Attribut des `<document>`,
   aus dem die Aussage stammt (es *sieht* die ID, muss keine Seite raten). Pro
   genutztem Chunk **ein** Chip; mehrere Chunks → mehrere Chips. Keine Seiten/
   Timestamps mehr vom Modell. Keyword bleibt verbatim (für Anker + Anzeige).

3. **`resolve_chunk_refs(text, registry, loader)`** (neu, `_chunk_cite.py`) läuft
   **zuerst** pro Zeile:
   - `[N, #C | kw]` parsen; `C` in Registry nachschlagen (unbekannt → Chip droppen).
   - **Verifizieren**: matcht der Zeilen-Klartext den Chunk-Inhalt?
     (`match_query` gegen die eine Chunk-Unit; PDF exakt, Media stem-aware).
     Nein → Chip droppen.
   - **PDF**: Seite = `chunk.page` (autoritativ); Anker via
     `loader.offset_suffixes(source, page, line)` → `[N, S.page@off | span]`,
     sonst `[N, S.page | kw]`.
   - **Media**: präziser Timestamp = bestes Transcript-Segment im Chunk-Fenster
     `[start_time, end_time]` (sonst `chunk.start_time`) → `[N, MM:SS | kw]`.
   - Quellen-Nummer kommt aus dem **Chunk** (`entry.qnum`), nicht aus dem
     getippten `N` → noch robuster.
   - Alle nicht aufgelösten `#C` werden entfernt (kein roher Marker erreicht je
     den Nutzer).

4. **Augmentieren, nicht ersetzen** — Pipeline pro Zeile:
   ```
   sanitize → chipify_inline → resolve_chunk_refs
   (kein Chunk-Ref auf der Zeile?) → resolve_citation_positions   # defensiv für Alt-Format
   → fill_uncited_lines                                           # Sicherheitsnetz
   ```
   Verifiziert kein genannter Chunk / nennt das Modell keinen → der heutige
   Filler greift wie bisher. PDF-Highlight-Anker (Architektur B) unverändert.
   Chip-Format zum Frontend **unverändert** (`[N, S.X@off | span]` / `[N, MM:SS | kw]`).

5. **Telemetrie** — die rohen genannten Chunk-IDs pro Zeile werden mitgeloggt,
   damit „welche Chunks?" nachvollziehbar bleibt.

## Scope & Risiken

- Nur **mid + large**. Kleine Modelle (8B-Minimum) emittieren IDs evtl.
  unzuverlässig → **nach Test ehrlich in der README dokumentieren**, kein Blocker.
- Mehr Tokens (ID je Aussage). Modell muss `id` korrekt kopieren (leichter als
  Seite raten, da sichtbar im Tag).

## Tests

- Backend pytest (neue `_chunk_cite`-Tests + bestehende grün halten).
- e2e + Live-MCP über alle Szenarien: all sources / einzeln / generic /
  specific / video.

## Bewusst unverändert

PDF-Matcher (`_citation_match`, `_reground_by_line`, `offset_suffixes`) bleibt —
dient jetzt als **Verifizierer + Fallback**. Siehe
[[project-citation-generic-vs-specific]], [[project-citation-highlight-plain-anchor]].
