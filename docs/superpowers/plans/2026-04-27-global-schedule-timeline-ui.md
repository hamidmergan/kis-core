# Globale Schedule UI auf Workspace-Timeline-Optik Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/schedule` und `UpcomingDeadlinesWidget` auf das Timeline-Layout des Workspace-Zeitplans umstellen, ohne Verhalten zu ändern.

**Architecture:** Workspace-Timeline-Logik wird in eine shared Komponente unter [frontend/src/components/schedule/](frontend/src/components/schedule/) gehoben, parametrisiert via `renderCard`. Eine neue `ScheduleEntryCardGlobal` Komponente repliziert die Workspace-Card-Optik mit Workspace-Chip statt Quellen-Chips und ohne Edit-Mode. Workspace-Timeline wird dünner Wrapper. `ScheduleListItem` wird gelöscht.

**Tech Stack:** React 19, Next.js App Router, Tailwind, Phosphor-Icons, CSS-Variablen (`--kb`, `--accent`, `--text`, `--muted`, `--border`, `--bg`).

**Spec:** [docs/superpowers/specs/2026-04-27-global-schedule-timeline-ui-design.md](docs/superpowers/specs/2026-04-27-global-schedule-timeline-ui-design.md)

**Wichtige Projektregeln:**
- Frontend läuft auf `npm run dev` (Port 3000) und wird NICHT angefasst. Hot-Reload prüft Änderungen automatisch.
- Phosphor-Icons immer `weight="bold"`.
- Workspace-Chip nutzt KB-Color (Blau), nicht Accent (im Workspace-Subtree Lila).
- Niemals committen ohne explizite User-Anweisung. Commit-Steps sind als "User-Commit" markiert.
- Keine Em-/En-Dashes in Code/Strings.

---

## File Structure

**Erstellt:**
- `frontend/src/components/schedule/ScheduleTimeline.tsx` (shared Timeline-Layout, generisch via Render-Prop)
- `frontend/src/components/schedule/ScheduleEntryCardGlobal.tsx` (globale Card-Variante mit Workspace-Chip)

**Modifiziert:**
- `frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleTimeline.tsx` (wird Wrapper für shared Timeline)
- `frontend/src/app/schedule/page.tsx` (List-Loop → Timeline)
- `frontend/src/app/workspaces/_components/UpcomingDeadlinesWidget.tsx` (List-Loop → Timeline)

**Gelöscht:**
- `frontend/src/components/schedule/ScheduleListItem.tsx` (nicht mehr referenziert nach Update)

---

## Task 1: Shared Timeline-Komponente bauen

**Files:**
- Create: `frontend/src/components/schedule/ScheduleTimeline.tsx`

Ziel: Layout-Logik der aktuellen Workspace-Timeline (Datum-Tile, vertikale Linie, Today-Dot, optionaler "Nach Vereinbarung"-Block) als generische Komponente herausziehen. Render-Prop für die Card. Helper bleiben lokal.

- [ ] **Step 1.1: Datei anlegen mit Helpers + Komponente**

Inhalt von `frontend/src/components/schedule/ScheduleTimeline.tsx`:

