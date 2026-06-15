# AI Configuration Export / Import — Design

**Status:** Approved
**Date:** 2026-05-28
**Scope:** Admin-Bereich → Provider-Tab. Export und Import der kompletten KI-Konfiguration (Provider, Voices, Capabilities, Endpoints, Feature-Routes inkl. Modellen und user_choices) als JSON-Datei.

## Motivation

Aktuell muss jede KI-Konfiguration (Provider mit Endpoint/Protocol/Capabilities/Voices + Feature-Route-Zuordnungen mit Modellnamen) auf einem neuen System manuell über die Admin-UI nachgepflegt werden. Bei Multi-Tenant-Setup (mehrere Hochschulen, vgl. [[multi-tenant-branding]]) und beim Aufsetzen neuer Instanzen ist das fehleranfällig und zeitraubend.

Mit Export/Import kann eine vollständige Snapshot-Datei (ohne Secrets) zwischen Systemen übertragen werden — typischer Workflow: bestehende Instanz exportieren, neue Instanz aufsetzen, importieren, dann nur noch API-Keys nachtragen.

## Sicherheits-Invariante

**API-Keys werden niemals exportiert.** Die Export-Datei ist als unverschlüsselter Klartext-JSON konzipiert und darf gefahrlos per E-Mail, Git oder Slack geteilt werden. Diese Invariante zieht sich durch das ganze Design:

- Export-Endpoint strippt `api_key` aus jedem Provider, bevor die Datei generiert wird.
- Beim Export-Download zeigt das Frontend einen Toast mit dem Hinweis "Export enthält keine API-Keys".
- Beim Import zeigt der Vorschau-Dialog für jeden Provider mit Key-Anforderung eine rote Warnzeile.
- Nach erfolgtem Import zeigt die Provider-Liste rot/orange Warn-Indikatoren bei Providern, denen ein Key fehlt.

## Datenmodell — Export-Format

JSON-Datei mit Dateinamen `kis-ai-config-YYYY-MM-DD.json`:

```json
{
  "schema_version": 1,
  "exported_at": "2026-05-28T14:00:00Z",
  "exported_from": "https://kis.th-luebeck.de",
  "providers": [
    {
      "name": "KISSKI",
      "protocol": "openai_compat",
      "base_url": "https://chat-ai.academiccloud.de",
      "capabilities": ["chat", "embedding"],
      "voices": [],
      "enabled": true
    }
  ],
  "feature_routes": [
    {
      "feature": "transcription",
      "provider_name": "KISSKI",
      "model_name": "whisper-large",
      "user_choices": ["KISSKI"],
      "provider_models": { "KISSKI": "whisper-large" }
    }
  ]
}
```

**Designentscheidungen:**

- **Kein `api_key`-Feld:** Wird komplett weggelassen, nicht als `null` gesetzt. Macht visuell klar, dass das Feld nicht existiert.
- **Kein `id`-Feld:** Provider werden über ihren `name` identifiziert. Damit ist die Datei portabel zwischen Systemen — IDs sind DB-lokal.
- **`provider_name` statt `provider_id` in Feature-Routes:** Auflösung in IDs erfolgt erst beim Import auf dem Zielsystem.
- **`user_choices` und `provider_models` als Provider-Namen-Listen / -Maps:** Konsistent mit dem ID-freien Design.
- **`schema_version`:** Aktuell `1`. Erlaubt künftige Format-Migrationen ohne Bruch.
- **`exported_at` / `exported_from`:** Reine Metadaten für den Import-Dialog ("Diese Datei stammt von …"), keine Validierungs-Relevanz.

## Backend — Neue Endpoints

Hinzugefügt zu [backend/src/routes/admin/providers.py](backend/src/routes/admin/providers.py):

### `GET /admin/providers/export`

- Liest alle Provider via `db.list_providers()` und alle Feature-Routes via `db.list_routes()`.
- Strippt `api_key` und `id` aus jedem Provider.
- Übersetzt `provider_id` → `provider_name` in den Routes (Lookup gegen Provider-Liste). Auch in `user_choices` und `provider_models`.
- Antwort:
  - `Content-Type: application/json`
  - `Content-Disposition: attachment; filename="kis-ai-config-<YYYY-MM-DD>.json"`
  - Body: das oben spezifizierte JSON-Objekt.

### `POST /admin/providers/import/preview`

