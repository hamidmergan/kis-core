"use client";

import Link from "next/link";
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
  href: string;
}

export function ScheduleEntryCardGlobal({
  entry,
  isPast,
  urgency,
  href,
}: ScheduleEntryCardGlobalProps) {
  const baseStyle: React.CSSProperties = {
    display: "block",
    border: "1px solid var(--border)",
    backgroundColor: entry.is_checked ? "#f0fdf4" : "var(--bg)",
    opacity: isPast ? 0.55 : entry.is_checked ? 0.7 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
    color: "inherit",
    textDecoration: "none",
  };

  const isOwned = entry.module_relation === "owned";
  const RelIcon = isOwned ? Folder : Users;
  const description = cleanScheduleDescription(entry.description, entry.due_time);

  return (
    <Link
      href={href}
      style={baseStyle}
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
    </Link>
  );
}
