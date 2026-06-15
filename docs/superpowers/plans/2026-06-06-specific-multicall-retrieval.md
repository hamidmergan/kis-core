# SPECIFIC Retrieval: relevanz-pro-Quelle + großes Budget + Multi-Call

> Status: **UMGESETZT + VERIFIZIERT** (2026-06-06). Per-Source-Retrieval und Multi-Call (map-reduce) sind live. Vorgelagert abgeschlossen: unified post-hoc Attribution + Highlight-Removal + SPECIFIC 1-Quellen-Recall-Fix (Pool 40→80, limit 20→200), siehe [2026-06-06-aia-unified-attribution-no-highlight.md](2026-06-06-aia-unified-attribution-no-highlight.md).

## Option 2: Relevanz-gewichteter Budget-Split (Ist-Stand, ersetzt "alles schicken")
Problem das auffiel: "kein Hybrid-Hit abschneiden" hieß ~160 Hits/Quelle schicken, **davon meist Noise** — beim Autor-Fall 946 Chunks gesendet, nur 5 enthalten den Namen. Ein Name embeddet nicht nah an der Frage (Rang ~59), also lässt sich Noise NICHT vor dem LLM von der Antwort trennen. Lösung: nicht reinigen, sondern **Menge deckeln + relevanz-gewichtet aufteilen**.

`_allocate_specific_budget(kept, char_budget)` in `chat.py`:
- EIN Gesamt-Char-Budget (= `context_budget`) auf die on-topic-Quellen (nach Gate) verteilen.
- Gewicht je Quelle = `threshold - src_best` (näher dran → mehr Chars); Fallback gleichgewichtet.
- **Floor** `_SPECIFIC_FLOOR_CHARS=4000` (gedeckelt auf `budget//K`) → jede on-topic-Quelle ist vertreten (Fall "jedes Doc nennt einen Autor"); Rest nach Gewicht oben drauf → Total ≈ budget → meist **1 Call**.
- 1 Quelle → ganzes Budget (tiefer Rang-59-Fakt passt).
- Verifiziert: 946→328 Chunks @250k (Autor da), Edge-Cases ok, Suite 323 grün.
- **Trade-off bewusst:** lange Low-Relevance-Tails (Noise) werden gekappt — das ist der Zweck. Multi-Call bleibt als Sicherheitsnetz, feuert nur noch selten.

## UMSETZUNG (Ist-Stand)
- **Packer** `_pack_context_batches(chunks, budget, …, multi)` in `chat.py`:
  - `multi=False` (GENERIC/SCOPE/popup): EIN Batch, Überlauf wird verworfen (Überblick darf truncaten).
  - `multi=True` (SPECIFIC, `_specific_path and not source_text`): Überlauf spillt in WEITERE Batches, **nichts wird abgeschnitten**. Chunk-ids starten je Batch bei 1. `seen_pages_by_source` = Union über alle Batches (Media → leeres Set).
- **Map-Reduce** in `_stream()`: bei >1 Batch je Batch ein paralleler non-stream MAP-Call (`asyncio.gather`), dann gestreamter REDUCE-Call mit `aia_reduce_user_message(question, partials)`. Token-Summe der Map-Calls fließt in den usage-log (`_map_tok_in/out`). Fällt alles leer aus → Fallback 1 Call über Batch 0.
- **Reduce-Prompt** `aia_reduce_user_message` in `tool_prompts.py`: behält jeden Fakt aus mind. EINER Teilantwort, ignoriert "nicht in den Quellen"-Teilantworten, eine saubere Antwort (keine Meta-Sätze), Sprache = Frage. Danach normale post-hoc nav-only Attribution.
- **Budget pro Call** = `_context_budget()` (Admin-Knopf, Default `AIA_CONTEXT_MAX_CHARS=60000`). Höheres Budget ⇒ weniger Batches/Calls.

## VERIFIZIERT
- Packer-Unit: multi spillt korrekt, single truncatet (alt), ids/Media-Set korrekt.
- Autor-Fall (3× VFHMUT, 477 Hits): @60k alt 66/477 (Autor FEHLT) vs. neu 8 Batches 477/477 (Autor da); @250k 2 Batches. Map+Reduce live: Reduce übernimmt Namen, verwirft Sentinel.
- Backend-Suite: 323 passed.