Body:
```json
{ "config": <export-json> }
```

Antwort (Dry-Run, ändert keine DB-Zeile):
```json
{
  "providers": [
    {
      "name": "KISSKI",
      "action": "create",
      "needs_api_key": true,
      "existing_has_key": false,
      "protocol_change": null
    },
    {
      "name": "DeepL DE-EN",
      "action": "update",
      "needs_api_key": true,
      "existing_has_key": false,
      "protocol_change": null
    },
    {
      "name": "Kokoro lokal",
      "action": "create",
      "needs_api_key": false,
      "existing_has_key": false,
      "protocol_change": null
    },
    {
      "name": "AltProvider",
      "action": "update",
      "needs_api_key": true,
      "existing_has_key": true,
      "protocol_change": { "from": "openai_compat", "to": "deepl" }
    }
  ],
  "routes": [
    { "feature": "tts", "action": "create", "resolved_provider": "Kokoro lokal" },
    { "feature": "transcription", "action": "update", "resolved_provider": "KISSKI" },
    {
      "feature": "translation",
      "action": "skip_unresolved",
      "reason": "Provider 'X' nicht im Import enthalten"
    }
  ]
}
```

**Feldsemantik:**

- `action: "create"` — Provider mit diesem Namen existiert nicht auf dem Zielsystem.
- `action: "update"` — Provider existiert, wird überschrieben (außer API-Key).
- `needs_api_key` — `true` für Protocols, die typischerweise einen Key brauchen (`openai_compat` mit externem Endpoint, `deepl`). `false` für `docling` und für rein lokale Provider (Heuristik: `base_url` enthält `localhost`, `127.0.0.1` oder `0.0.0.0`).
- `existing_has_key` — bei `update`: ob der vorhandene Provider bereits einen Key gespeichert hat. Hilft dem Admin zu sehen, dass nichts verloren geht.
- `protocol_change` — bei `update`, wenn das Protocol abweicht. UI zeigt explizite Warnung.
- `routes[].action: "skip_unresolved"` — referenzierter Provider-Name existiert weder im Import noch auf dem Zielsystem. Route bleibt unverändert (falls vorhanden) oder wird nicht angelegt.

**Validierung:** vor dem Bauen der Preview-Antwort:

- `schema_version == 1` — sonst 400 mit klarer Meldung.
- Alle Provider-Protocols ∈ `known_protocols()` — sonst 400 mit Liste der unbekannten.
- Alle Capabilities ∈ `CAPABILITIES` — sonst 400 mit Liste.
- Alle Feature-Namen ∈ `FEATURES` — sonst 400 mit Liste.
- Keine doppelten Provider-Namen im Import — sonst 400.

### `POST /admin/providers/import`

Body:
```json
{ "config": <export-json> }
```

Führt den Merge transaktional aus (dieselbe Validierung wie Preview):

**Provider-Merge-Regeln:**

1. Lookup per `name`.
2. **Existiert nicht** → `db.create_provider(..., api_key=None)`. Kein Key gesetzt — Provider ist initial nicht funktionsfähig bis Admin den Key nachträgt.
3. **Existiert** → `db.update_provider()` mit `protocol`, `base_url`, `capabilities`, `voices`, `enabled` aus dem Import. `api_key` wird **niemals** im Update übergeben — bestehender Key bleibt unangetastet.
4. Nach create/update: `probe_provider(provider_id)` (synchron, blockt aber nur kurz — Endpoint antwortet erst wenn alle Probes durch sind, damit das Frontend frische Status-Daten sieht).

**Feature-Route-Merge-Regeln:**

1. Für jede Route im Import: `provider_name` → `provider_id` per Lookup gegen die (nach Provider-Merge aktualisierte) Provider-Tabelle.
2. Wenn Lookup fehlschlägt → Route wird übersprungen, in der Antwort als `skip_unresolved` markiert.
3. Sonst: `db.set_route(feature, provider_id=..., model_name=..., user_choices=[...], provider_models={...})`. `user_choices` und `provider_models`-Keys werden ebenfalls von Namen zu IDs übersetzt; einzelne nicht-auflösbare Einträge werden weggelassen.
4. Wenn die `embedding`-Route geändert wird → `invalidate_fingerprint_cache()` aufrufen (analog zu `set_feature_route` in `providers.py`).

