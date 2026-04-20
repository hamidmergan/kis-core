import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CalendarBlank, CheckCircle, Files, PencilSimple, Plus, Sparkle, Trash } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { ZeitplanEntry, ZeitplanData } from "../_types";
import {
  fetchZeitplan,
  fetchZeitplanJob,
  fetchActiveZeitplanJob,
  generateZeitplan,
  createEntry as apiCreateEntry,
  updateEntry as apiUpdateEntry,
  deleteEntry as apiDeleteEntry,
  deleteAllEntries as apiDeleteAll,
} from "../_api/zeitplan";
import { ZeitplanTimeline } from "./ZeitplanTimeline";
import { ZeitplanEntryEditModal, type EditInput } from "./ZeitplanEntryEditModal";

interface SourceLike { uuid: string; filename: string; }

export function ZeitplanView({
  moduleUuid,
  sources,
  selectedSourceIds,
  onPillClick,
}: {
  moduleUuid: string;
  sources: SourceLike[];
  selectedSourceIds: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number, isExact?: boolean) => void;
}) {
  const [entries, setEntries] = useState<ZeitplanEntry[]>([]);
  const [processedUuids, setProcessedUuids] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generateMsg, setGenerateMsg] = useState<{ kind: "success" | "error" | "info"; text: string } | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editing, setEditing] = useState<ZeitplanEntry | null>(null);
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
      const data: ZeitplanData = await fetchZeitplan(moduleUuid);
      setEntries(data.entries);
      setProcessedUuids(data.processed_source_uuids);
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }, [moduleUuid]);

  useEffect(() => {
    if (!generateMsg) return;
    const t = setTimeout(() => setGenerateMsg(null), 10000);
    return () => clearTimeout(t);
  }, [generateMsg]);

  const startPolling = useCallback((jobId: number) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const job = await fetchZeitplanJob(moduleUuid, jobId);
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
  }, [moduleUuid, load, stopPolling]);

  // On mount: load entries, then check if a job is already running (from a prior session/tab)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      await load();
      if (cancelled) return;
      try {
        const active = await fetchActiveZeitplanJob(moduleUuid);
        if (cancelled || !active.active || !active.id) return;
        setGenerating(true);
        startPolling(active.id);
      } catch {
        // silently ignore — user can still trigger a new generate
      }
    })();
    return () => { cancelled = true; stopPolling(); };
  }, [moduleUuid, load, startPolling, stopPolling]);

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
      const updated = await apiUpdateEntry(moduleUuid, id, { is_checked: checked });
      setEntries((prev) => prev.map((e) => e.id === id ? updated : e));
    } catch {
      await load();
    }
  };

  const handleCreateManual = async (input: EditInput) => {
    const created = await apiCreateEntry(moduleUuid, {
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

    const updated = await apiUpdateEntry(moduleUuid, editing.id, patch);
    setEntries((prev) => prev.map((e) => e.id === editing.id ? updated : e));
    setEditing(null);
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm("Eintrag wirklich löschen?")) return;
    await apiDeleteEntry(moduleUuid, id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
  };

  const handleGenerate = async () => {
    if (selectedPending.length === 0) return;
    setGenerating(true);
    setGenerateMsg(null);
    try {
      const { job_id } = await generateZeitplan(moduleUuid, selectedPending);
      startPolling(job_id);
    } catch (e: any) {
      setGenerating(false);
      setGenerateMsg({ kind: "error", text: e?.message || "Fehler beim Start" });
    }
  };

  const handleDeleteAll = async () => {
    await apiDeleteAll(moduleUuid);
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
  else if (selectedProcessed.length === 0) selectionHint = `${selectedPending.length} Quelle(n) werden verarbeitet`;
  else selectionHint = `${selectedPending.length} neu · ${selectedProcessed.length} bereits verarbeitet`;

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      {/* Header: Quellen-Hint links, Edit-Icon rechts */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 gap-2">
        <div
          className="rounded-xl px-3 py-1.5 text-xs font-medium flex items-center gap-2"
          style={{
            color: !hasSources || !hasSelection ? "#B91C1C" : "var(--accent)",
          }}
        >
          <Files size={13} weight="bold" />
          {selectionHint}
        </div>
        <button
          type="button"
          onClick={() => setEditMode((v) => !v)}
          className="w-7 h-7 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity flex-shrink-0"
          style={{
            backgroundColor: editMode ? "var(--accent)" : "var(--surface-dim)",
            color: editMode ? "#fff" : "var(--muted)",
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
          className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
          style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}
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
              color: generateMsg.kind === "success" ? "#166534"
                : generateMsg.kind === "error" ? "#B91C1C"
                : "#334155",
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{ color: "var(--accent)", backgroundColor: "var(--surface-dim)" }}
          >
            <Plus size={12} weight="bold" /> Neuer Eintrag
          </button>
          <button
            type="button"
            onClick={() => setConfirmDeleteAll(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold"
            style={{ color: "#B91C1C", backgroundColor: "rgba(185,28,28,.08)" }}
          >
            <Trash size={12} weight="bold" /> Alles löschen
          </button>
        </div>
      )}

      {/* Content */}
      <div className="px-3 py-2">
        {loading && (
          <p className="text-xs py-6 text-center" style={{ color: "var(--muted)" }}>Lade Zeitplan...</p>
        )}
        {error && (
          <p className="text-xs py-6 text-center" style={{ color: "#B91C1C" }}>{error}</p>
        )}
        {!loading && !error && entries.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <CalendarBlank size={40} weight="light" style={{ color: "var(--muted)" }} />
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              Noch keine Einträge. Wähle Quellen links aus und generiere, oder erstelle manuelle Einträge.
            </p>
          </div>
        )}
        {!loading && entries.length > 0 && (
          <>
            <ZeitplanTimeline
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
                  <p key={s.number} className="text-[11px] leading-snug" style={{ color: "var(--muted)" }}>
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
        <ZeitplanEntryEditModal
          title="Neuer Eintrag"
          submitLabel="Anlegen"
          onCancel={() => setCreatingManual(false)}
          onSubmit={handleCreateManual}
        />
      )}
      {editing && (
        <ZeitplanEntryEditModal
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
            style={{ backgroundColor: "var(--bg)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-base font-bold mb-2" style={{ color: "var(--text)" }}>Zeitplan komplett löschen?</h3>
            <p className="text-xs" style={{ color: "var(--muted)" }}>
              Alle Einträge werden gelöscht und alle Quellen werden wieder generierbar. Diese Aktion kann nicht rückgängig gemacht werden.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteAll(false)}
                className="px-4 py-2 rounded-lg text-xs font-semibold"
                style={{ color: "var(--muted)", backgroundColor: "var(--surface-dim)" }}
              >
                Abbrechen
              </button>
              <button
                type="button"
                onClick={handleDeleteAll}
                className="px-4 py-2 rounded-lg text-xs font-semibold"
                style={{ color: "#fff", backgroundColor: "#B91C1C" }}
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
