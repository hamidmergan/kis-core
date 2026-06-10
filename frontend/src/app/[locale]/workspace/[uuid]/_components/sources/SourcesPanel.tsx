import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  SidebarSimple,
  Plus,
  FilePdf,
  ArrowCounterClockwise,
  Trash,
  Check,
  DotsThreeVertical,
} from "@phosphor-icons/react";
import type { Source, StaffNoteLink } from "../../_types";
import { FileIcon, SourceStatus } from "./FileIcon";
import { UploadErrorsBlock } from "./UploadErrorsBlock";
import { StaffNoteBox } from "./StaffNoteBox";
import { StaffNoteEditModal } from "./StaffNoteEditModal";
import { EmptyState } from "@/components/ui/EmptyState";

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
  workspaceUuid,
  hideHeader,
  staffNoteText,
  staffNoteLinks,
  onStaffNoteSave,
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
  workspaceUuid: string;
  hideHeader?: boolean;
  staffNoteText?: string | null;
  staffNoteLinks?: StaffNoteLink[];
  onStaffNoteSave?: (text: string | null, links: StaffNoteLink[]) => Promise<void>;
}) {
  const t = useTranslations("workspace.detail.sources");
  const tPanels = useTranslations("workspace.detail.panels");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [compact, setCompact] = useState(false);
  const [staffNoteModalOpen, setStaffNoteModalOpen] = useState(false);
  const noteLinks = staffNoteLinks ?? [];

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 220);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // A source is chat-ready once indexing is done (status "ready" with the
  // progress field cleared). Selecting an in-progress source would feed the
  // chat empty context.
  const isFullyReady = (s: Source) => s.status === "ready" && !s.progress;
  const readySources = sources.filter(isFullyReady);
  const allSelected = readySources.length > 0 && readySources.every((s) => selectedSourceIds.includes(s.uuid));

  function toggleAll() {
    if (allSelected) {
      // deselect all
      sources.forEach((s) => { if (selectedSourceIds.includes(s.uuid)) onToggleSource(s.uuid); });
    } else {
      // select all ready
      sources.filter((s) => isFullyReady(s) && !selectedSourceIds.includes(s.uuid))
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
          <span className="text-base font-semibold tracking-wide" style={{ color: "var(--foreground)" }}>
            {t("title")}
            {sources.length > 0 && (
              <span className="ml-1.5 font-normal" style={{ color: "var(--foreground-soft)" }}>
                ({sources.length})
              </span>
            )}
          </span>
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={tPanels("minimize")}
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
            className="add-source-btn w-full flex items-center justify-center gap-2 py-2 rounded-lg text-base font-medium border-2 border-dashed transition-colors text-[var(--kb)] bg-[rgba(var(--kb-rgb),0.08)] border-[rgba(var(--kb-rgb),0.3)] hover:bg-[rgba(var(--kb-rgb),0.16)] hover:border-[var(--kb)]"
          >
            <Plus size={15} weight="bold" />
            {t("addSources")}
          </button>
          {uploadProgress !== null && (
            <div className="mt-2">
              <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress.percent}%`, backgroundColor: "var(--kb)" }}
                />
              </div>
              <p className="text-xs mt-1" >
                {uploadProgress.total > 1
                  ? t("uploadingMulti", { current: uploadProgress.current, total: uploadProgress.total, percent: uploadProgress.percent })
                  : t("uploadingSingle", { percent: uploadProgress.percent })}
              </p>
            </div>
          )}
          {uploadErrors.length > 0 && (
            <UploadErrorsBlock errors={uploadErrors} onDismiss={onDismissUploadErrors} />
          )}
        </div>
      )}

      {/* Owner-managed pinned note (visible to owner + enrolled students) */}
      {onStaffNoteSave && (
        <StaffNoteBox
          text={staffNoteText ?? null}
          links={noteLinks}
          isOwner={isLecturer}
          workspaceUuid={workspaceUuid}
          onEdit={() => setStaffNoteModalOpen(true)}
        />
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
            aria-label={allSelected ? t("deselectAll") : t("selectAll")}
            className={`flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
              allSelected
                ? "border-[var(--kb)] bg-[var(--kb)]"
                : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
            }`}
            style={{ color: "#fff" }}
          >
            {allSelected && <Check size={11} weight="bold" />}
          </button>
          <span className="text-sm" >
            {t("selectAll")}
          </span>
        </label>
      )}

      {/* Source list */}
      <div className="flex-1 overflow-y-auto">
        {sources.length === 0 ? (
          <EmptyState
            size="lg"
            icon={<FilePdf size={32} weight="bold" />}
            text={t("emptyHint")}
          />
        ) : (
          sources.map((src) => {
            const checked = selectedSourceIds.includes(src.uuid);
            const ready = isFullyReady(src);
            return (
              <div
                key={src.uuid}
                className="group relative flex items-center transition-colors hover:bg-[var(--surface-dim)]"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <div className="flex-shrink-0 pl-4 py-2.5">
                  <button
                    type="button"
                    onClick={() => { if (ready) onToggleSource(src.uuid); }}
                    disabled={!ready}
                    aria-label={checked ? t("deselectSource") : t("selectSource")}
                    title={!ready ? t("stillProcessing") : undefined}
                    className={`source-checkbox flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
                      checked
                        ? "border-[var(--kb)] bg-[var(--kb)]"
                        : ready
                        ? "border-[var(--border)] bg-background hover:border-[var(--kb)]"
                        : "border-[var(--border)] bg-background"
                    }`}
                    style={{ color: "#fff" }}
                  >
                    {checked && <Check size={11} weight="bold" />}
                  </button>
                </div>

                <div
                  onClick={() => { if (ready) onOpenViewer(src); }}
                  onKeyDown={(e) => {
                    if (ready && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      onOpenViewer(src);
                    }
                  }}
                  role={ready ? "button" : undefined}
                  tabIndex={ready ? 0 : undefined}
                  title={ready ? t("openInViewer") : undefined}
                  className={`flex-1 flex items-center gap-3 pl-3 pr-4 py-2.5 min-w-0 ${ready ? "cursor-pointer" : "cursor-default"}`}
                >
                  <FileIcon filename={src.filename} />
                  <span
                    className="flex-1 text-sm leading-snug truncate min-w-0 font-medium"
                    style={{ color: "var(--foreground)" }}
                    title={src.filename}
                  >
                    {src.filename}
                  </span>
                  <SourceStatus status={src.status} progress={src.progress} />
                </div>

                {src.status === "failed" && src.error_message && (
                  <div
                    className="absolute left-4 right-4 top-full z-10 mt-1 rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
                    style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
                  >
                    {src.error_message}
                  </div>
                )}

                {!compact && (
                  <>
                    {isLecturer && src.status === "failed" && (
                      <div className="flex-shrink-0 flex items-center justify-center px-1 py-2.5">
                        <button
                          type="button"
                          onClick={() => onRetrySource(src.uuid)}
                          className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                          style={{ backgroundColor: "var(--surface-dim)" }}
                          title={t("retry")}
                        >
                          <ArrowCounterClockwise size={13} weight="bold" />
                        </button>
                      </div>
                    )}
                    {isLecturer && (
                      <div className="flex-shrink-0 flex items-center justify-center pl-1 pr-2 py-2.5">
                        <div className="relative">
                          <button
                            type="button"
                            onClick={() => setMenuOpenId(menuOpenId === src.uuid ? null : src.uuid)}
                            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                            style={{ backgroundColor: "var(--surface-dim)" }}
                            title={t("options")}
                          >
                            <DotsThreeVertical size={16} weight="bold" />
                          </button>
                          {menuOpenId === src.uuid && (
                            <>
                              <div className="fixed inset-0 z-40" onClick={() => setMenuOpenId(null)} />
                              <div
                                className="absolute right-0 top-9 z-50 rounded-xl py-1"
                                style={{
                                  backgroundColor: "var(--surface)",
                                  border: "1px solid var(--border)",
                                  minWidth: 180,
                                  boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                                }}
                              >
                                <button
                                  type="button"
                                  onClick={() => { setMenuOpenId(null); setDeleteSourceId(src.uuid); }}
                                  className="w-full flex items-center gap-2 px-4 py-2.5 text-base text-left hover:bg-[var(--surface-dim)] transition-colors"
                                  style={{ color: "rgb(185, 28, 28)" }}
                                >
                                  <Trash size={16} weight="bold" />
                                  {t("delete")}
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Staff note edit modal (owner only) */}
      {isLecturer && onStaffNoteSave && (
        <StaffNoteEditModal
          open={staffNoteModalOpen}
          initialText={staffNoteText ?? null}
          initialLinks={noteLinks}
          onClose={() => setStaffNoteModalOpen(false)}
          onSave={onStaffNoteSave}
        />
      )}

      {/* Delete confirmation modal */}
      {deleteSourceId && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteTitle")}</h3>
            <p className="text-sm text-foreground-soft mb-1 break-all">
              <span className="font-medium">{sources.find((s) => s.uuid === deleteSourceId)?.filename || t("deleteFallback")}</span>
            </p>
            <p className="text-sm text-error mb-6">
              {t("deleteWarning")}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteSourceId(null)}
                className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
              >
                {t("cancel")}
              </button>
              <button
                onClick={() => { onDeleteSource(deleteSourceId); setDeleteSourceId(null); }}
                className="px-4 py-2 text-sm btn-danger rounded-lg"
              >
                {t("delete")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