**Antwort:**
```json
{
  "providers_created": 2,
  "providers_updated": 1,
  "routes_created": 3,
  "routes_updated": 2,
  "routes_skipped": 1,
  "providers_needing_key": ["KISSKI", "DeepL DE-EN"]
}
```

Das Frontend nutzt `providers_needing_key` für die Warn-Indikatoren in der Provider-Liste nach dem Import.

### `DELETE /admin/providers/all`

Destruktiver Reset für den Fall, dass der Admin vor einem Import einen sauberen Zustand will (statt Merge in die bestehende Konfiguration). Bewusst als eigene Aktion getrennt, nicht als Import-Option — so ist die Entscheidung "ich werfe alles weg" eine eigenständige, sichtbare Handlung und nicht ein Häkchen im Import-Dialog.

- Löscht **alle** Zeilen aus der `providers`-Tabelle.
- Löscht **alle** Zeilen aus der `feature_routes`-Tabelle (Feature-Routes referenzieren Provider, werden ohnehin ungültig).
- Ruft `invalidate_fingerprint_cache()` auf (analog zu `set_feature_route`).
- Antwort:
  ```json
  { "providers_deleted": 5, "routes_deleted": 8 }
  ```

Keine zusätzliche Authentifizierung über `get_admin_user` hinaus — die Schutz-Schicht ist die UI-Bestätigung (siehe Frontend).

### Pydantic-Modelle

Neue Modelle in [backend/src/routes/admin/_models.py](backend/src/routes/admin/_models.py):

- `ExportedProvider` — Felder `name`, `protocol`, `base_url`, `capabilities`, `voices`, `enabled`.
- `ExportedFeatureRoute` — Felder `feature`, `provider_name`, `model_name`, `user_choices`, `provider_models`.
- `ExportedConfig` — `schema_version`, `exported_at`, `exported_from`, `providers`, `feature_routes`.
- `ImportConfigRequest` — `config: ExportedConfig`.

## Frontend — UI

### Provider-Tab-Header

Erweitert [ProviderListCard.tsx](frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx):

```
[ Provider ]            [Exportieren] [Importieren] [+ Provider hinzufügen] [⋮]
```

- **Exportieren** → `fetch('/api/admin/providers/export')`, Response als Blob, Browser-Download via `URL.createObjectURL` + temporärer `<a>`-Klick. Danach Toast: *"Export enthält keine API-Keys. Auf dem Zielsystem müssen Keys neu gesetzt werden."*
- **Importieren** → öffnet versteckten `<input type="file" accept="application/json">`. Nach Datei-Auswahl: JSON parsen → an `/api/admin/providers/import/preview` schicken → Preview-Dialog öffnen mit der Diff-Antwort. Bei Parse-Fehler: Fehler-Toast, kein Dialog.
- **⋮ (Drei-Punkte-Menü)** → öffnet Dropdown mit einem Eintrag *"Alles löschen…"* (rot, `text-red-600`). Klick darauf öffnet den Clear-All-Bestätigungs-Modal (siehe unten). Bewusst hinter dem Drei-Punkte-Menü versteckt, weil destruktiv und selten gebraucht.

### Clear-All-Bestätigungs-Modal

Neue Komponente `ClearAllConfirmDialog.tsx`. Zwei-stufiger Schutz: erst Drei-Punkte-Menü öffnen + "Alles löschen" wählen, dann erscheint dieser Modal als zweite explizite Bestätigung.

```
┌─ ⚠ Alle Provider und Routes löschen? ────────────┐
│                                                  │
│   Diese Aktion löscht UNWIDERRUFLICH:            │
│                                                  │
│     • 5 Provider (inkl. aller API-Keys)          │
│     • 8 Feature-Route-Zuordnungen                │
│                                                  │
│   ⚠ KI-Funktionen (Chat, TTS, ASR, Übersetzung,  │
│      Embedding) stehen danach NICHT mehr zur     │
│      Verfügung, bis Provider neu angelegt oder   │
│      importiert wurden.                          │
│                                                  │
│   Diese Aktion kann NICHT rückgängig gemacht     │
│   werden. Vorher ggf. Export erstellen.          │
│                                                  │
│         [Abbrechen]   [Ja, alles löschen]        │
└──────────────────────────────────────────────────┘
```