```tsx
import type { ReactNode } from "react";
import { todayISO, urgencyColor } from "./utils";

export interface DatedEntry {
  id: number | string;
  due_date: string | null;
  due_time?: string | null;
  is_checked?: boolean;
}

interface CardContext {
  isToday: boolean;
  isPast: boolean;
  urgency: string | null;
}

interface ScheduleTimelineProps<T extends DatedEntry> {
  entries: T[];
  renderCard: (entry: T, ctx: CardContext) => ReactNode;
  renderTbdCard?: (entry: T) => ReactNode;
}

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function sortByDate<T extends DatedEntry>(entries: T[]): T[] {
  return [...entries].sort((a, b) => {
    const da = a.due_date ? parseYMD(a.due_date).getTime() : 0;
    const db = b.due_date ? parseYMD(b.due_date).getTime() : 0;
    if (da !== db) return da - db;
    const ta = a.due_time || "";
    const tb = b.due_time || "";
    return ta.localeCompare(tb);
  });
}

function formatDay(dateStr: string, today: Date): { day: string; month: string; year: string | null } {
  const d = parseYMD(dateStr);
  const months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  const showYear = d.getFullYear() !== today.getFullYear();
  return {
    day: String(d.getDate()).padStart(2, "0"),
    month: months[d.getMonth()],
    year: showYear ? String(d.getFullYear()) : null,
  };
}

function isToday(dateStr: string, today: Date): boolean {
  const d = parseYMD(dateStr);
  return (
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate()
  );
}

function isPast(dateStr: string, dueTime: string | null | undefined, now: Date): boolean {
  const d = parseYMD(dateStr);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (d.getTime() < todayStart.getTime()) return true;
  if (d.getTime() > todayStart.getTime()) return false;
  if (!dueTime) return false;
  const [h, m] = dueTime.split(":").map(Number);
  const due = new Date(d.getFullYear(), d.getMonth(), d.getDate(), h || 0, m || 0);
  return due.getTime() < now.getTime();
}

export function ScheduleTimeline<T extends DatedEntry>({
  entries,
  renderCard,
  renderTbdCard,
}: ScheduleTimelineProps<T>) {
  const dated = sortByDate(entries.filter((e) => !!e.due_date));
  const tbd = renderTbdCard ? entries.filter((e) => !e.due_date) : [];
  const today = new Date();
  const todayStr = todayISO();

  return (
    <div className="relative">
      <div
        className="absolute w-0.5"
        style={{
          left: 11,
          top: 12,
          bottom: tbd.length > 0 ? 0 : 12,
          backgroundColor: "var(--accent)",
        }}
      />

      <div className="flex flex-col">
        {dated.map((entry) => {
          const today_ = isToday(entry.due_date!, today);
          const past_ = isPast(entry.due_date!, entry.due_time, today);
          const { day, month, year } = formatDay(entry.due_date!, today);
          const urgency = urgencyColor(entry.due_date, todayStr);

          return (
            <div
              key={entry.id}
              className="grid items-start py-1.5"
              style={{ gridTemplateColumns: "24px 60px 1fr", columnGap: 0 }}
            >
              <div className="flex justify-center relative pt-2.5" style={{ zIndex: 1 }}>
                <div
                  className="rounded-full"
                  style={{
                    width: 14,
                    height: 14,
                    backgroundColor: entry.is_checked ? "#10b981" : "var(--border)",
                    boxShadow: entry.is_checked
                      ? "0 0 0 5px var(--bg), 0 0 0 6px #10b981"
                      : "0 0 0 5px var(--bg), 0 0 0 6px var(--accent)",
                  }}
                />
              </div>

              <div className="text-right pr-1">
                <div
                  className="font-bold leading-none"
                  style={{
                    color: urgency ?? (past_ && !today_ ? "var(--muted)" : "var(--text)"),
                    fontSize: 17,
                  }}
                >
                  {day}
                </div>
                <div
                  className="mt-0.5 font-semibold uppercase tracking-wider"
                  style={{ color: urgency ?? "var(--muted)", fontSize: 10 }}
                >
                  {month}
                </div>
                {year && (
                  <div
                    className="mt-0.5 font-semibold"
                    style={{ color: "#B91C1C", fontSize: 9 }}
                  >
                    {year}
                  </div>
                )}
              </div>

              {renderCard(entry, { isToday: today_, isPast: past_, urgency })}
            </div>
          );
        })}

        {tbd.length > 0 && renderTbdCard && (
          <>
            <div
              className="mt-2 mb-1 pl-[84px] text-[11px] font-semibold uppercase tracking-wider"
              style={{ color: "var(--muted)" }}
            >
              Nach Vereinbarung
            </div>
            {tbd.map((entry) => (
              <div
                key={entry.id}
                className="grid items-start py-1.5"
                style={{ gridTemplateColumns: "24px 60px 1fr", columnGap: 0 }}
              >
                <div className="flex justify-center relative pt-2.5" style={{ zIndex: 1 }}>
                  <div
                    className="rounded-full"
                    style={{
                      width: 14,
                      height: 14,
                      backgroundColor: entry.is_checked ? "#10b981" : "var(--border)",
                      boxShadow: entry.is_checked
                        ? "0 0 0 5px var(--bg), 0 0 0 6px #10b981"
                        : "0 0 0 5px var(--bg), 0 0 0 6px var(--accent)",
                    }}
                  />
                </div>
                <div className="text-right pr-1">
                  <div
                    className="font-semibold uppercase tracking-wider leading-tight"
                    style={{ color: "var(--muted)", fontSize: 9 }}
                  >
                    offen
                  </div>
                </div>
                {renderTbdCard(entry)}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 1.2: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors. Falls Errors zu vorhandenen Files gehören, ignorieren (nicht Teil dieser Änderung).

- [ ] **Step 1.3: Manuelle Smoke-Verifikation überspringen**

Datei wird in Task 2 verwendet. Solange isolierte Komponente noch nicht verkabelt ist, keine UI-Wirkung.

- [ ] **Step 1.4: User-Commit (überspringen, nicht selbst committen)**

Nach kompletter Plan-Umsetzung wird der User entscheiden, ob/wie committet wird. Diesen Schritt skippen.

---

## Task 2: Workspace-Timeline auf shared Komponente umstellen

**Files:**
- Modify: `frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleTimeline.tsx`

Ziel: Workspace-Timeline ist nach diesem Task ein dünner Wrapper, der die shared Timeline mit `ScheduleEntryCard` als `renderCard` nutzt. TBD-Block bleibt erhalten via `renderTbdCard`.

- [ ] **Step 2.1: Datei komplett neu schreiben**

Kompletter neuer Inhalt von `frontend/src/app/workspaces/[uuid]/_components/studio/ScheduleTimeline.tsx`:

```tsx
import type { ScheduleEntry } from "../../_types";
import { ScheduleEntryCard } from "./ScheduleEntry";
import { ScheduleTimeline as SharedTimeline } from "@/components/schedule/ScheduleTimeline";

