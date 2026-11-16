"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import IconButton from "@/components/ui/IconButton";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import ScheduleMonthLegend from "./ScheduleMonthLegend";
import ScheduleMonthRow from "./ScheduleMonthRow";
import ScheduleMonthWeek from "./ScheduleMonthWeek";
import ScheduleEntryModal from "./ScheduleEntryModal";
import type { RangeEntry } from "./_ranges";
import { useHiddenGroups, useHiddenIds } from "./_hidden";
import { monthGrid, rangesOn } from "./_monthGrid";
import { dateLocaleTag, parseYMD, todayISO } from "./utils";
import { deleteEntry, fetchAllEntries, fetchColors, putChecked, putColor, PRIVAT, type CalendarColors } from "./_api";

/** Until the colours arrive, every entry stands in the accent colour. */
const ERSATZ_FARBE = "var(--kb)";

const ISO_TAG = /^\d{4}-\d{2}-\d{2}$/;

/** Month grid across all courses, a click opens the day's appointments below. */
export default function ScheduleMonth({ initialDate }: { initialDate?: string }) {
  const t = useTranslations("schedule");
  const locale = useLocale();
  const tag = dateLocaleTag(locale);

  const [entries, setEntries] = useState<ScheduleListEntry[] | null>(null);
  const [farben, setFarben] = useState<CalendarColors | null>(null);
  const [error, setError] = useState(false);
  // The calendar starts in the current month so today is in view, a day from the
  // start page overrides that and opens its own month.
  const [cursor, setCursor] = useState(() => {
    const d = initialDate && ISO_TAG.test(initialDate) ? parseYMD(initialDate) : new Date();
    return { y: d.getFullYear(), m: d.getMonth() };
  });
  const [selected, setSelected] = useState<string | null>(
    initialDate && ISO_TAG.test(initialDate) ? initialDate : null,
  );
  const [modalOpen, setModalOpen] = useState(false);
  // Prefilled date for a new appointment, empty for the button in the bar.
  const [modalDate, setModalDate] = useState("");
  // Remembers the last click so a double click or double tap is recognised.
  const letzterKlick = useRef<{ iso: string; zeit: number } | null>(null);
  const [editing, setEditing] = useState<ScheduleListEntry | null>(null);
  const { hidden, toggleHidden } = useHiddenIds();
  const { hiddenGroups, toggleGroup } = useHiddenGroups();

  useEffect(() => {
    let cancelled = false;
    fetchAllEntries().then((items) => {
      if (cancelled) return;
      if (items === null) {
        setError(true);
        return;
      }
      setEntries(items);
    });
    fetchColors().then((c) => { if (!cancelled && c) setFarben(c); });
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
    // A failed reload shows the error, otherwise the spinner would never end.
    fetchAllEntries().then((items) => {
      if (items === null) setError(true);
      else setEntries(items);
    });
    // A first private appointment or a new workspace needs its own colour.
    fetchColors().then((c) => { if (c) setFarben(c); });
  }, []);

  const pickColor = useCallback(async (group: string, index: number) => {
    const c = await putColor(group, index);
    if (c) setFarben(c);
  }, []);

  const handleDelete = useCallback(async (entry: ScheduleListEntry) => {
    if (!window.confirm(t("month.deleteConfirm", { title: entry.title }))) return;
    if (await deleteEntry(entry.id)) setEntries((prev) => prev?.filter((e) => e.id !== entry.id) ?? prev);
  }, [t]);

  /** One click selects the day, two in quick succession create an appointment there. */
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
    // Done entries stay and are only struck through, the calendar shows everything.
  }, []);

  // The server hands out the colours, so two workspaces never share one.
  const colorFor = useCallback(
    (uuid: string | null) => farben?.colors[uuid ?? PRIVAT] ?? ERSATZ_FARBE,
    [farben],
  );

  const weekdays = useMemo(() => {
    // 2024-01-01 was a Monday, that gives the order Monday to Sunday.
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
  const grid = monthGrid(entries, y, m, hiddenGroups);
  const { byDay, noDay, monthRanges } = grid;
  const legend = grid.groups.map(({ key, title }) => ({
    key,
    title: title ?? t("month.personal"),
    color: colorFor(key === PRIVAT ? null : key),
  }));

  // Only the grid leaves hidden entries out, the list on the right still shows everything.
  const imRaster = (e: ScheduleListEntry) => !hidden.has(e.id);
  const noDayGrid = noDay.filter(imRaster);

  // A span has an end, everything else is a single day.
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
  const selectedEntries = selected ? (byDay.get(selected) ?? []).concat(rangesOn(monthRanges, selected)) : [];
  // A span alone fills the month too, the bar would otherwise stand above "no appointments".
  const isEmptyMonth = byDay.size === 0 && noDay.length === 0 && monthRanges.length === 0;

  // Only on wide screens, the column shows the month or the selected day.
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
    {/* On wide screens the grid grows in height, otherwise half the screen stays empty; below that the content sets the height. */}
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
        {/* Same button as "+ Workspace" on the start page. */}
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

      {/* On the phone the grid extends past the page margin, otherwise only 358 of 390 px remain for seven columns. */}
      <div className="-mx-4 sm:mx-0 grid grid-cols-7 gap-1 mb-1">
        {weekdays.map((w) => (
          <div
            key={`${y}-${m}-${w}`}
            className="text-2xs font-bold text-center pb-1 uppercase tracking-wide"
            style={{ color: "var(--muted)" }}
          >
            {w}
          </div>
        ))}
      </div>

      <div className="-mx-4 sm:mx-0 flex flex-col gap-1 xl:flex-1">
        {Array.from({ length: grid.weeks }, (_, w) => (
          <ScheduleMonthWeek
            key={`${y}-${m}-${w}`}
            y={y}
            m={m}
            week={w}
            grid={grid}
            bars={ranges}
            inGrid={imRaster}
            today={today}
            selected={selected}
            colorFor={colorFor}
            onDayClick={handleDayClick}
          />
        ))}
      </div>

      {/* From xl these entries sit in the right column, here they would be duplicates. */}
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

      {/* From xl the hint sits in the right column, here it would be a duplicate. */}
      {isEmptyMonth && (
        <p className="text-center text-xs py-6 xl:hidden" style={{ color: "var(--muted)" }}>
          {t("month.empty")}
        </p>
      )}

      <ScheduleMonthLegend
        groups={legend}
        palette={farben?.palette}
        hiddenGroups={hiddenGroups}
        onPickColor={pickColor}
        onToggleGroup={toggleGroup}
      />

      {/* Narrow screens keep the day list below the grid. */}
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
      className="hidden xl:flex xl:flex-col xl:pl-5"
      style={{ borderLeft: "1px solid var(--border-soft)" }}
    >
      <p className="text-2xs font-bold uppercase tracking-wide mb-3 shrink-0" style={{ color: "var(--muted)" }}>
        {sideHeading}
      </p>
      {/* With many entries the list scrolls instead of stretching the page beyond the grid on the left. */}
      <div className="xl:max-h-[68vh] overflow-y-auto">
        {sideEntries.length > 0 ? (
          rows(sideEntries)
        ) : (
          <p className="text-xs py-4" style={{ color: "var(--muted)" }}>
            {t(selected ? "month.emptyDay" : "month.empty")}
          </p>
        )}
      </div>
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