**Styling:**
- Modal-Header rot (`bg-red-50` mit `border-red-200`, Icon ⚠ in `text-red-600`).
- "Ja, alles löschen"-Button rot (`bg-red-600 hover:bg-red-700`, weißer Text), klar als destruktiv erkennbar.
- "Abbrechen" als Default-Fokus, damit Enter-Taste nicht versehentlich löscht.

**Zähler in der Warnung** (5 Provider / 8 Routes) kommen aus dem aktuellen lokalen State (`providers.length`, `routes.length`) — keine extra API-Calls nötig.

**Klick auf "Ja, alles löschen"** → `DELETE /api/admin/providers/all` → Bei Erfolg: Modal schließen, `refreshAll()` (Liste ist jetzt leer), Toast *"Alle Provider und Routes gelöscht."*

### Import-Preview-Dialog

Neue Komponente `ImportPreviewDialog.tsx`:

```
┌─ Konfiguration importieren ──────────────────────┐
│ Quelle: kis-ai-config-2026-05-27.json            │
│ Erstellt am: 2026-05-27, von kis.th-luebeck.de   │
│                                                  │
│ PROVIDER (3)                                     │
│  KISSKI (openai_compat)                  [NEU]   │
│   ⚠ API-Key fehlt — nach Import setzen!         │
│                                                  │
│  DeepL DE-EN (deepl)                     [MERGE] │
│   ⚠ API-Key fehlt — nach Import setzen!         │
│                                                  │
│  Kokoro lokal (openai_compat)            [NEU]   │
│   ✓ Kein API-Key nötig                          │
│                                                  │
│  AltProvider (deepl)                     [MERGE] │
│   ⚠ Protocol ändert sich: openai_compat → deepl │
│   ✓ Bestehender API-Key bleibt erhalten         │
│                                                  │
│ FEATURE-ROUTES (5)                               │
│  ✓ tts → Kokoro lokal                            │
│  ✓ transcription → KISSKI (whisper-large)        │
│  ⚠ translation → übersprungen                    │
│      (Provider "DeepL US-EN" nicht im Import)    │
│  ...                                             │
│                                                  │
│         [Abbrechen]   [Import bestätigen]        │
└──────────────────────────────────────────────────┘
```

**Styling-Details:**

- `[NEU]` / `[MERGE]` / `[SKIP]` als kleine Badges (Tailwind: `bg-blue-100 text-blue-800`, `bg-amber-100 text-amber-800`, `bg-gray-100 text-gray-600`).
- Rote ⚠-Warnzeile direkt unter dem Provider-Namen, eingerückt: `text-red-600 border-l-2 border-red-600 pl-2`.
- Grüne ✓-Zeile für "Kein API-Key nötig" oder "Bestehender Key bleibt": `text-green-700`.
- Protocol-Change-Warnung: orange (`text-amber-700`), darüber.

**Klick auf "Import bestätigen"** → `POST /api/admin/providers/import`. Bei Erfolg: Dialog schließen, `refreshAll()` der übergeordneten `ProvidersTab`, Toast: *"Import erfolgreich. {n} Provider benötigen noch einen API-Key."*

### Warn-Indikatoren in der Provider-Liste

Nach dem Import (und generell für alle Provider ohne Key, deren Protocol einen erfordert): in [ProviderListCard.tsx](frontend/src/app/[locale]/admin/_components/providers/ProviderListCard.tsx) wird neben dem Provider-Namen eine kleine ⚠-Ikone angezeigt (orange, `text-amber-500`), mit Tooltip *"API-Key fehlt — Provider ist nicht funktionsfähig"*.

Die Heuristik "braucht Key" (frontend-seitig):
- `protocol === "openai_compat"` und `base_url` enthält keine lokale Adresse (`localhost`, `127.0.0.1`, `0.0.0.0`), oder
- `protocol === "deepl"`.

Und gleichzeitig `api_key_set === false`.

### i18n

Alle neuen Strings unter `admin.providers.exportImport.*` in [frontend/messages/de.json](frontend/messages/de.json) und [frontend/messages/en.json](frontend/messages/en.json):

