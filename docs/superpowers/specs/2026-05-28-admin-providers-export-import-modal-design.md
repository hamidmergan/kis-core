# Admin Providers — Export/Import Modal mit Provider-Auswahl

**Status:** Draft
**Date:** 2026-05-28
**Scope:** Admin → Provider-Tab. UX-Refactoring der bestehenden Export/Import-Funktion: Zwei prominente Toolbar-Buttons werden zu einem Kebab-Menüeintrag, der ein Modal mit zwei Tabs (Export, Import) öffnet. Im Export-Tab kann der Admin zusätzlich auswählen, welche Provider exportiert werden.

Knüpft an [`2026-05-28-ai-config-export-import-design.md`](2026-05-28-ai-config-export-import-design.md) an — Backend-Endpoints und Sicherheits-Invariante (API-Keys werden nie exportiert) bleiben unverändert.

## Motivation

Die aktuelle Toolbar im Provider-Tab ist überladen: `Export`, `Import`, `+ Hinzufügen`, Kebab. Zwei dieser Aktionen (Export/Import) sind seltene Admin-Operationen und gehören nicht prominent ins Hauptgeschoss. Gleichzeitig fehlt eine Möglichkeit, beim Export nur eine Teilmenge der Provider auszuwählen — typischer Use-Case: Test-Provider nicht ins Produktiv-Export mitnehmen.

Ziel: Aufgeräumte Toolbar, gebündelte Export/Import-UX, plus optionale Provider-Filterung beim Export.

## UX

### Toolbar

**Vorher:**
```
[ ⇩ Export ] (?)  [ ⇧ Import ]  [ + Hinzufügen ]  [ ⋮ ]
```

**Nachher:**
```
                                 [ + Hinzufügen ]  [ ⋮ ]
```

Top-Level Export- und Import-Buttons sowie der HelpTooltip neben `Export` entfallen. Der `EmptyState` (sichtbar bei 0 Providern, dort gibt es kein Kebab) behält seinen lokalen Import-Button als alleinigen Einstiegspunkt für den Erst-Import.

### Kebab-Menü

```
┌──────────────────────────────┐
│ ⇅ Export / Import…           │
│ ──────────────────────────── │
│ 🗑 Alle löschen              │
└──────────────────────────────┘
```

Neuer Eintrag „Export / Import…" oben, Divider, dann der bestehende „Alle löschen". Klick auf den neuen Eintrag öffnet das Modal im Export-Tab.

### Modal — Export-Tab (Standard)

```
┌─ Export ── Import ──────────────────────────────┐
│                                                  │
│  ⚠ Die exportierte Datei enthält KEINE          │
│    API-Keys — diese müssen am Zielsystem        │
│    manuell neu gesetzt werden.                  │
│                                                  │
│  ─ Provider ────────────── 3 von 3 · Alle/Keine │
│  ☑ OpenAI                                       │
│  ☑ Anthropic                                    │
│  ☑ Kokoro                                       │
│                                                  │
│            [ Abbrechen ]  [ Exportieren (3) ]   │
└──────────────────────────────────────────────────┘
```

- **Hinweis-Block** oben: Amber-Box (gleiches Styling wie `protocolChange` im bisherigen Preview), Text aus dem bereits eingeführten i18n-Key `exportHint`.
- **Provider-Liste**: alle Provider mit Checkbox, default alle angehakt. Provider-Reihenfolge wie in `providers[]`.
- **Header rechts**: Counter `{selected} von {total}` + Toggle-Link, der zwischen „Alle"/„Keine" umschaltet abhängig vom aktuellen Zustand.
- **Footer-Button** `Exportieren ({count})`: disabled wenn `count === 0`.
- **Klick auf Exportieren**:
  1. `exportConfig()` (existing) lädt das volle Export-JSON.
  2. Frontend filtert client-side:
     - `providers[]` → das Backend exportiert ohne DB-IDs und verschlüsselt alle Cross-Referenzen über `name` (vgl. `build_export`). Filter daher per Name: `providers.filter(p => selectedNames.has(p.name))`.
     - `feature_routes[]` → für jede Route:
       - Wenn `provider_name` **nicht** in `selectedNames` → Route komplett verwerfen (Primär-Provider fehlt, Import würde sie ohnehin skippen).
       - Sonst: `user_choices[]` auf selektierte Namen reduzieren, `provider_models`-Keys auf selektierte Namen reduzieren. Route bleibt im Export, aber referenziert nur noch ausgewählte Provider.
  3. Gefiltertes JSON als Blob → Download → Modal schließt.
- **Edge Case**: 0 Provider in der DB ist unmöglich, da das Modal nur über Kebab erreichbar ist und Kebab nur bei `providers.length > 0` rendert.

### Modal — Import-Tab

```
┌─ Export ── Import ──────────────────────────────┐
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │   ⇧  JSON-Datei hier ablegen oder      │    │
│  │      Klick zum Auswählen               │    │
│  └────────────────────────────────────────┘    │
│                                                  │
└──────────────────────────────────────────────────┘
```

