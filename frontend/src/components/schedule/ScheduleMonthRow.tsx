"use client";

import { useLocale, useTranslations } from "next-intl";
import { Check, Eye, EyeSlash, PencilSimple, Trash } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import IconButton from "@/components/ui/IconButton";
import type { ScheduleListEntry } from "./ScheduleEntryCardGlobal";
import { cleanScheduleDescription, dateQualifier, formatRangeEnd, urgencyColor } from "./utils";

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

interface Props {
  entry: ScheduleListEntry;
  /** Colour of the workspace, the same as in the grid. */
  color: string;
  today: string;
  onToggleChecked: (checked: boolean) => void;
  /** When set, the grid leaves this appointment out, the row stays here. */
  hidden: boolean;
  onToggleHidden: () => void;
  /** Only set for private appointments, workspace ones are edited in the workspace. */
  onEdit?: () => void;
  onDelete?: () => void;
}

/** Appointment row next to the grid, flatter than the card because the column is narrow. */
export default function ScheduleMonthRow({
  entry, color, today, onToggleChecked, hidden, onToggleHidden, onEdit, onDelete,
}: Props) {
  const t = useTranslations("schedule.card");
  const tMonth = useTranslations("schedule.month");
  const tPlan = useTranslations("schedule");
  const locale = useLocale();
  const tag = locale === "en" ? "en-US" : "de-DE";

  const date = parseYMD(entry.due_date);
  const monthOnly = entry.date_precision === "month";
  const month = new Intl.DateTimeFormat(tag, { month: "short" }).format(date);
  // If the source names only the month, the appointment is over only after the month.
  const isPast = monthOnly
    ? entry.due_date.slice(0, 7) < today.slice(0, 7)
    : entry.due_date < today;
  const urgency = urgencyColor(entry.due_date, today);
  const description = cleanScheduleDescription(entry.description, entry.due_time, entry.due_date);
  // The span always stands as a text line, the badge only labels the start day.
  const spannenEnde = formatRangeEnd(entry.due_date, entry.end_date, locale);
  // 'from' or 'until' above the day number when the source bounded the day.
  const marke = dateQualifier(entry);
  const bisText = spannenEnde ? tMonth("until", { datum: spannenEnde }) : null;
  const eigener = entry.workspace_uuid === null;

  const inhalt = (
    <>
      <div
        className={`text-sm font-bold leading-snug break-words ${eigener ? "" : "group-hover:underline"}`}
        style={{
          color: "var(--foreground)",
          textDecorationLine: entry.is_checked ? "line-through" : undefined,
        }}
      >
        {entry.title}
      </div>
      {bisText && (
        <div className="text-xs mt-0.5 font-semibold" style={{ color: "var(--muted)" }}>
          {bisText}
        </div>
      )}
      {description && (
        <div className="text-xs mt-0.5 leading-snug break-words" style={{ color: "var(--muted)" }}>
          {description}
        </div>
      )}
      <div className="flex items-center gap-2 mt-1.5 text-xs" style={{ color: "var(--foreground-soft)" }}>
        <span className="rounded-sm flex-shrink-0" style={{ width: 9, height: 9, backgroundColor: color }} />
        {eigener ? (
          <span
            className="text-3xs font-bold uppercase tracking-wide rounded-full px-2 py-px"
            style={{ border: "1px solid var(--border-soft)", color: "var(--muted)" }}
          >
            {tMonth("personal")}
          </span>
        ) : (
          <span className="truncate">{entry.module_title}</span>
        )}
      </div>
    </>
  );

  return (
    <div
      className="flex items-start gap-3 py-3.5"
      style={{ opacity: isPast ? 0.6 : 1 }}
    >
      {/* Haken und Auge stehen uebereinander: erledigt und im Raster sichtbar sind
          zwei getrennte Schalter fuer denselben Termin. */}
      <span className="flex flex-col items-center gap-1.5 flex-shrink-0">
        <button
          type="button"
          aria-label={entry.is_checked ? t("uncheckAria") : t("checkAria")}
          onClick={() => onToggleChecked(!entry.is_checked)}
          className="w-5.5 h-5.5 rounded-md flex items-center justify-center transition-colors mt-1.5 border-2"
          style={{
            borderColor: entry.is_checked ? "var(--kb)" : "var(--border)",
            backgroundColor: entry.is_checked ? "var(--kb)" : "var(--background)",
            color: "#fff",
          }}
        >
          {entry.is_checked && <Check size={12} weight="bold" />}
        </button>
        <IconButton
          size="sm"
          onClick={onToggleHidden}
          aria-label={hidden ? tMonth("showInCalendar") : tMonth("hideInCalendar")}
          title={hidden ? tMonth("showInCalendar") : tMonth("hideInCalendar")}
          aria-pressed={hidden}
          style={{ color: hidden ? "var(--muted)" : "var(--foreground-soft)" }}
        >
          {hidden ? <EyeSlash size={14} weight="bold" /> : <Eye size={14} weight="bold" />}
        </IconButton>
      </span>

      {/* Feste Höhe, sonst wird die Plakette ohne Tagesnummer niedriger als die anderen. */}
      <div
        className="flex-shrink-0 w-12 min-h-[62px] rounded-lg py-1.5 flex flex-col justify-center text-center"
        style={{ backgroundColor: "var(--surface)" }}
      >
        {/* Die Kopfzeile tritt zurueck, sonst traegt die Plakette drei Zeilen im selben Gewicht. */}
        {marke && (
          <div className="text-3xs font-bold" style={{ color: "var(--muted-soft)" }}>
            {marke === "from" ? tPlan("fromMark") : tPlan("untilMark")}
          </div>
        )}
        <div className="text-3xs font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
          {month}
        </div>
        {/* Nennt die Quelle nur einen Monat, steht hier keine Tagesnummer. */}
        {!monthOnly && (
          <div
            className="font-extrabold leading-none mt-0.5 text-base"
            style={{ color: urgency ?? "var(--foreground)" }}
          >
            {date.getDate()}
          </div>
        )}
        {/* Die Jahreszahl ist nur Beiwerk und darf nie nach Fehler aussehen. */}
        <div className="text-3xs font-bold mt-0.5" style={{ color: "var(--muted-soft)" }}>
          {monthOnly ? date.getFullYear() : String(date.getFullYear()).slice(2)}
        </div>
      </div>

      {eigener ? (
        <div className="min-w-0 flex-1">{inhalt}</div>
      ) : (
        <Link href={`/workspace/${entry.workspace_uuid}?tab=schedule`} className="min-w-0 flex-1 group">
          {inhalt}
        </Link>
      )}

      {/* Nur eigene Termine lassen sich hier aendern, die anderen gehoeren einem Workspace. */}
      {eigener && onEdit && onDelete && (
        <span className="flex items-center gap-1 flex-shrink-0">
          <IconButton onClick={onEdit} aria-label={tMonth("edit")} title={tMonth("edit")}>
            <PencilSimple size={14} weight="bold" />
          </IconButton>
          <IconButton onClick={onDelete} aria-label={tMonth("delete")} title={tMonth("delete")}>
            <Trash size={14} weight="bold" />
          </IconButton>
        </span>
      )}
    </div>
  );
}
