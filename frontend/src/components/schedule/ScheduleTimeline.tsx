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
          backgroundColor: "var(--kb)",
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
              data-entry-id={entry.id}
              className="group schedule-row grid items-start py-1.5"
              style={{ gridTemplateColumns: "24px 44px 1fr", columnGap: 0 }}
            >
              <div className="flex justify-center relative pt-2.5" style={{ zIndex: 1 }}>
                <div
                  className={`schedule-dot rounded-full transition-[background-color,box-shadow] group-hover:bg-[var(--kb)] ${
                    entry.is_checked ? "bg-[var(--success)]" : "bg-[var(--border)]"
                  }`}
                  style={{
                    width: 14,
                    height: 14,
                    boxShadow: entry.is_checked
                      ? "0 0 0 5px var(--background), 0 0 0 6px var(--success)"
                      : "0 0 0 5px var(--background), 0 0 0 6px var(--kb)",
                  }}
                />
              </div>

              <div className="text-right pr-1">
                <div
                  className="font-bold leading-none"
                  style={{
                    color: urgency ?? (past_ && !today_ ? "var(--muted)" : "var(--foreground)"),
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
                    style={{ color: "var(--error-strong)", fontSize: 9 }}
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
              className="mt-2 mb-1 pl-[68px] text-[11px] font-semibold uppercase tracking-wider"
              style={{ color: "var(--muted)" }}
            >
              Nach Vereinbarung
            </div>
            {tbd.map((entry) => (
              <div
                key={entry.id}
                className="grid items-start py-1.5"
                style={{ gridTemplateColumns: "24px 44px 1fr", columnGap: 0 }}
              >
                <div className="flex justify-center relative pt-2.5" style={{ zIndex: 1 }}>
                  <div
                    className="rounded-full"
                    style={{
                      width: 14,
                      height: 14,
                      backgroundColor: entry.is_checked ? "var(--success)" : "var(--border)",
                      boxShadow: entry.is_checked
                        ? "0 0 0 5px var(--background), 0 0 0 6px var(--success)"
                        : "0 0 0 5px var(--background), 0 0 0 6px var(--kb)",
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
