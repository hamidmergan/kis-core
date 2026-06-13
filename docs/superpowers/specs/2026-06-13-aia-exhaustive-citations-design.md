# AIA: Alle Fundstellen als Zitat-Chips anzeigen

Datum: 2026-06-13
Branch: feat/aia-show-all-citations

## Problem

Beobachtet im Chat bei der Frage "Wann muss ich die Hausarbeit abgeben".

1. Ein Fakt steht in mehreren Dokumenten, aber inline werden nur 2 bis 3 Quellen
   als Chip gezeigt. Die restlichen geholten Quellen tauchen nur stumm im
   "X Quellen"-Aufklapper auf.
2. Die ausdrueckliche Aufforderung "Zeige mir alle Quellen / alle Stellen" wird
   nicht erfuellt. Die Antwort bleibt kompakt und zeigt teils sogar weniger Chips.

## Ursache

- Attribution ist post-hoc, also nach der Antwort, per Embedding-Suche
  (`backend/src/features/ai_assistant/routes/_helpers.py`). Sie kostet kein
  LLM-Kontext-Budget.
- Zwei harte Grenzen kappen die Chips bewusst:
  - `_MAX_CHIPS_PER_LINE = 3` (max 3 Chips pro Antwortzeile).
  - `_MULTI_CHIP_MAX_DELTA = 0.08` (zweite/dritte Quelle nur, wenn semantisch
    fast so nah wie die beste).
- Kandidaten sind zusaetzlich auf geholte Chunks geklammert (`_is_seen`), damit
  ein Chip nie auf eine ungelesene Seite zeigt.
- Es gibt nur zwei Intents: GENERIC und SPECIFIC (`_understand_query`). Kein
  "zaehle alle Fundstellen auf". "alle Quellen" wird wie eine normale Frage
  behandelt und verpufft.

## Entscheidungen

- Ausgabe bei "alle Stellen": kurze normale Antwort plus jede Fundstelle als
  Chip (Quelle + Seite oder Zeit). Kein zusaetzlicher Text. Damit kein
  Kontext-Risiko, weil alles post-hoc bleibt.
- Toggle (Problem 1) und Aufforderung (Problem 2) nutzen denselben Mechanismus.
  Einziger Unterschied ist der Ausloeser.
- Suchumfang haengt am Modus:
  - OFF (Default): wie heute, Stellen nur aus den geholten Chunks.
  - ON: Suche ueber die ganze aktive Dokumentauswahl (alle aktiven
    `source_ids`), nicht nur die geholten Chunks.
- ON-Suche: exakte Treffer (Datum, Name, Zahl woertlich) plus Semantik am schon
  kalibrierten 0.6-Gate (`_GENERIC_ATTRIB_MAX_DIST`).
- Deckel: maximal 10 Fundstellen pro Zeile, damit nichts explodiert.
- Weil reine Navigations-Links: ein Chip darf im ON-Modus auch auf eine
  ungelesene Seite zeigen. Das ist hier gewollt.

## Design

### Ein Mechanismus, zwei Ausloeser

Ein Flag `exhaustive` pro Antwort. Gesetzt, wenn:
- die Per-User-Einstellung an ist, ODER
- in der Nachricht eine "alle Quellen/Stellen"-Aufforderung erkannt wurde.

### Erkennung (Problem 2)

- `_understand_query` bekommt ein zusaetzliches Feld im Ergebnis, z.B. `exhaustive: bool`.
- Erkennung sprach-agnostisch per LLM, keine Wortlisten (siehe Projekt-Regel
  "Language-Agnostic Required"). Faengt "alle Quellen", "alle Stellen",
  "wo ueberall", "show all sources" und Aequivalente in jeder Sprache.
- Bei Parse-Fehler: `exhaustive = false` (konservativ).

### Attribution-Verhalten

- OFF: Kandidaten nur aus geholten Chunks (`_is_seen`), Kappe `_MAX_CHIPS_PER_LINE = 3`,
  Delta-Gate aktiv. Unveraendert gegenueber heute.
- ON:
  - Kandidatenquelle: alle aktiven `source_ids` der Auswahl, nicht nur geholte.
  - `_is_seen`-Klammer aus.
  - Kappe und Delta-Gate aus, stattdessen Deckel 10 pro Zeile.
  - Treffer: exakt plus Semantik am 0.6-Gate, dedupliziert pro Quelle/Seite
    bzw. Quelle/Zeit.

### Frontend

- Pro Zeile genau 1 Chip sichtbar, der Rest hinter einem kleinen
  "+N"-Aufklapper. Gilt fuer beide Modi:
  - OFF: 1 sichtbar, bis zu 2 eingeklappt.
  - ON: 1 sichtbar, alle weiteren (bis 10) eingeklappt.
- Per-User-Toggle in den Chat-Einstellungen. Default aus.

### Kein Kontext-Risiko

- Antwortgenerierung und 250k-Zeichen-Budget (`_context_budget`) bleiben
  unveraendert.
- Mehrkosten im ON-Modus: zusaetzliche Embedding- und Exakt-Match-Suchen ueber
  die Auswahl. Skaliert mit Zahl der Zeilen und Quellen, nicht mit Kontext.

## Nicht im Umfang

- Kein Ausformulieren der Stellen durch das LLM (bewusst verworfen wegen
  Kontext-Risiko).
- Keine Aenderung am Retrieval fuer die eigentliche Antwort.
- Keine Aenderung am bestehenden "X Quellen"-Aufklapper unter der Antwort.

## Offene Punkte fuer die Planung

- Genauer Speicherort der Per-User-Einstellung (wo Chat-User-Praeferenzen
  liegen).
- Exakte Signatur-Aenderungen an `_understand_query` und der
  Attribution-Pipeline.
- Frontend-Komponente fuer den "+N"-Chip-Aufklapper.