Nach Datei-Auswahl wird die Drop-Zone durch das Preview ersetzt:

```
┌─ Export ── Import ──────────────────────────────┐
│  📄 kis-ai-config-2026-05-20.json  (Andere      │
│     Datei wählen)                                │
│                                                  │
│  ─ Provider (3) ───────────────────────────────  │
│  OpenAI                              [NEU]      │
│    ⚠ API-Key fehlt — nach Import setzen!        │
│  Anthropic                           [MERGE]    │
│    ✓ Bestehender API-Key bleibt erhalten        │
│  Kokoro                              [NEU]      │
│    ✓ Kein API-Key nötig                         │
│                                                  │
│  ─ Feature-Routes (4) ─────────────────────────  │
│  ✓ chat → OpenAI                                │
│  ⚠ tts übersprungen (Provider „X" nicht im…)    │
│                                                  │
│            [ Abbrechen ]  [ Import bestätigen ] │
└──────────────────────────────────────────────────┘
```

- **Drop-Zone**: Drag&Drop + Klick → `<input type="file" accept="application/json">`.
- **Preview-Sektionen**: identisches Layout und identische i18n-Strings wie der bisherige `ImportPreviewDialog`. Die dortige Rendering-Logik (Badges, per-Provider API-Key-Hinweis, Route-Skip-Hinweis) wird in das Tab übernommen.
- **„Andere Datei wählen"**-Link über der Provider-Liste setzt den Tab zurück in den Drop-Zone-Zustand.
- **Footer-Button** `Import bestätigen` ist erst sichtbar, wenn ein gültiger Preview vorliegt.
- **Fehlerbehandlung im Tab** (nicht als `window.alert`):
  - Datei ist kein JSON → Inline-Error in der Drop-Zone (`exportImport.errors.invalidJson`).
  - `importPreview()` wirft → Inline-Error (`exportImport.errors.importFailed`).
  - `importConfig()` wirft → Inline-Error unter Footer-Button, Modal bleibt offen.

### Modal-Verhalten

- **Esc-Taste** und **Click-Outside** schließen das Modal — außer während einer laufenden Import-Bestätigung. Pattern entspricht `ImportPreviewDialog.tsx`/`ProviderFormDialog.tsx`.
- **Tab-Wechsel** verwirft keinen State: Wechselt der Admin nach Datei-Auswahl im Import-Tab zum Export-Tab und zurück, ist das Preview noch da.
- **Default-Tab**: Export.

## Datenfluss

```
Kebab "Export / Import…"
  └─► setDialog({ open: true, mode: "export-import" })
        └─► <ExportImportDialog />
              ├─ Tab "Export"
              │    └─► User Klick "Exportieren"
              │          └─► exportConfig()  → filter client-side  → download blob  → setDialog({ open: false })
              └─ Tab "Import"
                   └─► User wählt Datei
                         └─► file.text() + JSON.parse  → importPreview(config)  → Preview-State im Tab
                               └─► User Klick "Import bestätigen"
                                     └─► importConfig(config)  → refreshAll()  → setDialog({ open: false })
```

## Komponenten-Struktur

**Neu:** `frontend/src/app/[locale]/admin/_components/providers/ExportImportDialog.tsx` (~250 Zeilen)
- Default-Export: `<ExportImportDialog>` — Modal-Shell mit Esc/Click-Outside, Tab-Bar, Sub-Komponenten in derselben Datei.
- Sub-Komponenten (modul-intern, nicht exportiert):
  - `ExportTab` — Hinweis-Block, Provider-Liste mit Checkboxen, Header-Counter+Toggle, Footer-Button. Hält `selectedNames: Set<string>`.
  - `ImportTab` — Drop-Zone-Zustand vs. Preview-Zustand, übernimmt Render-Logik aus dem alten `ImportPreviewDialog` (interne Hilfs-Komponenten `Badge`, `extractProviderFromReason`).
- Props:
  ```ts
  type Props = {
    providers: Provider[];
    initialTab: "export" | "import";
    onClose: () => void;
    onExportDownload: (filteredConfig: unknown, filename: string) => void;
    onImportPreview: (config: unknown) => Promise<ImportPreviewResult>;
    onImportConfirm: (config: unknown) => Promise<void>;
  };
  ```
  Filter-Logik, i18n-Lookup und Datei-Parsing leben im Dialog. Network-Calls (`importPreview`, `importConfig`, `exportConfig`) und Side-Effects (Blob-Download, Refresh) bleiben hinter Callbacks im Parent (`index.tsx`) — gleiches Pattern wie bisher.

**Geändert:** `ProviderListCard.tsx`
- Entfernt: Top-Level Export-Button, Import-Button (inkl. zugehörigem `<input ref={fileInputRef}>`), `HelpTooltip`-Import.
- Entfernt aus Props: `onExport`, `onImport`. Neu: `onOpenExportImport: (initialTab: "export" | "import") => void`.
- Kebab-Menü: neuer Eintrag `{t("list.exportImportMenuItem")}` oben, ruft `onOpenExportImport("export")` und schließt das Menü. Divider und „Alle löschen" bleiben.
- `EmptyState` behält seinen lokalen Import-Button; dessen Klick ruft `onOpenExportImport("import")` — Modal öffnet direkt im Import-Tab, Drop-Zone bereit. Einheitlicher Code-Pfad für alle Importe (kein paralleler Legacy-Flow).

