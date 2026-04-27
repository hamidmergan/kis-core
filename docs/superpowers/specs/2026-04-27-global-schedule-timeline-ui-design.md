# Globale Schedule UI auf Workspace-Timeline-Optik umstellen

**Datum:** 2026-04-27
**Branch:** feat/global-schedule

## Ziel

`/schedule` und das `UpcomingDeadlinesWidget` auf der `/workspaces`-Seite sollen visuell exakt wie der Workspace-Zeitplan aussehen (Datum-Tile links, durchgehende vertikale Linie, Cards mit Title/Time/Description). Das aktuelle, kompakte Listen-Layout (`ScheduleListItem`) wird ersetzt.

Verhalten bleibt 1:1 wie heute: ganze Card klickbar zum Workspace, Checkbox read-only, "Erledigte ausblenden"-Toggle, Infinite Scroll, kein Edit-Mode.

## Visuelle Änderung

- Layout: Datum-Tile + vertikale Linie + Card pro Eintrag (Pixel-identisch zum Workspace-Zeitplan).
- Card-Inhalt:
  - Title + Time/Description-Subline wie im Workspace.
  - Statt des Quellen-Chip-Blocks (im Workspace unten, mit dashed top border): Workspace-Chip (Folder-Icon bei `owned`, Users-Icon bei `enrolled`, KB-Background bei owned, Outline bei enrolled, mit `module_title`).
  - Checkbox-Slot: read-only Indikator. Wenn `is_checked`: grüner Kreis mit Check (wie aktuell `ScheduleEntryCard`). Wenn nicht: leerer Kreis im selben Slot, ohne onClick.
  - Kein Edit/Delete-Block (kein editMode global).
- Kein "Nach Vereinbarung"-Block: API `/api/ki-assistent/schedule/upcoming` liefert nur dated Entries.

## Code-Architektur

### Datei-Plan

**[frontend/src/components/schedule/ScheduleTimeline.tsx](frontend/src/components/schedule/ScheduleTimeline.tsx)** (NEU, shared)

Hochgezogene Layout-Logik aus der aktuellen Workspace-Timeline. Pure Datums-Gruppierung, vertikale Linie, Today-Indikator (Dot mit ring/glow). Generisch über den Entry-Type, parametrisiert via Render-Prop.

```ts
interface SharedTimelineProps<T extends DatedEntry> {
  entries: T[];
  renderCard: (entry: T, ctx: { isToday: boolean; isPast: boolean; urgency: string | null }) => ReactNode;
  // Workspace-Anwendungsfall: TBD-Block "Nach Vereinbarung" am Ende
  tbdEntries?: T[];
  renderTbdCard?: (entry: T) => ReactNode;
}

interface DatedEntry {
  id: number | string;
  due_date: string;       // YYYY-MM-DD
  due_time?: string | null;
  is_checked?: boolean;
}
```

Helper (`parseYMD`, `sortByDate`, `formatDay`, `isToday`, `isPast`) wandern aus der Workspace-Timeline mit hierhin.

**[frontend/src/components/schedule/ScheduleEntryCardGlobal.tsx](frontend/src/components/schedule/ScheduleEntryCardGlobal.tsx)** (NEU)

Optik 1:1 wie [`ScheduleEntryCard`](frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleEntry.tsx) (gleicher `baseStyle`, gleiche Title-/Time-/Description-Logik via `cleanScheduleDescription`). Unterschiede:

- Checkbox-Slot: read-only Indikator (kein `onClick`, kein `aria-label` als Button).
- Statt Quellen-Chips: ein einzelner Workspace-Chip im selben dashed-border-top-Container (Folder/Users-Icon + `module_title`, owned vs. enrolled Styling).
- Kein editMode-Block.
- Card als Ganzes klickbar via `onClick` Prop (springt zum Workspace `tab=schedule`).

**[frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleTimeline.tsx](frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleTimeline.tsx)** (REFACTOR)

Wird zum dünnen Wrapper. Importiert die shared Timeline und reicht `renderCard` durch, das den Workspace-spezifischen `ScheduleEntryCard` (mit `sources`, `sourceNumByUuid`, `editMode`, `onEdit`, `onDelete`, `onPillClick`) rendert. `tbdEntries` + `renderTbdCard` werden nur hier befüllt.

Bleibt in `_components/studio/`, weil die Workspace-Card und ihre Props dort hingehören. Die aktuelle Datei verschlankt sich auf etwa 30 Zeilen.

**[frontend/src/app/schedule/page.tsx](frontend/src/app/schedule/page.tsx)** (UPDATE)

`<ScheduleListItem>`-Loop wird ersetzt durch `<ScheduleTimeline entries={...} renderCard={(e) => <ScheduleEntryCardGlobal entry={e} onClick={() => router.push(...)} />} />`. Der äußere Container (`rounded-2xl border`) entfällt oder wird angepasst, da die Timeline ihr eigenes Layout liefert und vertikale Linie + Tiles sonst durch eine Border abgeschnitten würden. Padding/Margin der Timeline werden so gewählt, dass sie ohne Wrapper-Border sauber stehen.

