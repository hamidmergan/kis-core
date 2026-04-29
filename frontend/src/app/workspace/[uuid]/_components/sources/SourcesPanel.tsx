import { useEffect, useRef, useState } from "react";
import {
  SidebarSimple,
  Plus,
  FilePdf,
  Eye,
  ArrowCounterClockwise,
  Trash,
  Check,
} from "@phosphor-icons/react";
import type { Source } from "../../_types";
import { FileIcon, SourceStatus } from "./FileIcon";
import { UploadErrorsBlock } from "./UploadErrorsBlock";

export function SourcesPanel({
  sources,
  selectedSourceIds,
  onToggleSource,
  onOpenViewer,
  onDeleteSource,
  onRetrySource,
  onUpload,
  uploadProgress,
  uploadErrors,
  onDismissUploadErrors,
  isLecturer,
  onMinimize,
  moduleUuid,
  hideHeader,
}: {
  sources: Source[];
  selectedSourceIds: string[];
  onToggleSource: (uuid: string) => void;
  onOpenViewer: (source: Source) => void;
  onDeleteSource: (uuid: string) => void;
  onRetrySource: (uuid: string) => void;
  onUpload: (files: File[]) => void;
  uploadProgress: { current: number; total: number; percent: number } | null;
  uploadErrors: { filename: string; message: string }[];
  onDismissUploadErrors: () => void;
  isLecturer: boolean;
  onMinimize: () => void;
  moduleUuid: string;
  hideHeader?: boolean;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 220);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const readySources = sources.filter((s) => s.status === "ready");
  const allSelected = readySources.length > 0 && readySources.every((s) => selectedSourceIds.includes(s.uuid));

  function toggleAll() {
    if (allSelected) {
      // deselect all
      sources.forEach((s) => { if (selectedSourceIds.includes(s.uuid)) onToggleSource(s.uuid); });
    } else {
      // select all ready
      sources.filter((s) => s.status === "ready" && !selectedSourceIds.includes(s.uuid))
        .forEach((s) => onToggleSource(s.uuid));
    }
  }

  return (
    <div ref={panelRef} className="sources-panel flex flex-col h-full">
      {/* Panel header */}
      {!hideHeader && (
        <div
          className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span className="text-sm font-semibold tracking-wide" style={{ color: "var(--foreground)" }}>
            Quellen
          </span>
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title="Panel minimieren"
          >
            <SidebarSimple size={13} />
          </button>
        </div>
      )}

      {/* Upload button + drag-and-drop (lecturer) */}
      {isLecturer && (
        <div
          className="px-4 py-3 flex-shrink-0 transition-colors duration-150"
          style={{ borderBottom: "1px solid var(--border)" }}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.06)"; }}
          onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); if (!e.currentTarget.contains(e.relatedTarget as Node)) e.currentTarget.style.backgroundColor = ""; }}
          onDrop={(e) => {
            e.preventDefault(); e.stopPropagation(); e.currentTarget.style.backgroundColor = "";
            const fs = Array.from(e.dataTransfer.files ?? []);
            if (fs.length > 0) onUpload(fs);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.pptx,.mp3,.mp4,.wav,.flac,.m4a,.webm"
            className="hidden"
            onChange={(e) => {
              const fs = Array.from(e.target.files ?? []);
              if (fs.length > 0) { onUpload(fs); e.target.value = ""; }
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
            style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", border: "2px dashed rgba(var(--kb-rgb),0.3)" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--kb)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.3)"; }}
          >
            <Plus size={15} weight="bold" />
            Quellen hinzufügen
          </button>
          {uploadProgress !== null && (
            <div className="mt-2">
              <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress.percent}%`, backgroundColor: "var(--kb)" }}
                />
              </div>
              <p className="text-[11px] mt-1" >
                {uploadProgress.total > 1
                  ? `Datei ${uploadProgress.current}/${uploadProgress.total} – ${uploadProgress.percent}%`
                  : `Hochladen… ${uploadProgress.percent}%`}
              </p>
            </div>
          )}
          {uploadErrors.length > 0 && (
            <UploadErrorsBlock errors={uploadErrors} onDismiss={onDismissUploadErrors} />
          )}
        </div>
      )}

      {/* Select all row */}
      {sources.length > 0 && (
        <label
          className="sources-select-all flex items-center gap-3 px-4 py-2 flex-shrink-0 cursor-pointer"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <button
            type="button"
            onClick={toggleAll}
            aria-label={allSelected ? "Alle abwählen" : "Alle auswählen"}
            className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
              allSelected
                ? "border-[var(--kb)] bg-[var(--kb)]"
                : "border-[var(--border)] bg-white hover:border-[var(--kb)]"
            }`}
            style={{ color: "#fff" }}
          >
            {allSelected && <Check size={11} weight="bold" />}
          </button>
          <span className="text-xs" >
            Alle auswählen
          </span>
        </label>
      )}

      {/* Source list */}
      <div className="flex-1 overflow-y-auto">
        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 gap-2">
            <FilePdf size={32} color="var(--border)" />
            <p className="text-xs text-center" >
              Lade eine Quelle hoch.
            </p>
          </div>
        ) : (
          sources.map((src) => (
            <div
              key={src.uuid}
              className="relative flex items-center transition-colors hover:bg-[var(--surface-dim)]"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              <label
                className={`flex-1 flex items-center gap-3 px-4 py-2.5 min-w-0 ${src.status === "ready" ? "cursor-pointer" : "cursor-default"}`}
              >
                {(() => {
                  const checked = selectedSourceIds.includes(src.uuid);
                  const ready = src.status === "ready";
                  return (
                    <button
                      type="button"
                      onClick={() => { if (ready) onToggleSource(src.uuid); }}
                      disabled={!ready}
                      aria-label={checked ? "Quelle abwählen" : "Quelle auswählen"}
                      title={!ready ? "Quelle wird noch verarbeitet" : undefined}
                      className={`source-checkbox flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
                        checked
                          ? "border-[var(--kb)] bg-[var(--kb)]"
                          : ready
                          ? "border-[var(--border)] bg-white hover:border-[var(--kb)]"
                          : "border-[var(--border)] bg-white"
                      }`}
                      style={{ color: "#fff" }}
                    >
                      {checked && <Check size={11} weight="bold" />}
                    </button>
                  );
                })()}
                <FileIcon filename={src.filename} />
                <span
                  className="flex-1 text-xs leading-snug truncate min-w-0 font-medium"
                  style={{ color: "var(--foreground)" }}
                  title={src.filename}
                >
                  {src.filename}
                </span>
                <SourceStatus status={src.status} />
              </label>

              {src.status === "failed" && src.error_message && (
                <div
                  className="absolute left-4 right-4 top-full z-10 mt-1 rounded-lg px-3 py-2 text-[11px] leading-snug shadow-lg"
                  style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
                >
                  {src.error_message}
                </div>
              )}

              {!compact && (
                <>
                  <div className="flex-shrink-0 flex items-center justify-center px-1 py-2.5">
                    {isLecturer && src.status === "failed" ? (
                      <button
                        type="button"
                        onClick={() => onRetrySource(src.uuid)}
                        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                        style={{ backgroundColor: "var(--surface-dim)" }}
                        title="Erneut versuchen"
                      >
                        <ArrowCounterClockwise size={13} weight="regular" />
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onOpenViewer(src)}
                        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                        style={{ backgroundColor: "var(--surface-dim)" }}
                        title="Im Viewer öffnen"
                      >
                        <Eye size={13} />
                      </button>
                    )}
                  </div>
                  {isLecturer && (
                    <div className="flex-shrink-0 flex items-center justify-center px-1 py-2.5">
                      <button
                        type="button"
                        onClick={() => setDeleteSourceId(src.uuid)}
                        className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                        style={{ backgroundColor: "var(--surface-dim)" }}
                        title="Quelle löschen"
                      >
                        <Trash size={13} weight="regular" />
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))
        )}
      </div>

      {/* Delete confirmation modal */}
      {deleteSourceId && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Quelle löschen?</h3>
            <p className="text-sm text-foreground-soft mb-1">
              <span className="font-medium">{sources.find((s) => s.uuid === deleteSourceId)?.filename || "Quelle"}</span>
            </p>
            <p className="text-sm text-error mb-6">
              Die Quelle wird vollständig entfernt und kann nicht wiederhergestellt werden.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteSourceId(null)}
                className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-lg hover:bg-surface"
              >
                Abbrechen
              </button>
              <button
                onClick={() => { onDeleteSource(deleteSourceId); setDeleteSourceId(null); }}
                className="px-4 py-2 text-sm text-white bg-error hover:bg-error-strong rounded-lg"
              >
                Löschen
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
