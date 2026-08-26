"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import IconButton from "@/components/ui/IconButton";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import ScheduleMonthRow from "./ScheduleMonthRow";
import ScheduleEntryModal from "./ScheduleEntryModal";
import ScheduleBars, { barsSpace, BAR_TOP, BAR_GAP } from "./ScheduleBars";
import { laneCount, weekSegments, type RangeEntry } from "./_ranges";
import { useHiddenIds } from "./_hidden";
import { todayISO } from "./utils";

/** Kleine feste Palette, damit mehrere Workspaces im Raster unterscheidbar bleiben. */
const WS_COLORS = ["var(--kb)", "#B45309", "#6D28D9", "#0F766E", "#9D174D", "#1D4ED8"];

/** Eigene Termine tragen alle dasselbe Marken-Blau. Fest statt var(--kb60), weil
 *  weisse Schrift darauf in beiden Modi lesbar bleiben muss. */
const PRIV_COLOR = "#4F7A91";

/** Mehr Einträge pro Tag werden zu "+N weitere", sonst sprengt ein Tag die Zeilenhöhe. */
const MAX_CHIPS = 2;

/** Hoechstens so viele Balken uebereinander, der Rest zaehlt in "+N weitere" mit. */
const MAX_LANES = 2;

/** Heute traegt nur vier Winkel, kein voller Rahmen und keine Fuellung. */
const ECK_STRICH = "2px solid var(--kb)";
const ECKEN: React.CSSProperties[] = [
  { top: 0, left: 0, borderTop: ECK_STRICH, borderLeft: ECK_STRICH },
  { top: 0, right: 0, borderTop: ECK_STRICH, borderRight: ECK_STRICH },
  { bottom: 0, left: 0, borderBottom: ECK_STRICH, borderLeft: ECK_STRICH },
  { bottom: 0, right: 0, borderBottom: ECK_STRICH, borderRight: ECK_STRICH },
];

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function ymd(y: number, m: number, d: number): string {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** Wie ymd, aber der Tag darf ueber den Monat hinauslaufen, Date rechnet das um. */
function ymdShift(y: number, m: number, dayOffset: number): string {
  const dt = new Date(y, m, dayOffset);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** Der Kalender zeigt immer alles. Ein Monat mit Löchern wäre kein Kalender. */
async function fetchAll(): Promise<ScheduleListEntry[] | null> {
  const params = new URLSearchParams({
    include_past_open: "true",
    include_checked: "true",
  });
  try {
    const r = await fetch(`/api/ai-assistant/schedule/upcoming?${params.toString()}`, {
      credentials: "include",
    });
    if (!r.ok) return null;
    const data = await r.json();
    return data.entries || [];
  } catch {
    return null;
  }
}

async function putChecked(
  workspaceUuid: string | null,
  entryId: number,
  checked: boolean,
): Promise<boolean> {
  // Ein eigener Termin hat keinen Workspace im Pfad.
  const url = workspaceUuid
    ? `/api/ai-assistant/workspaces/${workspaceUuid}/schedule/entries/${entryId}`
    : `/api/ai-assistant/schedule/entries/${entryId}`;
  try {
    const r = await fetch(
      url,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ is_checked: checked }),
      },
    );
    return r.ok;
  } catch {
    return false;
  }
}

/**
 * Monatsraster über alle Workspaces. Ein Klick auf einen Tag öffnet dessen
 * Termine unter dem Raster, weil in einer Zelle nur zwei Titel Platz haben.
 */