## OFFEN / Bewusst NICHT
- **Kein Call-Hard-Cap** (würde wieder truncaten — gegen die Regel). Quellenzahl wird durch das Source-Distanz-Gate begrenzt; bei sehr vielen großen on-topic Quellen + winzigem Budget viele Calls → Mitigation: Admin-Budget anheben (Default evtl. auf 250k). Produktentscheidung, NICHT still geändert.
- Reranker: optional später, falls Multi-Calls zu teuer.

---
## Ursprünglicher Plan (zur Referenz)

## Ziel / harte Regel
Bei SPECIFIC darf **kein pgvector-relevanter Chunk ungeprüft weggeschnitten** werden. Lieber mehrere LLM-Calls als eine Antwort, die den entscheidenden Chunk nie gesehen hat (Bug: Autor auf Rang 59 fiel aus dem Top-20).

## Rahmenentscheidungen (abgestimmt 2026-06-06)
- **Minimum-Tier ist jetzt Mid/Large** (Small/8B/32k raus) → großer Kontext ok. Siehe Memory `project-minimum-model-tier`.
- **Budget pro Call = 450k Zeichen** (~128k Token; konfigurierbar). Nicht „nur 1 Call" — 450k ist das Budget JE Call.
- **Multi-Call:** passen mehr relevante Kandidaten rein als ein 450k-Kontext fasst → 2./3. Call mit dem Rest, Antworten zusammenführen.

## Ablauf SPECIFIC (neu)
1. Frage **einmal** embedden.
2. **Pro gewählter Quelle** eine Hybrid-Suche (relevanz-ranked, query_vector wiederverwenden) → je Quelle ihre relevantesten Chunks. (Ersetzt globale Top-N-Suche + diversify.)
3. Relevanz-Gate: nur Chunks innerhalb eines Distanz-Schwellwerts gelten als „relevante Kandidaten" (damit wir nicht über das ganze 1463-Chunk-Doc multi-callen, sondern nur über echt Relevantes).
4. Kandidaten **round-robin pro Quelle** in den Kontext packen, **relevanz-first**, bis 450k voll.
5. Bleiben relevante Kandidaten übrig → **nächster Call** mit dem Rest (wieder bis 450k), usw.
6. Antworten der Calls **zusammenführen** → finale Antwort.
7. **Post-hoc nav-only Attribution** auf der finalen Antwort (pro Zeile pgvector + Cross-Check) → Chips. (unverändert)

## GENERIC bleibt wie es ist
- Round-Robin **doc-order**-Füllung, **1 Call**, Truncation ok (Überblick muss nicht alles sehen). Kein Multi-Call.

## Vor dem Coden noch zu klären (nächster Schritt: Ablauf skizzieren)
- **Relevanz-Gate**: welcher Distanz-Schwellwert definiert „relevanter Kandidat" (analog `_DIST_FACTOR` 1.3)? Verhindert Multi-Call über irrelevante Massen.
- **Batching**: wie genau die Kandidaten in ≤450k-Batches schneiden (relevanz-first, pro Quelle fair).
- **Zusammenführen**: Map-Reduce (jeder Batch antwortet → mergen) vs Refine (laufende Antwort weiterreichen). Inkl.: was, wenn nur 1 Batch den Fakt hat.
- **Obergrenze Calls**: Hard-Cap (z.B. max 3 Calls) gegen Kosten-Explosion bei riesigen Korpora.
- **Budget-Konfig**: wo 450k lebt (env/Admin), pro-Modell adaptiv?
- **Chips nach Multi-Call**: Attribution läuft auf der zusammengeführten Antwort — bestätigen, dass das mit den Quell-IDs sauber ist.

## Explizit NICHT
- Fixe 450k als Ein-Call-Lösung (löst Überlauf nicht).
- Optimierung auf 32k-Kontext (Min-Tier ist jetzt Mid/Large).
- Reranker — optionales Effizienz-Add-on SPÄTER, falls Multi-Calls zu häufig/teuer.
