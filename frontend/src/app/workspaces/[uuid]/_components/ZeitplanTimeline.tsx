import type { ZeitplanEntry } from "../_types";
import { ZeitplanEntryCard } from "./ZeitplanEntry";

function parseYMD(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function sortByDate(entries: ZeitplanEntry[]): ZeitplanEntry[] {
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

function isPast(dateStr: string, dueTime: string | null, now: Date): boolean {
  const d = parseYMD(dateStr);
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (d.getTime() < todayStart.getTime()) return true;
  if (d.getTime() > todayStart.getTime()) return false;
  // Same day: check the time if one is set
  if (!dueTime) return false;
  const [h, m] = dueTime.split(":").map(Number);
  const due = new Date(d.getFullYear(), d.getMonth(), d.getDate(), h || 0, m || 0);
  return due.getTime() < now.getTime();
}

interface SourceLike { uuid: string; filename: string; }

export function ZeitplanTimeline({
  entries,
  editMode,
  sources,
  sourceNumByUuid,
  onToggleChecked,
  onEdit,
  onDelete,
  onPillClick,
}: {
  entries: ZeitplanEntry[];
  editMode: boolean;
  sources: SourceLike[];
  sourceNumByUuid: Map<string, number>;
  onToggleChecked: (id: number, checked: boolean) => void;
  onEdit: (entry: ZeitplanEntry) => void;
  onDelete: (id: number) => void;
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
}) {
  const dated = sortByDate(entries.filter((e) => !!e.due_date));
  const tbd = entries.filter((e) => !e.due_date);
  const today = new Date();

  return (
    <div className="relative">
      {/* Continuous vertical line, left-aligned; dots break it visually via thick ring */}
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

          return (
            <div
              key={entry.id}
              className="grid items-start py-1.5"
              style={{ gridTemplateColumns: "24px 60px 1fr", columnGap: 0 }}
            >
              {/* Dot column — aligned with top of card */}
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

              {/* Date column — right-aligned */}
              <div className="text-right pr-1">
                <div
                  className="font-bold leading-none"
                  style={{
                    color: past_ && !today_ ? "var(--muted)" : "var(--text)",
                    fontSize: 17,
                  }}
                >
                  {day}
                </div>
                <div
                  className="mt-0.5 font-semibold uppercase tracking-wider"
                  style={{
                    color: "var(--muted)",
                    fontSize: 10,
                  }}
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

              {/* Card */}
              <ZeitplanEntryCard
                entry={entry}
                isToday={today_}
                isPast={past_}
                editMode={editMode}
                sources={sources}
                sourceNumByUuid={sourceNumByUuid}
                onToggleChecked={(c) => onToggleChecked(entry.id, c)}
                onEdit={() => onEdit(entry)}
                onDelete={() => onDelete(entry.id)}
                onPillClick={onPillClick}
              />
            </div>
          );
        })}

        {tbd.length > 0 && (
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
                <ZeitplanEntryCard
                  entry={entry}
                  isToday={false}
                  isPast={false}
                  editMode={editMode}
                  sources={sources}
                  sourceNumByUuid={sourceNumByUuid}
                  onToggleChecked={(c) => onToggleChecked(entry.id, c)}
                  onEdit={() => onEdit(entry)}
                  onDelete={() => onDelete(entry.id)}
                  onPillClick={onPillClick}
                />
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