export default function ScheduleMonth() {
  const t = useTranslations("schedule");
  const locale = useLocale();
  const tag = locale === "en" ? "en-US" : "de-DE";

  const [entries, setEntries] = useState<ScheduleListEntry[] | null>(null);
  const [error, setError] = useState(false);
  // Der Kalender startet immer im laufenden Monat, damit heute im Bild ist.
  const [cursor, setCursor] = useState(() => {
    const d = new Date();
    return { y: d.getFullYear(), m: d.getMonth() };
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  // Vorbelegtes Datum fuer einen neuen Termin, leer beim Knopf in der Leiste.
  const [modalDate, setModalDate] = useState("");
  // Merkt den letzten Klick, damit ein Doppelklick oder Doppeltipp erkannt wird.
  const letzterKlick = useRef<{ iso: string; zeit: number } | null>(null);
  const [editing, setEditing] = useState<ScheduleListEntry | null>(null);
  const { hidden, toggleHidden } = useHiddenIds();

  useEffect(() => {
    let cancelled = false;
    fetchAll().then((items) => {
      if (cancelled) return;
      if (items === null) {
        setError(true);
        return;
      }
      setEntries(items);
    });
    return () => { cancelled = true; };
  }, []);

  const today = todayISO();

  const step = useCallback((dir: number) => {
    setSelected(null);
    setCursor((c) => {
      const m = c.m + dir;
      if (m < 0) return { y: c.y - 1, m: 11 };
      if (m > 11) return { y: c.y + 1, m: 0 };
      return { y: c.y, m };
    });
  }, []);

  const reload = useCallback(() => {
    setEntries(null);
    fetchAll().then((items) => { if (items !== null) setEntries(items); });
  }, []);

  const handleDelete = useCallback(async (entry: ScheduleListEntry) => {
    if (!window.confirm(t("month.deleteConfirm", { title: entry.title }))) return;
    const r = await fetch(`/api/ai-assistant/schedule/entries/${entry.id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (r.ok) setEntries((prev) => prev?.filter((e) => e.id !== entry.id) ?? prev);
  }, [t]);

  /** Einmal waehlt den Tag, zweimal kurz hintereinander legt dort einen Termin an. */
  const handleDayClick = useCallback((iso: string) => {
    const jetzt = Date.now();
    const vorher = letzterKlick.current;
    if (vorher && vorher.iso === iso && jetzt - vorher.zeit < 400) {
      letzterKlick.current = null;
      setSelected(null);
      setModalDate(iso);
      setModalOpen(true);
      return;
    }
    letzterKlick.current = { iso, zeit: jetzt };
    setSelected((vorheriges) => (vorheriges === iso ? null : iso));
  }, []);

  const jumpToToday = useCallback(() => {
    const d = new Date();
    setSelected(null);
    setCursor({ y: d.getFullYear(), m: d.getMonth() });
  }, []);

  const handleToggleChecked = useCallback(async (entry: ScheduleListEntry, checked: boolean) => {
    setEntries((prev) => prev?.map((e) => (e.id === entry.id ? { ...e, is_checked: checked } : e)) ?? prev);
    const ok = await putChecked(entry.workspace_uuid, entry.id, checked);
    if (!ok) {
      setEntries((prev) => prev?.map((e) => (e.id === entry.id ? { ...e, is_checked: !checked } : e)) ?? prev);
    }
    // Erledigtes bleibt stehen und wird nur durchgestrichen, der Kalender zeigt alles.
  }, []);

  // Farbe nach Reihenfolge statt nach Hash: so bekommen die ersten sechs
  // Workspaces garantiert verschiedene Farben, und die Zuordnung bleibt stabil.
  const wsColors = useMemo(() => {
    const ids = [...new Set((entries ?? []).map((e) => e.workspace_uuid))]
      .filter((id): id is string => id !== null)
      .sort();
    return new Map(ids.map((id, i) => [id, WS_COLORS[i % WS_COLORS.length]]));
  }, [entries]);

  const colorFor = useCallback(
    (uuid: string | null) => (uuid === null ? PRIV_COLOR : wsColors.get(uuid) ?? WS_COLORS[0]),
    [wsColors],
  );

  const weekdays = useMemo(() => {
    // 2024-01-01 war ein Montag, das gibt die Reihenfolge Mo bis So.
    const fmt = new Intl.DateTimeFormat(tag, { weekday: "short" });
    return Array.from({ length: 7 }, (_, i) => fmt.format(new Date(2024, 0, 1 + i)));
  }, [tag]);

  if (error) {
    return <p className="text-center text-sm py-12" style={{ color: "var(--error-strong)" }}>{t("loadError")}</p>;
  }
  if (!entries) {
    return <div className="flex justify-center py-16"><Spinner size="md" /></div>;
  }

  const { y, m } = cursor;
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  const daysInPrev = new Date(y, m, 0).getDate();
  const startCol = (new Date(y, m, 1).getDay() + 6) % 7; // Montag = 0
  const trailing = (7 - ((startCol + daysInMonth) % 7)) % 7;
  const weeks = (startCol + daysInMonth + trailing) / 7;

  // Ein Eintrag mit date_precision "month" nennt keinen Tag und passt daher in
  // keine Zelle. Er steht unter dem Raster.
  const byDay = new Map<string, ScheduleListEntry[]>();
  const noDay: ScheduleListEntry[] = [];
  const monthPrefix = `${y}-${String(m + 1).padStart(2, "0")}`;
  const monthStart = `${monthPrefix}-01`;
  const monthEnd = `${monthPrefix}-${String(daysInMonth).padStart(2, "0")}`;

  // Zeitraeume zeichnet der Balken, sie duerfen nicht zusaetzlich als Tages-Kachel auftauchen.
  const isRange = (e: ScheduleListEntry) => !!e.end_date && e.end_date !== e.due_date;
  const monthRanges = entries.filter(
    (e) => isRange(e) && e.due_date <= monthEnd && (e.end_date as string) >= monthStart,
  );

  for (const e of entries) {
    if (!e.due_date || !e.due_date.startsWith(monthPrefix)) continue;
    if (isRange(e)) continue;
    if (e.date_precision === "month") {
      noDay.push(e);
      continue;
    }
    const list = byDay.get(e.due_date);
    if (list) list.push(e);
    else byDay.set(e.due_date, [e]);
  }

  const usedWorkspaces = new Map<string, { title: string; color: string }>();
  let hatPrivate = false;
  for (const e of [...byDay.values()].flat().concat(noDay, monthRanges)) {
    // Eigene Termine tragen keinen Workspace-Namen, sie stehen als eine Zeile.
    if (e.workspace_uuid === null) {
      hatPrivate = true;
      continue;
    }
    if (!usedWorkspaces.has(e.workspace_uuid)) {
      usedWorkspaces.set(e.workspace_uuid, {
        title: e.module_title ?? "",
        color: colorFor(e.workspace_uuid),
      });
    }
  }
  if (hatPrivate) {
    usedWorkspaces.set("__privat__", { title: t("month.personal"), color: PRIV_COLOR });
  }

  // Nur das Raster laesst Ausgeblendetes weg, die Liste rechts zeigt weiter alles.
  const imRaster = (e: ScheduleListEntry) => !hidden.has(e.id);
  const noDayGrid = noDay.filter(imRaster);

  // Ein Zeitraum hat ein Ende, alles andere ist ein einzelner Tag.
  const ranges: RangeEntry[] = monthRanges
    .filter(imRaster)
    .map((e) => ({
      id: e.id,
      title: e.title,
      due_date: e.due_date,
      end_date: e.end_date as string,
      color: colorFor(e.workspace_uuid),
      is_checked: !!e.is_checked,
    }));

  const monthLabel = new Intl.DateTimeFormat(tag, { month: "long", year: "numeric" })
    .format(new Date(y, m, 1));
  // Ein Zeitraum steht in keiner Tageszelle, deckt den Tag aber trotzdem ab.
  // Ohne ihn waere ein Tag mitten in der Klausurphase nicht anklickbar.
  const rangesOn = (iso: string) =>
    monthRanges.filter((r) => r.due_date <= iso && (r.end_date as string) >= iso);
  const entriesOn = (iso: string) => (byDay.get(iso) ?? []).concat(rangesOn(iso));
  const selectedEntries = selected ? entriesOn(selected) : [];
  const isEmptyMonth = byDay.size === 0 && noDay.length === 0;

  // Nur auf breiten Schirmen: die Spalte rechts zeigt den ganzen Monat, und
  // sobald ein Tag gewählt ist, nur noch diesen.
  const monthEntries = [...byDay.entries()]
    .flatMap(([, list]) => list)
    .concat(monthRanges)
    .sort((a, b) => a.due_date.localeCompare(b.due_date) || a.id - b.id)
    .concat(noDay);
  const sideEntries = selected ? selectedEntries : monthEntries;
  const sideHeading = selected
    ? new Intl.DateTimeFormat(tag, { day: "numeric", month: "long", year: "numeric" })
        .format(parseYMD(selected))
    : t("month.inMonth", { month: monthLabel });

  const rows = (items: ScheduleListEntry[]) => (
    <div className="flex flex-col divide-y divide-border-soft">
      {items.map((entry) => (
        <ScheduleMonthRow
          key={entry.id}
          entry={entry}
          color={colorFor(entry.workspace_uuid)}
          today={today}
          onToggleChecked={(checked) => handleToggleChecked(entry, checked)}
          hidden={hidden.has(entry.id)}
          onToggleHidden={() => toggleHidden(entry.id)}
          onEdit={entry.workspace_uuid === null ? () => setEditing(entry) : undefined}
          onDelete={entry.workspace_uuid === null ? () => handleDelete(entry) : undefined}
        />
      ))}
    </div>
  );

  return (
    <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_340px] xl:gap-5 xl:items-start">
    {/* Auf breiten Schirmen wächst das Raster in die Höhe, sonst steht der halbe
        Bildschirm leer. Darunter bestimmt der Inhalt die Höhe wie bisher. */}
    <div className="min-w-0 xl:flex xl:flex-col xl:min-h-[68vh]">
      <div className="flex items-center gap-2.5 mb-3 flex-wrap">
        <span className="text-base font-bold" style={{ color: "var(--foreground)" }}>{monthLabel}</span>
        <IconButton onClick={() => step(-1)} aria-label={t("month.prev")}>
          <CaretLeft size={13} weight="bold" />
        </IconButton>
        <IconButton onClick={() => step(1)} aria-label={t("month.next")}>
          <CaretRight size={13} weight="bold" />
        </IconButton>
        <button
          type="button"
          onClick={jumpToToday}
          className="text-xs font-medium rounded-full px-3 py-1 text-[var(--foreground-soft)] btn-ghost hover:text-[var(--kb)] dark:hover:text-white"
          style={{ border: "1px solid var(--border)" }}
        >
          {t("month.today")}
        </button>
        {/* Gleicher Knopf wie "+ Modul" auf der Startseite. */}
        <button
          type="button"
          onClick={() => { setModalDate(""); setModalOpen(true); }}
          aria-label={t("month.addEntry")}
          className="ml-auto whitespace-nowrap rounded-lg text-sm font-medium btn-primary w-9 h-9 flex items-center justify-center text-lg md:w-auto md:h-auto md:px-4 md:py-2 md:text-sm"
        >
          <span className="md:hidden">+</span>
          <span className="hidden md:inline">+ {t("month.addEntryShort")}</span>
        </button>
      </div>

      {/* Auf dem Handy zieht das Raster ueber den Seitenrand hinaus, sonst
          bleiben von 390 px nur 358 fuer sieben Spalten. */}
      <div className="-mx-4 sm:mx-0 grid grid-cols-7 gap-1 mb-1">
        {weekdays.map((w) => (
          <div
            key={w}
            className="text-2xs font-bold text-center pb-1 uppercase tracking-wide"
            style={{ color: "var(--muted)" }}
          >
            {w}
          </div>
        ))}
      </div>

      {/* Jede Woche ist ein eigener Block, damit die Balken darin liegen koennen. */}
      <div className="-mx-4 sm:mx-0 flex flex-col gap-1 xl:flex-1">
      {Array.from({ length: weeks }, (_, w) => {
        const weekStart = ymdShift(y, m, 1 - startCol + w * 7);
        const segmente = weekSegments(ranges, weekStart);
        // Was ueber den Deckel hinausgeht, wird nicht gezeichnet, sondern gezaehlt.
        const sichtbareBalken = segmente.filter((s) => s.lane < MAX_LANES);
        const versteckteIds = new Set(
          segmente.filter((s) => s.lane >= MAX_LANES).map((s) => s.entry.id),
        );
        // Platz pro Tag statt pro Woche: ein Tag, den kein Balken kreuzt, braucht
        // keinen. Sonst steht in leeren Zellen ein Loch von zwei Balkenhoehen.
        const spurProTag = new Map<number, number>();
        for (const seg of sichtbareBalken) {
          for (let i = seg.col1 - 1; i <= seg.col2 - 2; i++) {
            spurProTag.set(i, Math.max(spurProTag.get(i) ?? -1, seg.lane));
          }
        }
        const wochenPlatz = barsSpace(laneCount(sichtbareBalken));
        return (
          <div
            key={weekStart}
            className="relative grid grid-cols-7 xl:flex-1"
            // Viele Balken brauchen echte Hoehe, sonst rutscht die Kachel darunter aus der Zelle.
            style={{
              borderTop: w === 0 ? undefined : "1px solid var(--border-soft)",
              ...(wochenPlatz ? { minHeight: BAR_TOP + wochenPlatz + BAR_GAP } : {}),
            }}
          >
        {Array.from({ length: 7 }, (_, i) => {
          const day = w * 7 + i - startCol + 1;
          if (day < 1 || day > daysInMonth) {
            return (
              <div
                key={`out-${w}-${i}`}
                aria-hidden="true"
                className="min-h-13 md:min-h-19 px-1.5 py-1 text-2xs font-semibold"
                style={{
                  borderLeft: i === 0 ? undefined : "1px solid var(--border-soft)",
                  color: "var(--border)",
                }}
              >
                {day < 1 ? daysInPrev + day : day - daysInMonth}
              </div>
            );
          }
          const iso = ymd(y, m, day);
          const items = (byDay.get(iso) ?? []).filter(imRaster);
          const spannen = rangesOn(iso);
          // Ein Zeitraum ohne Balken ist fuer diesen Tag genauso ein versteckter Eintrag
          // wie eine weggelassene Kachel, beide zaehlen in denselben Rest.
          const versteckteSpannen = spannen.filter((r) => versteckteIds.has(r.id)).length;
          const spur = spurProTag.get(i);
          const platz = spur === undefined ? 0 : barsSpace(spur + 1);
          const gesamt = items.length + versteckteSpannen;
          const isToday = iso === today;
          const isSelected = iso === selected;
          const chips = gesamt > MAX_CHIPS + 1 ? items.slice(0, MAX_CHIPS) : items;
          const restChips = gesamt - chips.length;

          return (
            <button
              key={iso}
              type="button"
              onClick={() => handleDayClick(iso)}
              aria-pressed={isSelected}
              className="relative min-h-13 md:min-h-19 px-1.5 py-1 flex flex-col text-left transition-colors cursor-pointer hover:bg-[var(--surface-dim)] hover:outline-2 hover:outline-[var(--kb)]"
              style={{
                borderLeft: i === 0 ? undefined : "1px solid var(--border-soft)",
                // Der gewaehlte Tag bekommt die volle Kontur, heute nur die Winkel darunter.
                outline: isSelected ? "2px solid var(--kb)" : undefined,
                outlineOffset: -2,
                backgroundColor: "var(--background)",
              }}
            >
              {isToday && ECKEN.map((eck, k) => (
                <span key={k} aria-hidden="true" className="absolute pointer-events-none" style={{ ...eck, width: 9, height: 9 }} />
              ))}
              <span
                className="text-2xs font-semibold"
                // Feste Hoehe, sonst rundet die Zeilenbox und der Abstand darunter
                // stimmt um ein Pixel nicht mit dem zwischen den Balken ueberein.
                style={{ height: 17, color: isToday ? "var(--kb)" : "var(--foreground-soft)" }}
              >
                {day}
              </span>

              {/* Der Platz fuer die Balken sitzt unter der Zahl, nie darueber. */}
              {platz > 0 && <span aria-hidden="true" style={{ height: platz }} />}

              {/* Ueberall dieselben Kacheln, in schmalen Zellen kuerzt truncate den Titel. */}
              <span className="flex flex-col gap-0.5 min-w-0">
                {chips.map((e) => (
                  <span
                    key={e.id}
                    title={e.title}
                    className="text-2xs font-semibold rounded px-1 py-px truncate"
                    style={{
                      backgroundColor: colorFor(e.workspace_uuid),
                      color: "#fff",
                      opacity: e.is_checked ? 0.45 : 1,
                      textDecoration: e.is_checked ? "line-through" : undefined,
                    }}
                  >
                    {e.title}
                  </span>
                ))}
                {restChips > 0 && (
                  <span
                    className="text-2xs font-bold px-1"
                    style={{ color: "var(--kb)" }}
                  >
                    {/* Das Wort "weitere" passt erst ab Tablet neben die Zahl. */}
                    <span className="md:hidden">+{restChips}</span>
                    <span className="hidden md:inline">{t("month.more", { count: restChips })}</span>
                  </span>
                )}
              </span>
            </button>
          );
        })}
            <ScheduleBars segments={sichtbareBalken} />
          </div>
        );
      })}
      </div>

      {/* Ab xl stehen diese Termine in der rechten Spalte, hier wären sie doppelt. */}
      {noDayGrid.length > 0 && (
        <div
          className="mt-3 rounded-lg px-3 py-2.5 flex items-center gap-2.5 flex-wrap xl:hidden"
          style={{ border: "1px dashed var(--border)", backgroundColor: "var(--surface)" }}
        >
          <span className="text-2xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            {t("month.noDay")}
          </span>
          {noDayGrid.map((e) => (
            <span
              key={e.id}
              className="inline-flex items-center gap-1.5 text-xs font-semibold rounded-full px-2.5 py-1"
              style={{ backgroundColor: "var(--background)", border: "1px solid var(--border-soft)" }}
            >
              <span
                className="rounded-sm"
                style={{ width: 8, height: 8, backgroundColor: colorFor(e.workspace_uuid) }}
              />
              {e.title}
            </span>
          ))}
        </div>
      )}

      {/* Ab xl steht der Hinweis in der rechten Spalte, hier wäre er doppelt. */}
      {isEmptyMonth && (
        <p className="text-center text-xs py-6 xl:hidden" style={{ color: "var(--muted)" }}>
          {t("month.empty")}
        </p>
      )}

      {usedWorkspaces.size > 0 && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
          {[...usedWorkspaces.values()].map((w) => (
            <span
              key={w.title}
              className="inline-flex items-center gap-1.5 text-xs"
              style={{ color: "var(--foreground-soft)" }}
            >
              <span className="rounded-sm" style={{ width: 9, height: 9, backgroundColor: w.color }} />
              {w.title}
            </span>
          ))}
        </div>
      )}

      {/* Schmale Schirme behalten die Tagesliste unter dem Raster. */}
      {selected && selectedEntries.length > 0 && (
        <div className="mt-4 pt-3.5 xl:hidden" style={{ borderTop: "1px solid var(--border-soft)" }}>
          <p className="text-2xs font-bold uppercase tracking-wide mb-2.5" style={{ color: "var(--muted)" }}>
            {new Intl.DateTimeFormat(tag, { day: "numeric", month: "long", year: "numeric" })
              .format(parseYMD(selected))}
          </p>
          {rows(selectedEntries)}
        </div>
      )}
    </div>

    <aside
      className="hidden xl:block xl:pl-5"
      style={{ borderLeft: "1px solid var(--border-soft)" }}
    >
      <p className="text-2xs font-bold uppercase tracking-wide mb-3" style={{ color: "var(--muted)" }}>
        {sideHeading}
      </p>
      {sideEntries.length > 0 ? (
        rows(sideEntries)
      ) : (
        <p className="text-xs py-4" style={{ color: "var(--muted)" }}>{t("month.empty")}</p>
      )}
    </aside>

    {(modalOpen || editing) && (
      <ScheduleEntryModal
        entry={editing}
        defaultDate={modalDate}
        onClose={() => { setModalOpen(false); setEditing(null); }}
        onSaved={() => { setModalOpen(false); setEditing(null); reload(); }}
      />
    )}
    </div>
  );
}
