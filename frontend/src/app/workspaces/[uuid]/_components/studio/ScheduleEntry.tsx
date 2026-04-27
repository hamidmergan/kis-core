import { Check, Clock, PencilSimple, Trash } from "@phosphor-icons/react";
import type { ScheduleEntry } from "../../_types";
import { _chunkLabel, _getChipIcon } from "../../_utils";
import { cleanScheduleDescription } from "@/components/schedule/utils";

interface SourceLike { uuid: string; filename: string; }

export function ScheduleEntryCard({
  entry,
  isToday,
  isPast,
  urgency,
  editMode,
  sources,
  sourceNumByUuid,
  onToggleChecked,
  onEdit,
  onDelete,
  onPillClick,
}: {
  entry: ScheduleEntry;
  isToday: boolean;
  isPast: boolean;
  urgency: string | null;
  editMode: boolean;
  sources: SourceLike[];
  sourceNumByUuid: Map<string, number>;
  onToggleChecked: (checked: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}) {
  const baseStyle: React.CSSProperties = {
    border: "1px solid var(--border)",
    backgroundColor: entry.is_checked ? "#f0fdf4" : "var(--bg)",
    // Dim whenever the deadline has passed — including today's entries whose
    // time is already in the past (isPast is computed with due_time in mind).
    opacity: isPast ? 0.55 : entry.is_checked ? 0.7 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
  };

  // Dedup: same (source_uuid, page, start_time) appears only once per entry,
  // even if multiple raw quotes hit the same position in the same source.
  const chipRefs: { ref: typeof entry.source_refs[number]; filename: string }[] = [];
  const seen = new Set<string>();
  for (const ref of entry.source_refs) {
    const src = sources.find((s) => s.uuid === ref.source_uuid);
    if (!src) continue;
    const key = `${ref.source_uuid}|${ref.page_number ?? ""}|${ref.start_time ?? ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    chipRefs.push({ ref, filename: src.filename });
  }

  return (
    <div style={baseStyle}>
      <div className="flex items-start gap-2.5">
        {/* Checkbox */}
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
          onClick={() => { if (!isPast) onToggleChecked(!entry.is_checked); }}
          disabled={isPast}
          className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors mt-0.5"
          style={{
            border: entry.is_checked ? "2px solid #10b981" : "2px solid var(--border)",
            backgroundColor: entry.is_checked ? "#10b981" : "#fff",
            color: "#fff",
            cursor: isPast ? "not-allowed" : "pointer",
          }}
        >
          {entry.is_checked && <Check size={11} weight="bold" />}
        </button>

        <div className="flex-1 min-w-0">
          <div
            className="font-semibold leading-tight"
            style={{
              color: entry.is_checked ? "#166534" : "var(--text)",
              textDecoration: entry.is_checked ? "line-through" : "none",
              fontSize: 14,
            }}
          >
            {entry.title}
          </div>
          {(() => {
            const description = cleanScheduleDescription(entry.description, entry.due_time);
            if (!entry.due_time && !description) return null;
            return (
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
                {description && <span>{description}</span>}
              </div>
            );
          })()}

          {chipRefs.length > 0 && (
            <div
              className="mt-2 pt-2 flex flex-wrap gap-x-3 gap-y-1"
              style={{ borderTop: "1px dashed var(--border)" }}
            >
              {chipRefs.map(({ ref, filename }, idx) => {
                const ChipIcon = _getChipIcon(filename);
                const page = ref.page_number ?? 0;
                const startTime = ref.start_time ?? undefined;
                const label =
                  startTime != null
                    ? _chunkLabel(filename, 0, startTime)
                    : page > 0
                    ? _chunkLabel(filename, page)
                    : null;
                const num = sourceNumByUuid.get(ref.source_uuid);
                return (
                  <span
                    key={`${ref.source_uuid}-${page}-${startTime ?? 0}-${idx}`}
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Same path as Chat-LLM chips: non-exact → trim + fuzzy.
                      // raw_quote is the ±80 char backend window; viewer
                      // handles normalization.
                      onPillClick?.(ref.source_uuid, page, filename, ref.raw_quote ?? undefined, startTime, false);
                    }}
                    onKeyDown={(e) => { if (e.key === "Enter") (e.currentTarget as HTMLElement).click(); }}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity whitespace-nowrap cursor-pointer"
                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                    title={label ? `${filename}, ${label}` : filename}
                  >
                    <ChipIcon size={10} weight="bold" />
                    {num != null ? `[${num}]` : ""}{label ? ` ${label}` : ""}
                  </span>
                );
              })}
            </div>
          )}

          {editMode && (
            <div
              className="mt-2 pt-2 flex gap-2"
              style={{ borderTop: "1px solid var(--border)" }}
            >
              <button
                type="button"
                onClick={onEdit}
                className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
                aria-label="Bearbeiten"
              >
                <PencilSimple size={11} weight="bold" />
              </button>
              <button
                type="button"
                onClick={onDelete}
                className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
                aria-label="Löschen"
              >
                <Trash size={11} weight="bold" />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