interface SourceLike { uuid: string; filename: string; }

export function ScheduleTimeline({
  entries,
  editMode,
  sources,
  sourceNumByUuid,
  onToggleChecked,
  onEdit,
  onDelete,
  onPillClick,
}: {
  entries: ScheduleEntry[];
  editMode: boolean;
  sources: SourceLike[];
  sourceNumByUuid: Map<string, number>;
  onToggleChecked: (id: number, checked: boolean) => void;
  onEdit: (entry: ScheduleEntry) => void;
  onDelete: (id: number) => void;
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}) {
  const renderCard = (entry: ScheduleEntry, ctx: { isToday: boolean; isPast: boolean; urgency: string | null }) => (
    <ScheduleEntryCard
      entry={entry}
      isToday={ctx.isToday}
      isPast={ctx.isPast}
      urgency={ctx.urgency}
      editMode={editMode}
      sources={sources}
      sourceNumByUuid={sourceNumByUuid}
      onToggleChecked={(c) => onToggleChecked(entry.id, c)}
      onEdit={() => onEdit(entry)}
      onDelete={() => onDelete(entry.id)}
      onPillClick={onPillClick}
    />
  );

  const renderTbdCard = (entry: ScheduleEntry) => (
    <ScheduleEntryCard
      entry={entry}
      isToday={false}
      isPast={false}
      urgency={null}
      editMode={editMode}
      sources={sources}
      sourceNumByUuid={sourceNumByUuid}
      onToggleChecked={(c) => onToggleChecked(entry.id, c)}
      onEdit={() => onEdit(entry)}
      onDelete={() => onDelete(entry.id)}
      onPillClick={onPillClick}
    />
  );

  return (
    <SharedTimeline
      entries={entries}
      renderCard={renderCard}
      renderTbdCard={renderTbdCard}
    />
  );
}
```

- [ ] **Step 2.2: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 2.3: Workspace-Zeitplan im Browser prüfen (Regression-Check)**

Frontend läuft bereits auf `npm run dev`. Nicht killen. Hot-Reload greift automatisch.

Prüfe in einem Workspace mit Terminen:
- Timeline rendert mit Datum-Tile, vertikaler Linie, heutigem Dot mit grünem/grauen Glow.
- Edit-Mode aktivieren: Pencil/Trash-Buttons in jeder Card sichtbar und klickbar.
- Quellen-Chips öffnen den PDF-Viewer auf der korrekten Seite.
- Mindestens ein Eintrag ohne Datum: "Nach Vereinbarung"-Block am Ende erscheint.
- Heutiger Eintrag: Dot grün-gefüllt wenn erledigt, sonst heller Indikator.
- Erledigter Eintrag: Card wirkt opaker, durchgestrichener Title.

Falls eine dieser Checks fehlschlägt: Step 2.1 oder Task 1 anpassen. NICHT weitermachen.

- [ ] **Step 2.4: User-Commit (überspringen)**

---

## Task 3: ScheduleEntryCardGlobal Komponente bauen

**Files:**
- Create: `frontend/src/components/schedule/ScheduleEntryCardGlobal.tsx`

Ziel: Card mit identischer Optik zur Workspace-Card, aber mit Workspace-Chip statt Quellen-Chips, read-only Checkbox und ohne Edit-Mode.

- [ ] **Step 3.1: Datei anlegen**

Inhalt von `frontend/src/components/schedule/ScheduleEntryCardGlobal.tsx`:

```tsx
"use client";

