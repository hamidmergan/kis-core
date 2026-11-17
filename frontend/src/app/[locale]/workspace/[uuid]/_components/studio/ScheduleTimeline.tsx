import type { ScheduleEntry } from "../../_types";
import { ScheduleEntryCard } from "./ScheduleEntry";
import { ScheduleTimeline as SharedTimeline } from "@/components/schedule/ScheduleTimeline";

interface SourceLike { uuid: string; filename: string; }

export function ScheduleTimeline({
  entries,
  editMode,
  sources,
  sourceNumByUuid,
  onToggleChecked,
  onEdit,
  onDelete,
  onPillClick,
  markiertId = null,
}: {
  markiertId?: number | null;
  entries: ScheduleEntry[];
  editMode: boolean;
  sources: SourceLike[];
  sourceNumByUuid: Map<string, number>;
  onToggleChecked: (id: number, checked: boolean) => void;
  onEdit: (entry: ScheduleEntry) => void;
  onDelete: (id: number) => void;
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}) {
  const card = (entry: ScheduleEntry, isPast: boolean, urgency: string | null) => (
    <ScheduleEntryCard
      entry={entry}
      isPast={isPast}
      urgency={urgency}
      editMode={editMode}
      sources={sources}
      sourceNumByUuid={sourceNumByUuid}
      onToggleChecked={(c) => onToggleChecked(entry.id, c)}
      onEdit={() => onEdit(entry)}
      onDelete={() => onDelete(entry.id)}
      onPillClick={onPillClick}
      markiert={entry.id === markiertId}
    />
  );

  return (
    <SharedTimeline
      entries={entries}
      renderCard={(entry, ctx) => card(entry, ctx.isPast, ctx.urgency)}
      renderTbdCard={(entry) => card(entry, false, null)}
    />
  );
}