- `exportButton`, `importButton`
- `exportToast` (mit Hinweis auf fehlende Keys)
- `preview.title`, `preview.source`, `preview.createdAt`, `preview.providersHeading`, `preview.routesHeading`
- `preview.badge.new`, `preview.badge.merge`, `preview.badge.skip`
- `preview.apiKeyMissing`, `preview.apiKeyNotNeeded`, `preview.apiKeyPreserved`
- `preview.protocolChange` (mit Platzhaltern `{from}`, `{to}`)
- `preview.routeSkipped` (mit `{provider}`)
- `preview.confirm`, `preview.cancel`
- `importSuccessToast` (mit `{count}`)
- `provider.missingKeyTooltip`
- `errors.invalidJson`, `errors.invalidSchemaVersion`, `errors.unknownProtocol`, `errors.duplicateNames`
- `clearAll.menuItem`, `clearAll.title`, `clearAll.bodyCounts` (mit `{providers}`, `{routes}`), `clearAll.warningFeaturesUnavailable`, `clearAll.warningIrreversible`, `clearAll.confirm`, `clearAll.cancel`, `clearAll.successToast`

### Frontend-API-Layer

Erweitert [_api.ts](frontend/src/app/[locale]/admin/_components/providers/_api.ts):

```ts
export async function exportConfig(): Promise<Blob>;
export async function importPreview(config: unknown): Promise<ImportPreviewResult>;
export async function importConfig(config: unknown): Promise<ImportResult>;
export async function clearAllProviders(): Promise<{ providers_deleted: number; routes_deleted: number }>;
```

Plus passende TS-Types in `_types.ts`.

## Tests

### Backend

Neue Test-Datei `backend/tests/test_provider_import_export.py`:

**Export:**
- `test_export_empty_db_returns_empty_arrays`
- `test_export_strips_api_keys` — Provider mit Key wird exportiert, Key fehlt im Output.
- `test_export_strips_ids` — kein `id`-Feld im Output.
- `test_export_translates_route_provider_ids_to_names`
- `test_export_round_trip_preserves_structure` — Export → Import → erneut Export = strukturell identisch (ohne `exported_at`-Vergleich).
- `test_export_filename_contains_date`

**Import-Preview:**
- `test_preview_new_provider_action_create`
- `test_preview_existing_provider_action_update`
- `test_preview_existing_provider_with_key_existing_has_key_true`
- `test_preview_protocol_change_detected`
- `test_preview_route_with_unknown_provider_skipped`
- `test_preview_does_not_modify_db` — row count vor/nach identisch.
- `test_preview_rejects_unknown_schema_version`
- `test_preview_rejects_unknown_protocol`
- `test_preview_rejects_unknown_capability`
- `test_preview_rejects_unknown_feature`
- `test_preview_rejects_duplicate_provider_names`

**Import-Commit:**
- `test_import_creates_new_providers_without_api_key`
- `test_import_update_preserves_existing_api_key`
- `test_import_update_overwrites_protocol_base_url_capabilities_voices_enabled`
- `test_import_creates_feature_routes`
- `test_import_skips_routes_with_unresolved_providers`
- `test_import_filters_unresolved_user_choices`
- `test_import_filters_unresolved_provider_models_keys`
- `test_import_triggers_reprobe_for_each_provider`
- `test_import_invalidates_fingerprint_cache_when_embedding_route_changes`
- `test_import_response_lists_providers_needing_key`

**Clear-All:**
- `test_clear_all_deletes_all_providers`
- `test_clear_all_deletes_all_feature_routes`
- `test_clear_all_invalidates_fingerprint_cache`
- `test_clear_all_on_empty_db_returns_zero_counts`
- `test_clear_all_response_contains_correct_counts`

### Frontend — manuelle Test-Checkliste

Keine automatisierten Tests (Projekt-Konvention: Provider-UI hat aktuell keine Frontend-Tests). Stattdessen explizite Checkliste, die nach Implementierung durchgegangen wird:

- [ ] Export-Button → JSON-Datei wird heruntergeladen, Toast erscheint.
- [ ] Heruntergeladene Datei enthält weder `api_key`-Felder noch `id`-Felder.
- [ ] Import einer eigenen Export-Datei → Preview zeigt alle Provider als `[MERGE]`, alle Routes als `✓`.
- [ ] Import auf leerem System → alle Provider als `[NEU]`, rote Warnzeilen sichtbar.
- [ ] Import mit Protocol-Change → orange Warnzeile in der Preview.
- [ ] Import mit Route, die auf nicht-existierenden Provider verweist → ⚠ "übersprungen" in der Route-Liste.
- [ ] Nach Bestätigung: Provider-Liste zeigt ⚠-Indikatoren bei Providern ohne Key.
- [ ] Datei kaputt / kein JSON → Fehler-Toast, kein Crash.
- [ ] Falsches `schema_version` → Fehlermeldung "Datei stammt aus einer neueren Version" (oder umgekehrt).
- [ ] Drei-Punkte-Menü → "Alles löschen" → Bestätigungs-Modal erscheint mit korrekten Zählern.
- [ ] Bestätigungs-Modal "Abbrechen" → keine Änderung, Modal schließt.
- [ ] Bestätigungs-Modal "Ja, alles löschen" → Provider-Liste ist danach leer, Toast erscheint.
- [ ] Default-Fokus im Modal liegt auf "Abbrechen" (Enter löscht nicht aus Versehen).

