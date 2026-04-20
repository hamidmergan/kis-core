import { Check, Clock, PencilSimple, Trash } from "@phosphor-icons/react";
import type { ZeitplanEntry } from "../_types";
import { _chunkLabel, _getChipIcon } from "../_utils";

interface SourceLike { uuid: string; filename: string; }

export function ZeitplanEntryCard({
  entry,
  isToday,
  isPast,
  editMode,
  sources,
  onToggleChecked,
  onEdit,
  onDelete,
  onPillClick,
}: {
  entry: ZeitplanEntry;
  isToday: boolean;
  isPast: boolean;
  editMode: boolean;
  sources: SourceLike[];
  onToggleChecked: (checked: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
}) {
  const baseStyle: React.CSSProperties = {
    border: "1px solid var(--border)",
    backgroundColor: entry.is_checked ? "#f0fdf4" : "var(--bg)",
    opacity: isPast && !isToday ? 0.55 : entry.is_checked ? 0.7 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: 13,
  };

  // One chip per source_ref (same source can appear multiple times at different
  // positions, e.g. PDF page X and another page Y).
  const chipRefs = entry.source_refs
    .map((ref) => {
      const src = sources.find((s) => s.uuid === ref.source_uuid);
      return src ? { ref, filename: src.filename } : null;
    })
    .filter((r): r is { ref: typeof entry.source_refs[number]; filename: string } => !!r);

  return (
    <div style={baseStyle}>
      <div className="flex items-start gap-2.5">
        {/* Checkbox */}
        <button
          type="button"
          aria-label={entry.is_checked ? "Erledigt aufheben" : "Als erledigt markieren"}
          onClick={() => onToggleChecked(!entry.is_checked)}
          className="flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors mt-0.5"
          style={{
            border: entry.is_checked ? "2px solid #10b981" : "2px solid var(--border)",
            backgroundColor: entry.is_checked ? "#10b981" : "#fff",
            color: "#fff",
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
          {(entry.due_time || entry.description) && (
            <div
              className="mt-1 text-[11.5px] flex items-center gap-1.5 flex-wrap"
              style={{ color: "var(--muted)" }}
            >
              {entry.due_time && (
                <span className="inline-flex items-center gap-1">
                  <Clock size={10} weight="bold" />
                  {entry.due_time}
                </span>
              )}
              {entry.due_time && entry.description && <span>·</span>}
              {entry.description && <span>{entry.description}</span>}
            </div>
          )}

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
                return (
                  <div
                    key={`${ref.source_uuid}-${page}-${startTime ?? 0}-${idx}`}
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      onPillClick?.(ref.source_uuid, page, filename, ref.raw_quote ?? undefined, startTime);
                    }}
                    onKeyDown={(e) => { if (e.key === "Enter") (e.currentTarget as HTMLElement).click(); }}
                    className="inline-flex items-center gap-1.5 cursor-pointer hover:opacity-80 transition-opacity"
                    title={label ? `${filename}, ${label}` : filename}
                  >
                    <span
                      className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium align-middle"
                      style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                    >
                      <ChipIcon size={8} weight="bold" />
                      {label ?? ""}
                    </span>
                    <span className="text-[10px] max-w-[180px] truncate" style={{ color: "var(--muted)" }}>
                      {filename}
                    </span>
                  </div>
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
