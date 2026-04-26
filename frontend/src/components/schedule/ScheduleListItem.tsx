"use client";

import { Check, Clock, Folder, Users } from "@phosphor-icons/react";

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

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const MONTHS_SHORT = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
const WEEKDAYS_SHORT = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];

function relativeLabel(dueDate: string, today: string): string {
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86_400_000);
    return `vor ${days} Tag${days === 1 ? "" : "en"}`;
  }
  if (dueDate === today) return "heute";
  const a = new Date(dueDate);
  const days = Math.round((a.getTime() - new Date(today).getTime()) / 86_400_000);
  if (days === 1) return "morgen";
  if (days < 14) return `in ${days} Tagen`;
  return "";
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  return `${WEEKDAYS_SHORT[d.getDay()]} ${String(d.getDate()).padStart(2, "0")}. ${MONTHS_SHORT[d.getMonth()]}`;
}

interface ScheduleListItemProps {
  entry: ScheduleListEntry;
  isFirst: boolean;
  onClick: () => void;
}

export function ScheduleListItem({ entry: e, isFirst, onClick }: ScheduleListItemProps) {
  const today = todayISO();
  const relText = relativeLabel(e.due_date, today);
  const isOwned = e.module_relation === "owned";
  const RelIcon = isOwned ? Folder : Users;

  return (
    <li
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          onClick();
        }
      }}
      className="flex items-center gap-6 px-4 py-3 cursor-pointer hover:opacity-80 transition-opacity whitespace-nowrap"
      style={{ borderTop: isFirst ? "none" : "1px solid var(--border)" }}
    >
      <div className="flex-shrink-0 flex flex-col items-center justify-center min-w-[72px]">
        <span
          className="text-[11px] font-semibold"
          style={{ color: "var(--text)" }}
        >
          {shortDate(e.due_date)}
        </span>
        {relText && (
          <span
            className="text-[10px] font-semibold uppercase tracking-wider mt-0.5"
            style={{ color: "var(--muted)" }}
          >
            {relText}
          </span>
        )}
        {e.due_time && (
          <span
            className="inline-flex items-center gap-0.5 text-[11px] font-medium mt-0.5"
            style={{ color: "var(--muted)" }}
          >
            <Clock size={9} weight="bold" />
            {e.due_time}
          </span>
        )}
      </div>

      {e.is_checked && (
        <span
          className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center"
          style={{ backgroundColor: "#10b981", color: "#fff" }}
        >
          <Check size={11} weight="bold" />
        </span>
      )}

      <div className="flex-shrink-0">
        <div
          className="text-sm font-medium leading-tight"
          style={{
            color: e.is_checked ? "var(--muted)" : "var(--text)",
            textDecoration: e.is_checked ? "line-through" : "none",
          }}
          title={e.title}
        >
          {e.title}
        </div>
        {e.description && (
          <div
            className="mt-1 text-[11.5px]"
            style={{ color: "var(--muted)" }}
          >
            {e.description}
          </div>
        )}
        <div className="mt-1.5">
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
              {e.module_title}
            </span>
          </span>
        </div>
      </div>
    </li>
  );
}