`hideChecked`-Toggle, Pagination/Sentinel, Spinner und Empty-State bleiben unverändert.

**[frontend/src/app/workspaces/_components/UpcomingDeadlinesWidget.tsx](frontend/src/app/workspaces/_components/UpcomingDeadlinesWidget.tsx)** (UPDATE)

`<ScheduleListItem>`-Loop wird ersetzt durch dieselbe Timeline mit denselben drei Einträgen. Der Widget-Header ("Nächste Termine" + "Alle anzeigen"-Button) bleibt. Der Widget-Wrapper (gerundete Box mit Border) wird ggf. angepasst (z. B. Padding um die Timeline herum), damit die vertikale Linie nicht direkt am Border klebt.

**[frontend/src/components/schedule/ScheduleListItem.tsx](frontend/src/components/schedule/ScheduleListItem.tsx)** (DELETE)

Nach den beiden Updates nirgends mehr referenziert (vorher gegrept: nur `schedule/page.tsx` und `UpcomingDeadlinesWidget.tsx` nutzen es). Datei wird gelöscht. Das `ScheduleListEntry`-Interface wandert nach `ScheduleEntryCardGlobal.tsx` (oder, falls dort sinnvoll, in eine neue `components/schedule/types.ts`, je nach Größe).

### Wiederverwendete Helfer

`urgencyColor`, `todayISO`, `cleanScheduleDescription` bleiben in [frontend/src/components/schedule/utils.ts](frontend/src/components/schedule/utils.ts). Datums-Helfer (`parseYMD`, `formatDay`, `isToday`, `isPast`, `sortByDate`) ziehen mit der Timeline um (lokal in `ScheduleTimeline.tsx`, nicht öffentlich exportiert, weil sie nirgends sonst gebraucht werden).

## Datenflow

- Backend-Endpoint `/api/ki-assistent/schedule/upcoming` bleibt unverändert. Liefert `ScheduleListEntry[]` mit `module_uuid`, `module_title`, `module_relation`, `due_date`, `due_time`, `title`, `description`, `is_checked`.
- Frontend mappt die Einträge ohne Adapter direkt auf die globale Card. Workspace-Timeline mappt ihre `ScheduleEntry[]` auf die Workspace-Card. Beide Entry-Typen sind kompatibel mit dem `DatedEntry`-Constraint der shared Timeline.

## Manuelle Verifikation

- `/schedule`:
  - Timeline rendert wie der Workspace-Zeitplan.
  - Klick auf Card öffnet `/workspaces/<uuid>?tab=schedule` (gleiches Verhalten wie aktuell).
  - "Erledigte ausblenden" Toggle wirkt.
  - Infinite Scroll lädt weitere Seiten beim Scrollen.
  - Erledigte Einträge zeigen grünen Check-Indikator und sind opaker (analog Workspace).
- `/workspaces` Widget:
  - Drei Termine im Timeline-Stil sichtbar.
  - "Alle anzeigen" springt zu `/schedule`.
  - Wenn keine Termine: Widget rendert nicht (wie heute).
- Workspace-Zeitplan (Regression-Check):
  - Edit-Mode (Pencil/Trash) funktioniert.
  - Quellen-Chips öffnen weiterhin den PDF-Viewer an der richtigen Stelle.
  - "Nach Vereinbarung"-Block für TBD-Einträge wird gerendert.
  - PDF-Highlight via `onPillClick` weiterhin korrekt (FontBBox-Fix bleibt unberührt, da reiner UI-Refactor).

## Out of Scope

- Backend-Änderungen.
- Card-Click toggling der Checkbox in der globalen Ansicht (bleibt read-only).
- Edit-Mode in der globalen Ansicht.
- Sortier-/Filter-/Suchfunktionen.
- Mobile-spezifische Layout-Anpassungen jenseits des bestehenden responsive Verhaltens (`max-w-5xl`, `min-w-max` etc. bleiben).

## Risiken

- Refactor der Workspace-Timeline kann Regressionen einführen (insb. TBD-Block, Today-Dot-Glow). Workspace-Zeitplan muss nach dem Refactor manuell durchgeklickt werden.
- Widget-Container-Padding kann mit dem Timeline-internen Padding kollidieren und in einer doppelten Border / abgeschnittenen Linie resultieren. Lösung: Wrapper-Padding so anpassen, dass die Timeline frei stehen kann.
- `ScheduleEntryCardGlobal` darf nicht versehentlich auf den Edit-Mode-Pfad oder die `sources`-Props zurückgreifen. Klar getrennte Komponente statt Conditional Logic in der Workspace-Card.