import { Check, Clock, Folder, Users } from "@phosphor-icons/react";
import { cleanScheduleDescription } from "./utils";

export interface ScheduleListEntry {
  id: number;
  module_uuid: string;
  module_title: string;
  module_relation: "owned" | "enrolled";
  title: string;
  description?: string | null;
  due_date: string;
  due_time?: string | null;
  is_checked?: boolean;
}

interface ScheduleEntryCardGlobalProps {
  entry: ScheduleListEntry;
  isToday: boolean;
  isPast: boolean;
  urgency: string | null;
  onClick: () => void;
}

export function ScheduleEntryCardGlobal({
  entry,
  isPast,
  urgency,
  onClick,
}: ScheduleEntryCardGlobalProps) {
  const baseStyle: React.CSSProperties = {
    border: "1px solid var(--border)",
    backgroundColor: entry.is_checked ? "#f0fdf4" : "var(--bg)",
    opacity: isPast ? 0.55 : entry.is_checked ? 0.7 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
    cursor: "pointer",
  };

  const isOwned = entry.module_relation === "owned";
  const RelIcon = isOwned ? Folder : Users;
  const description = cleanScheduleDescription(entry.description, entry.due_time);

  return (
    <div
      style={baseStyle}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onClick();
        }
      }}
      className="hover:opacity-80 transition-opacity"
    >
      <div className="flex items-start gap-2.5">
        <div
          aria-hidden="true"
          className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center mt-0.5"
          style={{
            border: entry.is_checked ? "2px solid #10b981" : "2px solid var(--border)",
            backgroundColor: entry.is_checked ? "#10b981" : "#fff",
            color: "#fff",
          }}
        >
          {entry.is_checked && <Check size={11} weight="bold" />}
        </div>

        <div className="flex-1 min-w-0">
          <div
            className="font-semibold leading-tight break-words"
            style={{
              color: entry.is_checked ? "#166534" : "var(--text)",
              textDecoration: entry.is_checked ? "line-through" : "none",
              fontSize: 14,
            }}
          >
            {entry.title}
          </div>

          {(entry.due_time || description) && (
            <div
              className="mt-1 text-[11.5px] flex items-center gap-1.5 flex-wrap"
              style={{ color: "var(--muted)" }}
            >
              {entry.due_time && (
                <span
                  className="inline-flex items-center gap-1"
                  style={urgency ? { color: urgency } : undefined}
                >
                  <Clock size={10} weight="bold" />
                  {entry.due_time}
                </span>
              )}
              {entry.due_time && description && <span>·</span>}
              {description && <span className="break-words">{description}</span>}
            </div>
          )}

          <div
            className="mt-2 pt-2"
            style={{ borderTop: "1px dashed var(--border)" }}
          >
            <span
              className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full"
              style={{
                backgroundColor: isOwned ? "rgba(var(--kb-rgb),0.12)" : "transparent",
                border: isOwned ? "none" : "1px solid var(--border)",
                color: isOwned ? "var(--kb)" : "var(--muted)",
              }}
              title={isOwned ? "Eigener Arbeitsraum" : "Geteilter Arbeitsraum"}
            >
              <RelIcon size={10} weight="bold" />
              <span className="truncate" style={{ maxWidth: 240 }}>
                {entry.module_title}
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3.2: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 3.3: User-Commit (überspringen)**

---

## Task 4: /schedule auf neue Timeline + Card umstellen

**Files:**
- Modify: `frontend/src/app/schedule/page.tsx`