**Geändert:** `providers/index.tsx`
- `DialogState` Variante `"import-preview"` entfällt. Neue Variante:
  ```ts
  | { open: true; mode: "export-import"; initialTab: "export" | "import" }
  ```
- `handleExport` wird zu `handleExportDownload(filteredConfig, filename)`: nur noch Blob-Erzeugung und Download (Filter passiert im Dialog).
- `handleImportFile` und `handleImportConfirm` werden zusammengefasst in `handleImportConfirm(config)`: ruft `importConfig`, refresht, schließt Modal. Die `importPreview`-Call und Datei-Parsing wandern in den `ImportTab`.
- Erfolgs-`window.alert` aus `handleImportConfirm` entfällt — der Tab-State (Modal geschlossen + frische Provider-Liste) ist Feedback genug. Optional: kompakter Status-Hinweis im Tab vor dem Schließen (siehe „Offen" unten).
- `<ProviderListCard onOpenExportImport={...} />` statt `onExport`/`onImport`.
- `<ImportPreviewDialog>` aus dem JSX entfernt.

**Gelöscht:** `ImportPreviewDialog.tsx`. Render-Logik wandert in `ExportImportDialog.tsx`.

## i18n

Neue Strings unter `admin.providers` (in `de.json` und `en.json`):

- `list.exportImportMenuItem` — Kebab: „Export / Import…"
- `exportImport.modal.title` — Modal-Titel: „Export / Import"
- `exportImport.modal.tabExport` — Tab-Label: „Exportieren"
- `exportImport.modal.tabImport` — Tab-Label: „Importieren"
- `exportImport.export.providersHeading` — „Provider"
- `exportImport.export.selectAll` — „Alle"
- `exportImport.export.selectNone` — „Keine"
- `exportImport.export.selectedCount` — „{selected} von {total}"
- `exportImport.export.confirmButton` — „Exportieren ({count})"
- `exportImport.import.dropzoneHint` — „JSON-Datei hier ablegen oder klicken zum Auswählen"
- `exportImport.import.chooseAnotherFile` — „Andere Datei wählen"
- `exportImport.import.confirmButton` — „Import bestätigen"

Wiederverwendet (unverändert):
- `exportImport.exportHint` — Hinweis-Block im Export-Tab.
- `exportImport.preview.*` — Badges und per-Provider Hinweise im Import-Tab.
- `exportImport.errors.*` — Inline-Fehler im Import-Tab.
- `exportImport.importSuccessToast` — entfällt (Modal-Close = Feedback).

Entfernt:
- `exportImport.exportToast` (bereits in vorherigem Refactor zu `exportHint` umbenannt).

## Sicherheit & Invarianten

- **API-Keys**: Backend strippt weiterhin. Der client-side Filter berührt nur `providers[]` und `feature_routes[]`, fügt keine Felder hinzu.
- **Partielle Routes**: Eine Route wird komplett verworfen, sobald ihr Primär-Provider oder einer ihrer `provider_models`-Keys nicht ausgewählt ist. So wird kein halbgefiltertes `provider_models`-Objekt exportiert, das den Importer durcheinanderbringt.
- **Filename**: bleibt `kis-ai-config-YYYY-MM-DD.json` (aus Backend-Header übernommen, nicht client-side gesetzt).

## Tests

Kein Backend-Change, keine neuen Backend-Tests.

Frontend-Tests (falls Testharness existiert; aktuell sind im Provider-Bereich keine Komponenten-Tests vorhanden — siehe Bestand): keine neuen Tests in diesem Spec, da bestehende Provider-Komponenten ebenfalls untestet sind und Test-Setup-Aufbau außerhalb des Scopes liegt.

Manuelle Verifikation:
1. Voller Export (alle ausgewählt) erzeugt identische Datei wie bisheriger Export.
2. Teil-Export deselektiert einen Provider → JSON enthält ihn nicht, Routes, die ihn referenzieren, fehlen ebenfalls.
3. Import mit Drop&Drop zeigt Preview inline.
4. Import-Bestätigung schließt Modal und zeigt frische Provider-Liste.
5. Esc und Click-Outside schließen das Modal in beiden Tabs.

## Offen / Nicht in diesem Spec

- **Erfolgs-Feedback nach Import**: Aktuell schließt das Modal kommentarlos. Für Phase 2 ggf. ein dezenter Toast oder Inline-Banner mit der bisherigen Message `importSuccessToast`. Entscheidung vertagt.
- **Backend-Filter** als Endpoint-Variante (`?provider_ids=…`): explizit abgewählt zugunsten client-side Filter.
- **Route-only-Toggle**: explizit abgewählt — Routes folgen den Providern.
