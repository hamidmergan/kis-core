import { useTranslations } from "next-intl";
import { Check, Clock, PencilSimple, Trash } from "@phosphor-icons/react";
import type { ScheduleEntry } from "../../_types";
import { _chunkLabel, _getChipIcon } from "../../_utils";
import { cleanScheduleDescription } from "@/components/schedule/utils";

interface SourceLike { uuid: string; filename: string; }

export function ScheduleEntryCard({
  entry,
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
  const t = useTranslations("workspace.detail.studio.schedule.entry");
  const tChip = useTranslations("sourceChip");
  const baseStyle: React.CSSProperties = {
    border: "1px solid var(--border)",
    // Dim whenever the deadline has passed — including today's entries whose
    // time is already in the past (isPast is computed with due_time in mind).
    opacity: isPast ? 0.55 : entry.is_checked ? 0.7 : 1,
    boxShadow: "0 1px 3px rgba(13,31,45,.04)",
    borderRadius: 12,
    padding: "12px 14px",
    fontSize: "0.875rem",
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
    <div
      className={`border-2 border-transparent hover:border-kb transition-colors ${
        entry.is_checked
          ? "bg-[var(--success-bg)]"
          : "bg-background hover:bg-surface-dim group-hover:bg-surface-dim"
      }`}
      style={baseStyle}
    >
      <div className="flex items-start gap-2.5">
        {/* Checkbox */}
        <button
          type="button"
          aria-label={entry.is_checked ? t("uncheckAria") : t("checkAria")}
          onClick={() => onToggleChecked(!entry.is_checked)}
          className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors mt-0.5 border-2 ${
            entry.is_checked
              ? "border-[var(--success)] bg-[var(--success)]"
              : "border-[var(--border)] bg-background hover:border-[var(--success)]"
          }`}
          style={{
            color: "#fff",
            cursor: "pointer",
          }}
        >
          {entry.is_checked && <Check size={11} weight="bold" />}
        </button>

        <div className="flex-1 min-w-0">
          <div
            className="font-semibold leading-tight"
            style={{
              color: entry.is_checked ? "var(--success-strong)" : "var(--foreground)",
              textDecoration: entry.is_checked ? "line-through" : "none",
              fontSize: "0.875rem",
            }}
          >
            {entry.title}
          </div>
          {(() => {
            const description = cleanScheduleDescription(entry.description, entry.due_time);
            if (!entry.due_time && !description) return null;
            return (
              <div
                className="mt-1 text-2xs flex items-center gap-1.5 flex-wrap"
                
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
                    ? _chunkLabel(filename, 0, startTime, (key, vals) => tChip(key, vals))
                    : page > 0
                    ? _chunkLabel(filename, page, undefined, (key, vals) => tChip(key, vals))
                    : null;
                const num = sourceNumByUuid.get(ref.source_uuid);
                return (
                  <span
                    key={`${ref.source_uuid}-${page}-${startTime ?? 0}-${idx}`}
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      // Nav-only wie die anderen Studio-Tools (Datentabelle, Mindmap): nur zur
                      // Seite oder zum Zeitstempel springen, kein Highlight. raw_quote wird
                      // bewusst nicht mehr uebergeben.
                      onPillClick?.(ref.source_uuid, page, filename, undefined, startTime);
                    }}
                    onKeyDown={(e) => { if (e.key === "Enter") (e.currentTarget as HTMLElement).click(); }}
                    className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded-full font-medium chip-cite whitespace-nowrap cursor-pointer"
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
                className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                style={{ backgroundColor: "var(--surface-dim)" }}
                aria-label={t("edit")}
              >
                <PencilSimple size={11} weight="bold" />
              </button>
              <button
                type="button"
                onClick={onDelete}
                className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                style={{ backgroundColor: "var(--surface-dim)" }}
                aria-label={t("delete")}
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