Ziel: List-Loop ersetzen durch shared Timeline mit `ScheduleEntryCardGlobal`. Verhalten (Toggle, Pagination, Empty-State) bleibt gleich. Outer-Container-Border entfällt, weil die Timeline ihr eigenes Layout liefert.

- [ ] **Step 4.1: Imports und Render-Block ändern**

In `frontend/src/app/schedule/page.tsx` folgende Änderungen vornehmen.

Ersetze den Import:

```tsx
import { ScheduleListItem, type ScheduleListEntry } from "@/components/schedule/ScheduleListItem";
```

durch:

```tsx
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";
```

Ersetze den `entries.length > 0`-Block (aktuell `<div className="rounded-2xl overflow-x-auto" ...><ul>...{entries.map(...)}...</ul></div>`) durch:

```tsx
{entries.length > 0 && (
  <>
    <ScheduleTimeline
      entries={entries}
      renderCard={(entry, ctx) => (
        <ScheduleEntryCardGlobal
          entry={entry}
          isToday={ctx.isToday}
          isPast={ctx.isPast}
          urgency={ctx.urgency}
          onClick={() => router.push(`/workspaces/${entry.module_uuid}?tab=schedule`)}
        />
      )}
    />

    <div ref={sentinelRef} aria-hidden="true" />

    {loadingMore && (
      <div className="flex justify-center py-4">
        <Spinner size="sm" />
      </div>
    )}

    {!hasMore && entries.length >= PAGE_SIZE && (
      <p className="text-center text-xs py-4" style={{ color: "var(--muted)" }}>
        Alle Termine geladen
      </p>
    )}
  </>
)}
```

Der `outer`-Container mit `rounded-2xl border` entfällt komplett, weil die Timeline ihr eigenes Layout liefert. Ein zusätzlicher Border würde die Datum-Tile und vertikale Linie abschneiden.

- [ ] **Step 4.2: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 4.3: Browser-Verifikation `/schedule`**

Im laufenden Frontend (Port 3000) `/schedule` aufrufen.

Prüfe:
- Timeline rendert mit Datum-Tile, vertikaler Linie, Today-Dot wenn passend.
- Workspace-Chip ist sichtbar in jeder Card (Folder-Icon bei eigenen Modulen, Users-Icon bei geteilten).
- Klick auf eine Card öffnet `/workspaces/<uuid>?tab=schedule` (selber Tab).
- Tastatur-Navigation: Tab fokussiert die Card, Enter/Space löst Click aus.
- Toggle "Erledigte ausblenden" oben rechts wirkt (Liste leer/befüllt sich).
- Beim Scrollen werden weitere Seiten nachgeladen (Spinner erscheint kurz).
- Erledigte Einträge: grüner Check-Indikator, durchgestrichener Title, opakere Card.
- Heutiger Eintrag: Time-Subline in Urgency-Farbe (rot/orange wenn knapp).
- Empty-State (kein Eintrag): Text "Keine Termine vorhanden" mit großem Kalender-Icon.

Falls eine dieser Checks fehlschlägt: Task 4 oder vorherige Tasks anpassen.

- [ ] **Step 4.4: User-Commit (überspringen)**

---

## Task 5: Widget auf neue Timeline + Card umstellen

**Files:**
- Modify: `frontend/src/app/workspaces/_components/UpcomingDeadlinesWidget.tsx`

Ziel: List-Loop des Widgets ersetzen durch dieselbe Timeline. Header bleibt. Container-Padding leicht anpassen, damit die vertikale Linie nicht am Border klebt.

- [ ] **Step 5.1: Imports und Render-Block ändern**

In `frontend/src/app/workspaces/_components/UpcomingDeadlinesWidget.tsx`:

Ersetze den Import:

```tsx
import { ScheduleListItem, type ScheduleListEntry } from "@/components/schedule/ScheduleListItem";
```

durch:

```tsx
import { ScheduleTimeline } from "@/components/schedule/ScheduleTimeline";
import { ScheduleEntryCardGlobal, type ScheduleListEntry } from "@/components/schedule/ScheduleEntryCardGlobal";
```

Ersetze den `<div className="overflow-x-auto"><ul ...>{entries.map(...)}</ul></div>`-Block durch:

