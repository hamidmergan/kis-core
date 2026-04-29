"use client";

import Link from "next/link";
import { Check, Clock, Folder, Users } from "@phosphor-icons/react";
import { cleanScheduleDescription } from "./utils";

export interface ScheduleListEntry {
  id: number;
  workspace_uuid: string;
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
  href: string;
  onToggleChecked?: (checked: boolean) => void;
}

export function ScheduleEntryCardGlobal({
  entry,
  isPast,
  urgency,
  href,
  onToggleChecked,
}: ScheduleEntryCardGlobalProps) {
  const containerStyle: React.CSSProperties = {
    border: "1px solid var(--border)",
    backgroundColor: entry.is_checked ? "var(--success-bg)" : "var(--background)",
    opacity: isPast ? 0.55 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
    display: "flex",
    alignItems: "flex-start",
    gap: 10,
  };

  const isOwned = entry.module_relation === "owned";
  const RelIcon = isOwned ? Folder : Users;
  const description = cleanScheduleDescription(entry.description, entry.due_time);

  return (
    <div className="hover:outline-2 hover:outline-kb transition" style={containerStyle}>
      <button
        type="button"
        aria-label={
          isPast
            ? "Vergangene Termine können nicht geändert werden"
            : entry.is_checked
            ? "Erledigt aufheben"
            : "Als erledigt markieren"
        }
        title={isPast ? "Vergangene Termine sind gesperrt" : undefined}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (isPast) return;
          onToggleChecked?.(!entry.is_checked);
        }}
        disabled={isPast || !onToggleChecked}
        className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors mt-0.5 border-2 ${
          entry.is_checked
            ? "border-[var(--success)] bg-[var(--success)]"
            : !isPast && onToggleChecked
            ? "border-[var(--border)] bg-white hover:border-[var(--success)]"
            : "border-[var(--border)] bg-white"
        }`}
        style={{
          color: "#fff",
          cursor: isPast || !onToggleChecked ? "not-allowed" : "pointer",
        }}
      >
        {entry.is_checked && <Check size={11} weight="bold" />}
      </button>

      <Link
        href={href}
        className="flex-1 min-w-0"
        style={{ color: "inherit", textDecoration: "none" }}
      >
        <div
          className="font-semibold leading-tight break-words"
          style={{
            color: entry.is_checked ? "var(--success-strong)" : "var(--foreground)",
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
      </Link>
    </div>
  );
}
