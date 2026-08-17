import type { ReactNode } from "react";
import { useLocale, useTranslations } from "next-intl";
import { todayISO, urgencyColor } from "./utils";

export interface DatedEntry {
  id: number | string;
  due_date: string | null;
  due_time?: string | null;
  /** "month": die Quelle nannte nur einen Monat, dann steht keine Tagesnummer da. */
  date_precision?: string | null;
  is_checked?: boolean;
}

interface CardContext {
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

function formatDay(
  dateStr: string,
  locale: string,
  monthOnly = false,
): { day: string | null; month: string; year: string } {
  const d = parseYMD(dateStr);
  const tag = locale === "en" ? "en-US" : "de-DE";
  return {
    // Nennt die Quelle nur einen Monat, steht hier keine Tagesnummer. Der Monatserste
    // ist nur der Sortierpunkt, im Dokument stand er nie.
    day: monthOnly ? null : String(d.getDate()).padStart(2, "0"),
    month: new Intl.DateTimeFormat(tag, { month: "short" }).format(d),
    year: String(d.getFullYear()),
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
  const t = useTranslations("schedule");
  const locale = useLocale();
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
        {dated.map((entry, i) => {
          const monthOnly = entry.date_precision === "month";
          const today_ = !monthOnly && isToday(entry.due_date!, today);
          const past_ = isPast(entry.due_date!, entry.due_time, today);
          const { day, month, year } = formatDay(entry.due_date!, locale, monthOnly);
          // Die Jahreszahl steht nur dort, wo ein Jahr anfängt. Danach reicht der Monat.
          const prev = i > 0 ? dated[i - 1].due_date : null;
          const startsYear = !prev || String(parseYMD(prev).getFullYear()) !== year;
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
                {day && (
                  <div
                    className="font-bold leading-none"
                    style={{
                      color: urgency ?? (past_ && !today_ ? "var(--muted)" : "var(--foreground)"),
                      fontSize: "1rem",
                    }}
                  >
                    {day}
                  </div>
                )}
                <div
                  className={`font-semibold uppercase tracking-wider ${day ? "mt-0.5" : ""}`}
                  style={{
                    color: urgency ?? (day ? "var(--muted)" : "var(--foreground)"),
                    fontSize: day ? "0.625rem" : "0.8125rem",
                  }}
                >
                  {month}
                </div>
                {startsYear && (
                  <div
                    className="mt-0.5 font-semibold"
                    style={{ color: "var(--error-strong)", fontSize: "0.625rem" }}
                  >
                    {year}
                  </div>
                )}
              </div>

              {renderCard(entry, { isPast: past_, urgency })}
            </div>
          );
        })}

        {tbd.length > 0 && renderTbdCard && (
          <>
            <div
              className="mt-2 mb-1 pl-17 text-2xs font-semibold uppercase tracking-wider"
              style={{ color: "var(--muted)" }}
            >
              {t("tbdHeading")}
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
                    style={{ color: "var(--muted)", fontSize: "0.625rem" }}
                  >
                    {t("tbdLabel")}
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