```tsx
<div className="px-3 py-2">
  <ScheduleTimeline
    entries={entries}
    renderCard={(entry, ctx) => (
      <ScheduleEntryCardGlobal
        entry={entry}
        isToday={ctx.isToday}
        isPast={ctx.isPast}
        urgency={ctx.urgency}
        onClick={() => router.push(`/workspaces/${entry.module_uuid}?tab=schedule`)}
      />
    )}
  />
</div>
```

Hinweis: `px-3 py-2` ist Padding rund um die Timeline, damit Datum-Tile und vertikale Linie nicht direkt am Widget-Border kleben. Falls visuell zu eng oder zu locker, in Step 5.3 anpassen.

- [ ] **Step 5.2: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 5.3: Browser-Verifikation Widget auf `/workspaces`**

Im laufenden Frontend `/workspaces` aufrufen (Hauptseite mit Modul-Übersicht).

Prüfe:
- Widget "Nächste Termine" oben rendert drei Termine im Timeline-Stil.
- Datum-Tile + vertikale Linie sichtbar, nicht abgeschnitten.
- Wenn das Padding `px-3 py-2` zu eng wirkt: auf `px-4 py-3` erhöhen. Wenn zu locker: auf `px-2 py-1` reduzieren. Optisch sauberen Wert wählen.
- Klick auf Card → springt zum jeweiligen Workspace.
- Button "Alle anzeigen" oben rechts → springt zu `/schedule`.
- Header behält seine Optik (Kalender-Icon, Titel "Nächste Termine", Border-Bottom).
- Keine Termine vorhanden: Widget rendert nicht (`entries.length === 0` → return null bleibt unverändert).

- [ ] **Step 5.4: User-Commit (überspringen)**

---

## Task 6: ScheduleListItem löschen

**Files:**
- Delete: `frontend/src/components/schedule/ScheduleListItem.tsx`

Ziel: Komponente ist nach Tasks 4 und 5 nirgends mehr referenziert. Datei wird gelöscht.

- [ ] **Step 6.1: Verifizieren, dass keine Referenzen mehr existieren**

Run: `grep -rn "ScheduleListItem" frontend/src/ 2>/dev/null`
Expected: keine Treffer (oder nur in der Datei selbst, falls `grep` sie noch zeigt).

Falls Treffer in anderen Dateien: NICHT löschen, stattdessen Treffer aufräumen.

- [ ] **Step 6.2: Datei löschen**

Run: `rm frontend/src/components/schedule/ScheduleListItem.tsx`

- [ ] **Step 6.3: TypeScript-Check**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 6.4: Browser-Verifikation**

Erneut `/schedule` und `/workspaces` aufrufen, sicherstellen dass nichts kaputtgegangen ist (Hot-Reload sollte das schon erledigt haben).

- [ ] **Step 6.5: User-Commit (überspringen)**

---

## Task 7: Final Sweep

Letzte Verifikation, dass alle Spec-Punkte erfüllt sind.

- [ ] **Step 7.1: Spec-Coverage-Check**

Spec-Datei [docs/superpowers/specs/2026-04-27-global-schedule-timeline-ui-design.md](docs/superpowers/specs/2026-04-27-global-schedule-timeline-ui-design.md) Punkt für Punkt durchgehen:

- Layout Datum-Tile + vertikale Linie + Card auf `/schedule`: in Task 4 erledigt.
- Workspace-Chip statt Quellen-Chips: in Task 3 erledigt.
- Read-only Checkbox: in Task 3 erledigt (kein onClick, kein Button-Role).
- Kein Edit-Mode global: in Task 3 erledigt (keine Pencil/Trash).
- Ganze Card klickbar zum Workspace: in Task 3 + 4 + 5 erledigt.
- "Erledigte ausblenden"-Toggle bleibt: in Task 4 unverändert gelassen.
- Infinite Scroll bleibt: in Task 4 unverändert gelassen.
- Widget rendert drei Termine im Timeline-Stil: in Task 5 erledigt.
- Workspace-Zeitplan keine Regression: in Task 2 verifiziert.
- `ScheduleListItem` gelöscht: in Task 6 erledigt.

- [ ] **Step 7.2: Globaler TypeScript-Sweep**

Run: `cd frontend && npx tsc --noEmit`
Expected: keine neuen Errors.

- [ ] **Step 7.3: User informieren**

Bestätigen, dass die Umstellung lokal lauffähig ist. User entscheidet, ob/wann committet wird (alle Schritte folgen der Regel "kein Auto-Commit").