## Edge-Cases (explizit abgehandelt)

- **Kaputte JSON-Datei:** Parse-Fehler im Frontend → Toast, Dialog wird nicht geöffnet.
- **Zukünftiges Schema-Version:** Backend liefert 400 mit "Diese Datei stammt aus einer neueren KIS-Version" — Frontend zeigt Fehler-Toast mit dieser Message.
- **Provider-Name mit anderem Protocol:** Wird als `update` mit `protocol_change`-Feld behandelt. UI zeigt orange Warnung in der Preview. Admin entscheidet, ob er das will.
- **Route verweist auf Provider, der weder im Import noch im Zielsystem existiert:** Route wird übersprungen, nicht angelegt. Existierende Route bleibt unverändert.
- **`user_choices` enthält Provider-Name, der nicht auflösbar ist:** Einzelner Eintrag wird stillschweigend weggelassen, Route geht trotzdem durch. (Sonst würde ein einziger fehlender Choice die ganze Route blockieren.)

## Out-of-Scope (YAGNI)

- Keine Schedule-/Auto-Backup-Funktion.
- Keine Verschlüsselung oder Signing der Export-Datei (Klartext-JSON reicht — keine sensiblen Daten drin).
- Kein Replace-Modus innerhalb des Import-Flows — wer einen sauberen Stand will, nutzt vorher die separate Clear-All-Aktion (Drei-Punkte-Menü) und importiert danach. Diese explizite Zwei-Schritt-Sequenz macht "ich werfe alles weg" zu einer bewussten Entscheidung statt einer leicht übersehenen Import-Checkbox.
- Kein Multi-File-Bundle / ZIP mit mehreren Configs.
- Keine UI für Konflikt-Auflösung "field by field" — Provider-Felder werden komplett überschrieben (außer Key), das ist explizit und einfach.
- Keine Prompts/Templates im Export (würde Scope sprengen — kann später als separates Feature ergänzt werden mit kompatiblem Schema-Versionssprung).

## Akzeptanzkriterien

1. Admin kann auf der Provider-Tab-Seite eine JSON-Datei mit der kompletten Konfiguration herunterladen.
2. Datei enthält **kein** `api_key`-Feld und **kein** `id`-Feld.
3. Beim Klick auf Export wird im UI darauf hingewiesen, dass die Datei keine Keys enthält.
4. Admin kann eine solche Datei (oder eine aus einem anderen System) hochladen und sieht eine Vorschau, die jeden Provider und jede Route mit Aktion (`NEU`/`MERGE`/`SKIP`) zeigt.
5. Jeder Provider in der Vorschau, der einen Key braucht, hat **direkt darunter eine rote Warnzeile** "API-Key fehlt — nach Import setzen!".
6. Nach Bestätigung: Provider werden angelegt/aktualisiert, Routes werden gesetzt, bestehende API-Keys bleiben erhalten, neue Provider haben keinen Key.
7. Nach dem Import zeigt die Provider-Liste rot/orange Warn-Indikatoren bei Providern, deren Key fehlt.
8. Alle UI-Strings sind in DE und EN übersetzt.
9. Backend-Tests decken die Sicherheits-Invariante (kein Key im Export), die Merge-Regeln, und die Validierung ab.
10. Admin kann über ein Drei-Punkte-Menü oben im Provider-Tab die Aktion "Alles löschen" auswählen. Nach Klick erscheint ein **zweiter** Bestätigungs-Modal mit rotem Warnhinweis und korrekten Zählern (X Provider, Y Routes). Erst nach expliziter Bestätigung im Modal werden alle Provider und Feature-Routes gelöscht.

