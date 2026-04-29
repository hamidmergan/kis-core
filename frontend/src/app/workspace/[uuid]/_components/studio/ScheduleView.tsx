import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarBlank, CheckCircle, Files, PencilSimple, Plus, Sparkle, Trash } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { ScheduleEntry, ScheduleData } from "../../_types";
import {
  fetchSchedule,
  fetchScheduleJob,
  fetchActiveScheduleJob,
  generateSchedule,
  createEntry as apiCreateEntry,
  updateEntry as apiUpdateEntry,
  deleteEntry as apiDeleteEntry,
  deleteAllEntries as apiDeleteAll,
} from "../../_api/schedule";
import { ScheduleTimeline } from "./ScheduleTimeline";
import { ScheduleEntryEditModal, type EditInput } from "./ScheduleEntryEditModal";

interface SourceLike { uuid: string; filename: string; }

export function ScheduleView({
  workspaceUuid,
  sources,
  selectedSourceIds,
  onPillClick,
}: {
  workspaceUuid: string;
  sources: SourceLike[];
  selectedSourceIds: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}) {
  const [entries, setEntries] = useState<ScheduleEntry[]>([]);
  const [processedUuids, setProcessedUuids] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<{ kind: "success" | "error" | "info"; text: string } | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editing, setEditing] = useState<ScheduleEntry | null>(null);
  const [creatingManual, setCreatingManual] = useState(false);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data: ScheduleData = await fetchSchedule(workspaceUuid);
      setEntries(data.entries);
      setProcessedUuids(data.processed_source_uuids);
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [workspaceUuid]);

  useEffect(() => {
    if (!generateMsg || generateMsg.kind === "error") return;
    const t = setTimeout(() => setGenerateMsg(null), 10000);
    return () => clearTimeout(t);
  }, [generateMsg]);

  const startPolling = useCallback((jobId: number) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const job = await fetchScheduleJob(workspaceUuid, jobId);
        if (job.status === "success") {
          stopPolling();
          setGenerating(false);
          setGenerateMsg({
            kind: "success",
            text: job.added_count > 0
              ? `${job.added_count} neue Einträge hinzugefügt`
              : "Keine neuen Einträge gefunden",
          });
          await load();
        } else if (job.status === "failed") {
          stopPolling();
          setGenerating(false);
          setGenerateMsg({ kind: "error", text: job.error || "Generierung fehlgeschlagen" });
          await load();
        }
      } catch (e: any) {
        stopPolling();
        setGenerating(false);
        setGenerateMsg({ kind: "error", text: e?.message || "Polling fehlgeschlagen" });
      }
    }, 2000);
  }, [workspaceUuid, load, stopPolling]);

  // On mount: load entries, then check if a job is already running (from a prior session/tab)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      await load();
      if (cancelled) return;
      try {
        const active = await fetchActiveScheduleJob(workspaceUuid);
        if (cancelled || !active.active || !active.id) return;
        setGenerating(true);
        startPolling(active.id);
      } catch {
        // silently ignore — user can still trigger a new generate
      }
    })();
    return () => { cancelled = true; stopPolling(); };
  }, [workspaceUuid, load, startPolling, stopPolling]);

  // Number sources by first appearance across all entries so chips like "[1] S. 23"
  // line up with the legend at the bottom of the timeline.
  const { sourceLegend, sourceNumByUuid } = useMemo(() => {
    const byUuid = new Map<string, number>();
    const legend: { number: number; filename: string; uuid: string }[] = [];
    for (const entry of entries) {
      for (const ref of entry.source_refs) {
        if (byUuid.has(ref.source_uuid)) continue;
        const src = sources.find((s) => s.uuid === ref.source_uuid);
        if (!src) continue;
        const num = legend.length + 1;
        byUuid.set(ref.source_uuid, num);
        legend.push({ number: num, filename: src.filename, uuid: src.uuid });
      }
    }
    return { sourceLegend: legend, sourceNumByUuid: byUuid };
  }, [entries, sources]);

  // Sources filtering
  const processedSet = useMemo(() => new Set(processedUuids), [processedUuids]);
  const selectedPending = useMemo(
    () => selectedSourceIds.filter((id) => !processedSet.has(id)),
    [selectedSourceIds, processedSet]
  );
  const selectedProcessed = useMemo(
    () => selectedSourceIds.filter((id) => processedSet.has(id)),
    [selectedSourceIds, processedSet]
  );

  const handleToggleChecked = async (id: number, checked: boolean) => {
    setEntries((prev) => prev.map((e) => e.id === id ? { ...e, is_checked: checked } : e));
    try {
      const updated = await apiUpdateEntry(workspaceUuid, id, { is_checked: checked });
      setEntries((prev) => prev.map((e) => e.id === id ? updated : e));
    } catch {
      await load();
    }
  };

  const handleCreateManual = async (input: EditInput) => {
    const created = await apiCreateEntry(workspaceUuid, {
      type: input.type,
      title: input.title,
      description: input.description || null,
      due_date: input.due_date || null,
      due_time: input.due_time || null,
      is_optional: input.is_optional,
    });
    setEntries((prev) => [...prev, created]);
    setCreatingManual(false);
  };

  const handleEditSubmit = async (input: EditInput) => {
    if (!editing) return;
    const patch: Parameters<typeof apiUpdateEntry>[2] = {
      type: input.type,
      title: input.title,
      description: input.description || null,
      is_optional: input.is_optional,
    };
    if (input.due_date) patch.due_date = input.due_date; else patch.clear_date = true;
    if (input.due_time) patch.due_time = input.due_time; else patch.clear_time = true;

    const updated = await apiUpdateEntry(workspaceUuid, editing.id, patch);
    setEntries((prev) => prev.map((e) => e.id === editing.id ? updated : e));
    setEditing(null);
  };

  const handleDelete = async (id: number) => {
    await apiDeleteEntry(workspaceUuid, id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const handleGenerate = async () => {
    if (selectedPending.length === 0) return;
    setGenerating(true);
    setGenerateMsg(null);
    try {
      const { job_id } = await generateSchedule(workspaceUuid, selectedPending);
      startPolling(job_id);
    } catch (e: any) {
      setGenerating(false);
      setGenerateMsg({ kind: "error", text: e?.message || "Fehler beim Start" });
    }
  };

  const handleDeleteAll = async () => {
    await apiDeleteAll(workspaceUuid);
    setEntries([]);
    setProcessedUuids([]);
    setConfirmDeleteAll(false);
    setEditMode(false);
  };

  const hasSources = sources.length > 0;
  const hasSelection = selectedSourceIds.length > 0;
  const canGenerate = hasSources && selectedPending.length > 0 && !generating;

  let selectionHint = "";
  if (!hasSources) selectionHint = "Keine Quellen im Workspace";
  else if (!hasSelection) selectionHint = "Keine Quelle ausgewählt";
  else if (selectedPending.length === 0) selectionHint = `${selectedSourceIds.length} ausgewählt · alle bereits verarbeitet`;
  else if (selectedProcessed.length === 0) selectionHint = `${selectedPending.length} ausgewählt · nicht verarbeitet`;
  else selectionHint = `${selectedPending.length} neu · ${selectedProcessed.length} bereits verarbeitet`;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header: Quellen-Hint links, Edit-Icon rechts */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 gap-2">
        <div
          className="rounded-xl px-3 py-1.5 text-xs font-medium flex items-center gap-2"
          style={{
            color: !hasSources || !hasSelection ? "var(--error-strong)" : "var(--kb)",
          }}
        >
          <Files size={13} weight="bold" />
          {selectionHint}
        </div>
        <button
          type="button"
          onClick={() => setEditMode((v) => !v)}
          className="w-7 h-7 rounded-full flex items-center justify-center btn-icon flex-shrink-0"
          style={{
            backgroundColor: editMode ? "var(--kb)" : "var(--surface-dim)",
            ...(editMode ? { color: "#fff" } : {}),
          }}
          aria-label="Bearbeiten"
          title="Bearbeiten"
        >
          {editMode ? <CheckCircle size={14} weight="bold" /> : <PencilSimple size={14} weight="bold" />}
        </button>
      </div>

      {/* Generate-Button */}
      <div className="px-3 pb-2 flex flex-col items-center gap-1.5">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all disabled:opacity-40"
        >
          {generating ? <Spinner size="xs" color="current" /> : <Sparkle size={12} weight="bold" />}
          {generating ? "Termine werden extrahiert..." : "Abgaben & Termine aus Quellen"}
        </button>
        {generateMsg && (
          <div
            className="mt-1 px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2"
            style={{
              backgroundColor: generateMsg.kind === "success" ? "rgba(22,163,74,0.08)"
                : generateMsg.kind === "error" ? "rgba(185,28,28,0.08)"
                : "rgba(100,116,139,0.1)",
              color: generateMsg.kind === "success" ? "var(--success-strong)"
                : generateMsg.kind === "error" ? "var(--error-strong)"
                : "var(--foreground-soft)",
            }}
          >
            <span>{generateMsg.text}</span>
            <button
              type="button"
              onClick={() => setGenerateMsg(null)}
              className="opacity-60 hover:opacity-100 text-xs leading-none"
              aria-label="Schließen"
            >
              ×
            </button>
          </div>
        )}
      </div>

      {/* Edit-Mode Actions */}
      {editMode && (
        <div className="px-3 pb-2 flex gap-2 justify-center">
          <button
            type="button"
            onClick={() => setCreatingManual(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:outline-2 hover:outline-[var(--kb)]"
            style={{ color: "var(--kb)", backgroundColor: "var(--surface-dim)" }}
          >
            <Plus size={12} weight="bold" /> Neuer Eintrag
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteAll(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all hover:outline-2 hover:outline-[var(--error-strong)]"
            style={{ color: "var(--error-strong)", backgroundColor: "rgba(185,28,28,.08)" }}
          >
            <Trash size={12} weight="bold" /> Alles löschen
          </button>
        </div>
      )}

      {/* Content */}
      <div className="px-3 py-2">
        {loading && (
          <p className="text-xs py-6 text-center" >Lade Zeitplan...</p>
        )}
        {error && (
          <p className="text-xs py-6 text-center" style={{ color: "var(--error-strong)" }}>{error}</p>
        )}
        {!loading && !error && entries.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-10 text-center text-muted">
            <CalendarBlank size={40} weight="light" />
            <p className="text-xs">
              Noch keine Einträge. Wähle Quellen links aus und generiere, oder erstelle manuelle Einträge.
            </p>
          </div>
        )}
        {!loading && entries.length > 0 && (
          <>
            <ScheduleTimeline
              entries={entries}
              editMode={editMode}
              sources={sources}
              sourceNumByUuid={sourceNumByUuid}
              onToggleChecked={handleToggleChecked}
              onEdit={setEditing}
              onDelete={handleDelete}
              onPillClick={onPillClick}
            />
            {sourceLegend.length > 0 && (
              <div className="flex flex-col gap-1 pt-4 mt-4 border-t border-dashed" style={{ borderColor: "var(--border)" }}>
                {sourceLegend.map((s) => (
                  <p key={s.number} className="text-[11px] leading-snug text-[var(--muted)]">
                    [{s.number}] {s.filename}
                  </p>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Modals */}
      {creatingManual && (
        <ScheduleEntryEditModal
          title="Neuer Eintrag"
          submitLabel="Anlegen"
          onCancel={() => setCreatingManual(false)}
          onSubmit={handleCreateManual}
        />
      )}
      {editing && (
        <ScheduleEntryEditModal
          title="Eintrag bearbeiten"
          submitLabel="Speichern"
          initial={editing}
          onCancel={() => setEditing(null)}
          onSubmit={handleEditSubmit}
        />
      )}
      {confirmDeleteAll && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
          onClick={() => setConfirmDeleteAll(false)}
        >
          <div
            className="rounded-2xl w-full max-w-sm p-5"
            style={{ backgroundColor: "var(--background)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-bold mb-2" style={{ color: "var(--foreground)" }}>Zeitplan komplett löschen?</h3>
            <p className="text-xs" >
              Alle Einträge werden gelöscht und alle Quellen werden wieder generierbar. Diese Aktion kann nicht rückgängig gemacht werden.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteAll(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold"
                style={{ backgroundColor: "var(--surface-dim)" }}
              >
                Abbrechen
              </button>
              <button
                type="button"
                onClick={handleDeleteAll}
                className="px-4 py-2 rounded-lg text-xs font-semibold"
                style={{ color: "#fff", backgroundColor: "var(--error-strong)" }}
              >
                Alles löschen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
