# AIA Generic-Kontext: dynamisches Budget statt fester Caps — Design

**Datum:** 2026-05-31
**Status:** approved
**Verwandt:** [[project-minimum-model-tier]], [[language-agnostic-required]],
[[project-tier-testing-pending]], `2026-05-31-aia-generic-specific-tests-design.md`

## Problem

Der GENERIC-Pfad (Überblicksantworten) in
`backend/src/features/ai_assistant/routes/chat.py` baut pro Quelle bis zu **30**
Seiten-Summaries (PDF) bzw. **8** Roh-Chunks (Media) als Kontext
([chat.py:264-265](../../../backend/src/features/ai_assistant/routes/chat.py#L264-L265)).
Der fertige Kontext wird **nach Quelle gruppiert** sortiert
([chat.py:543](../../../backend/src/features/ai_assistant/routes/chat.py#L543))
und am Ende bei **200 000 Zeichen** hart abgeschnitten
([chat.py:576](../../../backend/src/features/ai_assistant/routes/chat.py#L576)).

Zwei Defekte daraus, die beide erst auf kleinen Modellen sichtbar werden:

1. **Truncation-Grenze ist nicht tier-sicher.** 200 000 Zeichen ≈ ~50 000 Tokens.
   Das KIS-Minimum-Tier ist Small (8 B, **32 k** Context, siehe
   [[project-minimum-model-tier]]). Plus System-Prompt, Frage, History und Platz
   für die Antwort sprengt das den 32-k-Context **heute schon** — der Cap ist für
   das kleinste unterstützte Modell zu groß.

2. **Gruppierte Reihenfolge killt bei Truncation ganze Quellen.** Weil alle
   Chunks von Quelle 1, dann alle von Quelle 2 … einsortiert werden, frisst die
   erste Quelle ihr Budget auf, die zweite das nächste — und sobald die Grenze
   greift, fallen die **hinteren Quellen komplett raus** (Quelle 4–30 unsichtbar),
   statt dass jede Quelle einen fairen, dünneren Anteil behält.

Beides untergräbt genau das Ziel „alle Tiers unterstützen": auf dem Tier, das
am meisten Schutz braucht, verschwinden Quellen lautlos.

## Ziel

Generic-Kontext so bauen, dass er **immer ins kleinste Tier passt** und der
verfügbare Platz **fair über alle aktiven Quellen** verteilt wird — ohne pro
Modell etwas konfigurieren zu müssen und ohne dass eine spätere Änderung am
Quellen-Limit (`aia_workspace_max_sources`, admin-tunbar 1–1000) eine
Code-Anpassung erzwingt.

## Nicht-Ziele (bewusst verworfen)

- **Tier-UI / Preset-Dropdown (Small/Mid/Large)** im Admin.
- **Pro-Modell-Feld `context_window`/`tier`.** Existiert nicht im Datenmodell
  (Modelle sind freie Namens-Strings,
  [_models.py:80-86](../../../backend/src/routes/admin/_models.py#L80-L86)) und
  müsste neu eingeführt + vom Admin korrekt gepflegt werden — Magic Number mit
  Pflegeaufwand.
- **Admin-Setting „Context-Budget".** YAGNI: DB-Key + GET/PATCH + Validierung +
  i18n + Frontend-Feld für eine Zahl, die fast nie jemand anfasst. Escape-Hatch
  ist die benannte Konstante in `limits.py` (deren Header explizit als
  Ops-Schraube gedacht ist) — eine Zeile beim Deploy.
- **Doc-Summary-Swap für sehr große Docs** (statt N verstreuter Seiten-Summaries
  die kohärente Doc-Summary nehmen). Sinnvolle mögliche Ergänzung, aber separat;
  hier out of scope.
- **SPECIFIC-Pfad-Umbau.** Für Themenfragen entscheidet Relevanz (Hybrid-Search
  Top-20), nicht Quellen-Gleichgewicht — die Quellen-Anzahl beeinflusst die
  Präzision dort nicht. Specific erbt nur die tier-sichere Truncation-Konstante.

## Ansatz: dynamisches Budget + Round-Robin

Kernidee: **ein** tier-sicheres Gesamt-Budget (Zeichen) ist die einzige echte
Grenze. Die festen Pro-Quelle-Zahlen entfallen; stattdessen werden die Segmente
**reihum** (Round-Robin) über die Quellen eingefüllt, bis das Budget erschöpft
ist. Erschöpfte Quellen (z. B. eine 2-Seiten-PDF) fallen aus der Rotation und
ihr Platz fließt automatisch an die verbleibenden — ein „Water-Filling", das
sich ohne Sonderfälle ergibt.

Verhalten, das daraus **automatisch** folgt:

- **Wenige Quellen → Tiefe.** 1–3 Quellen: jede kriegt nahezu all ihre
  Seiten-Summaries (budgetbegrenzt).
- **Viele Quellen → Breite.** 30 Quellen teilen sich das Budget → jede ist mit
  ein paar Segmenten vertreten, keine fällt raus.
- **Kleine Quellen voll drin.** Eine 2-Seiten-Quelle liefert ihre 2 Segmente und
  scheidet aus; der frei werdende Platz geht an die dicken Quellen.
- **Skaliert mit jedem `aia_workspace_max_sources`.** Das Budget wird durch das
  jeweils aktuelle N geteilt — 30 → 50 → 1000 ohne Code-Change.

Dass mehr Quellen die Generic-Antwort gröber machen, ist dabei **unvermeidbar
und gewollt** (fixes Context-Fenster, geteilt über mehr Quellen = Breite statt
Tiefe), nicht ein Defekt.

## Mechanik

Drei Änderungen, alle in/um `_assemble_generic_context` und den geteilten
Kontext-Builder in `chat.py`:

1. **Pro-Quelle-Decke hoch statt fix.** `PAGE_SUMS_PER_SOURCE` (30) und
   `MEDIA_CHUNKS_PER_SOURCE` (8) werden durch **eine** großzügige
   Sicherheits-Decke ersetzt (Vorschlag `AIA_GENERIC_MAX_SEGMENTS_PER_SOURCE =
   900` in `limits.py`). Da eine PDF höchstens `AIA_SOURCE_MAX_PAGES = 300`
   Seiten hat, ist `_sample` damit für PDFs praktisch ein No-op: **alle**
   Seiten-Summaries werden zu Kandidaten, das Budget schneidet ab — nicht die
   Decke. Die Decke verhindert nur absurd lange Kandidatenlisten (sehr lange
   Videos).

2. **Round-Robin-Reihenfolge.** Jedes Generic-Segment bekommt einen
   **Quellen-internen Sequenz-Index** (0,1,2 … in Kandidaten-Reihenfolge). Die
   finale Sortierung wird `(seq, panel_order)` statt der heutigen
   Quellen-Gruppierung
   ([chat.py:543](../../../backend/src/features/ai_assistant/routes/chat.py#L543)):
   erst Segment 0 jeder Quelle (in Panel-Reihenfolge), dann Segment 1 jeder
   Quelle, usw. Der bestehende Truncation-`break` im Kontext-Builder
   ([chat.py:576-577](../../../backend/src/features/ai_assistant/routes/chat.py#L576-L577))
   schneidet dann **am Ende = in späten Runden** ab → jede Quelle behält ihre
   frühen Segmente.

3. **Tier-sichere Truncation-Konstante.** Das hartcodierte `200000`
   ([chat.py:576](../../../backend/src/features/ai_assistant/routes/chat.py#L576))
   wird durch eine benannte Konstante in `limits.py` ersetzt (Vorschlag
   `AIA_CONTEXT_MAX_CHARS ≈ 60000`). Rechen-Rationale als Kommentar: 32 k Tokens
   − Reserve für System-Prompt/Frage/History/Antwort ≈ ~24 k Tokens Kontext;
   bei konservativ ~3,5 Zeichen/Token (gemischt DE/Nicht-Latein,
   [[language-agnostic-required]]) ≈ ~60 k Zeichen. Finaler Wert beim Testen
   über die Tiers tunbar ([[project-tier-testing-pending]]).

**Integrationshinweis für den Plan:** Die heutige Sortierung in
[chat.py:543](../../../backend/src/features/ai_assistant/routes/chat.py#L543) hat
einen Zweck (Doc-Index läuft in Panel-Reihenfolge, niedrige Quellen bei
Truncation bevorzugt). Der `(seq, panel_order)`-Schlüssel erhält den
Panel-Reihenfolge-Aspekt als Sekundär-Sortierung; der Plan muss prüfen, dass die
interleavte `<document index="N">`-Folge (Indizes wiederholen sich: 1,2,3,1,2,3)
den Citation-Resolver nicht stört (`source_index` ist nach `qn` aggregiert, also
voraussichtlich unkritisch — verifizieren).

## Auswirkung auf SPECIFIC

Nur Punkt 3 (geteilte Truncation-Konstante) wirkt auf den SPECIFIC-Pfad, weil
der Kontext-Builder geteilt ist. Das ist erwünscht: auch eine Themenfrage muss
auf einem 32-k-Modell passen. SPECIFIC ist von Natur aus klein (Top-20 +
Per-Source-Fallback bis 3,
[chat.py:460-506](../../../backend/src/features/ai_assistant/routes/chat.py#L460-L506))
und nutzt die `(seq, …)`-Sortierung — falls sie für beide Pfade gilt — sogar
fairer (bester Treffer je Quelle überlebt zuerst). Kein gezielter Umbau nötig.

## Tests

`backend/tests/test_chat_paths.py` (gemockte DB, deterministisch):

- **Anpassen:** `test_generic_multi_source_caps_page_summaries_per_source`
  ([test_chat_paths.py:187-199](../../../backend/tests/test_chat_paths.py#L187-L199))
  — die Erwartung `{1: 30, 2: 30}` gilt nicht mehr; neu gegen die hohe Decke
  bzw. „alle Summaries werden Kandidaten" prüfen.
- **Neu — Round-Robin-Fairness:** Bei einem künstlich kleinen Budget und N
  Quellen behält **jede** Quelle ≥ 1 Segment (kein Quellen-Dropout). Beweist
  Defekt 2 behoben.
- **Neu — Water-Filling:** Mix aus einer winzigen (z. B. 2 Segmente) und großen
  Quellen → die winzige ist vollständig drin, ihr Rest-Platz geht an die großen.
- **Neu — Budget-Grenze:** Gesamt-Zeichen des gebauten Kontexts ≤
  `AIA_CONTEXT_MAX_CHARS`.
- **Skaliert mit N:** bei kleinerem Budget/größerem N sinkt Segmente-pro-Quelle,
  ohne dass eine Quelle leer ausgeht.

Playwright-Smoke (siehe Schwester-Spec) bleibt gültig: Generic über alle Quellen
rendert weiter mehrere Quellen-Chips.

## Offene Punkte

- Finaler `AIA_CONTEXT_MAX_CHARS`-Wert empirisch über die drei Tiers + eine
  Nicht-Deutsch-Quelle bestätigen ([[project-tier-testing-pending]]).
- Citation-Resolver-Verträglichkeit mit interleavten Doc-Indizes verifizieren
  (Integrationshinweis oben).
