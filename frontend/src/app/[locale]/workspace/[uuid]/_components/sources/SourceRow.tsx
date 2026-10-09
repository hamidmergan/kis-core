import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ArrowCounterClockwise,
  ArrowLeft,
  Check,
  DotsThreeVertical,
  TextAlignLeft,
  FolderSimple,
  PencilSimple,
  TextAa,
  TextT,
  Trash,
  WarningCircle,
} from "@phosphor-icons/react";
import type { Chapter, Source } from "../../_types";
import { OwnerOnly } from "../layout/OwnerOnly";
import { splitFilename, _isMediaFile } from "../../_utils";
import { FileIcon, SourceStatus } from "./FileIcon";

/** One row of the source list, the panel drives the renaming. */
export function SourceRow({
  src,
  checked,
  isOwner,
  ocrEnabled,
  compact,
  nested,
  chapters,
  menuOpen,
  menuMode,
  onMenuOpen,
  onMenuMode,
  renaming,
  onRenameStart,
  onRenameEnd,
  onToggle,
  onOpenViewer,
  onEditTranscript,
  onEditText,
  onDelete,
  onRename,
  onRetry,
  onSummarize,
  onMoveToChapter,
  onShowSummary,
}: {
  src: Source;
  checked: boolean;
  isOwner: boolean;
  /** Text recognition on platform wide, with it off there is nothing to catch up on. */
  ocrEnabled: boolean;
  compact: boolean;
  /** Indented as soon as chapters exist at all. */
  nested: boolean;
  chapters: Chapter[];
  menuOpen: boolean;
  /** 'root' is the normal menu, 'chapter' the chapter list for moving. */
  menuMode: "root" | "chapter";
  onMenuOpen: (open: boolean) => void;
  onMenuMode: (mode: "root" | "chapter") => void;
  renaming: boolean;
  onRenameStart: () => void;
  onRenameEnd: () => void;
  onToggle: (uuid: string) => void;
  onOpenViewer: (source: Source) => void;
  // Opens the recording and turns its transcript into the editable state.
  onEditTranscript?: (source: Source) => void;
  // Opens the pasted text of a text source for editing.
  onEditText?: (source: Source) => void;
  onDelete: (uuid: string) => void;
  onRename?: (uuid: string, name: string) => Promise<void>;
  onRetry: (uuid: string) => void;
  onSummarize?: (uuid: string) => void;
  onMoveToChapter?: (sourceUuid: string, chapterUuid: string | null) => void;
  onShowSummary?: (source: Source) => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  const [renameValue, setRenameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [renameBusy, setRenameBusy] = useState(false);
  const renameInputRef = useRef<HTMLInputElement>(null);

  // The name part is selected in the field so overtyping works right away.
  useEffect(() => {
    if (renaming) {
      setRenameValue(splitFilename(src.filename)[0]);
      setRenameError(null);
      renameInputRef.current?.select();
    }
  }, [renaming, src.filename]);

  // A source is only selectable once ingest is finished.
  const ready = src.status === "ready" && !src.progress;

  // Only a warning sign, and none when text recognition is off entirely.
  const ocrOpen = src.ocr_info?.open ?? [];
  const showOcrWarning = ready && ocrEnabled && ocrOpen.length > 0;
  // A short line for the menu, the full sentence hangs off it as a tooltip.
  const ocrLabel = !src.ocr_info
    ? ""
    : src.ocr_info.enabled
    ? t("ocrIncompleteShort", { open: ocrOpen.length })
    : t("ocrWasOffShort", { open: ocrOpen.length });
  const ocrHint = !src.ocr_info
    ? ""
    : src.ocr_info.enabled
    ? t("ocrIncomplete", { open: ocrOpen.length, done: src.ocr_info.done })
    : t("ocrWasOff", { open: ocrOpen.length });

  async function commitRename() {
    if (renameBusy || !onRename) return;
    const next = renameValue.trim();
    // Unchanged or empty: simply close, no call, no message.
    if (!next || next === splitFilename(src.filename)[0]) {
      onRenameEnd();
      setRenameError(null);
      return;
    }
    setRenameBusy(true);
    try {
      await onRename(src.uuid, next);
      onRenameEnd();
      setRenameError(null);
    } catch (e) {
      // The field stays open so the rejected name can be fixed right away.
      setRenameError(e instanceof Error && e.message ? e.message : t("renameFailed"));
    } finally {
      setRenameBusy(false);
    }
  }

  return (
    <div
      data-tour="source-row"
      className="group relative flex items-center transition-colors hover:bg-[var(--surface-dim)]"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <div className={`flex-shrink-0 py-2.5 ${nested ? "pl-7" : "pl-4"}`}>
        <button
          type="button"
          data-tour="source-check"
          onClick={() => { if (ready) onToggle(src.uuid); }}
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

      {renaming ? (
        <div className="flex-1 flex items-center gap-2 pl-3 pr-4 py-2.5 min-w-0">
          <FileIcon filename={src.filename} sourceUrl={src.source_url} fileType={src.file_type} />
          <input
            ref={renameInputRef}
            value={renameValue}
            disabled={renameBusy}
            autoFocus
            placeholder={t("renamePlaceholder")}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); commitRename(); }
              if (e.key === "Escape") { e.preventDefault(); onRenameEnd(); setRenameError(null); }
            }}
            onBlur={() => commitRename()}
            className="flex-1 min-w-0 text-sm px-2 py-1 rounded-md border-2 bg-background"
            style={{ borderColor: "var(--kb)", color: "var(--foreground)" }}
          />
          <span className="flex-shrink-0 text-sm" style={{ color: "var(--foreground-soft)" }}>
            {splitFilename(src.filename)[1]}
          </span>
        </div>
      ) : (
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
          <FileIcon filename={src.filename} sourceUrl={src.source_url} fileType={src.file_type} />
          <span
            className="flex-1 text-sm leading-snug truncate min-w-0 font-medium"
            style={{ color: "var(--foreground)" }}
            title={src.source_url ?? src.filename}
          >
            {src.filename}
          </span>
          <SourceStatus status={src.status} progress={src.progress} />
        </div>
      )}

      {renaming && renameError && (
        <div
          className="absolute left-4 right-4 top-full z-10 mt-1 rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
          style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
        >
          {renameError}
        </div>
      )}

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
          {src.has_summary && onShowSummary && (
            <div className="flex-shrink-0 flex items-center justify-center px-1 py-2.5">
              <button
                type="button"
                onClick={() => onShowSummary(src)}
                className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                style={{ backgroundColor: "var(--surface-dim)" }}
                title={t("summary.open")}
              >
                <TextAlignLeft size={14} weight="bold" />
              </button>
            </div>
          )}
          <OwnerOnly show={isOwner && src.status === "failed"}>
            <div className="flex-shrink-0 flex items-center justify-center px-1 py-2.5">
              <button
                type="button"
                onClick={() => onRetry(src.uuid)}
                className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                style={{ backgroundColor: "var(--surface-dim)" }}
                title={t("retry")}
              >
                <ArrowCounterClockwise size={13} weight="bold" />
              </button>
            </div>
          </OwnerOnly>
          <OwnerOnly show={isOwner}>
            <div className="flex-shrink-0 flex items-center justify-center pl-1 pr-2 py-2.5">
              <div className="relative">
                <button
                  type="button"
                  onClick={() => onMenuOpen(!menuOpen)}
                  className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                  style={{ backgroundColor: "var(--surface-dim)" }}
                  title={t("options")}
                >
                  <DotsThreeVertical size={16} weight="bold" />
                </button>
                {menuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => onMenuOpen(false)} />
                    <div
                      className="absolute right-0 top-9 z-50 rounded-xl py-1"
                      style={{
                        backgroundColor: "var(--surface)",
                        border: "1px solid var(--border)",
                        minWidth: 200,
                        maxHeight: "16rem",
                        overflowY: "auto",
                        boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                      }}
                    >
                      {menuMode === "chapter" ? (
                        <>
                          {chapters.map((c) => (
                            <MenuItem
                              key={c.uuid}
                              icon={<FolderSimple size={16} weight="bold" />}
                              label={c.name}
                              disabled={src.chapter_uuid === c.uuid}
                              onClick={() => { onMoveToChapter?.(src.uuid, c.uuid); onMenuOpen(false); }}
                            />
                          ))}
                          <MenuItem
                            icon={<FolderSimple size={16} weight="bold" />}
                            label={t("noChapter")}
                            disabled={!src.chapter_uuid}
                            onClick={() => { onMoveToChapter?.(src.uuid, null); onMenuOpen(false); }}
                          />
                          <div className="my-1" style={{ height: 1, backgroundColor: "var(--border)" }} />
                          <MenuItem
                            icon={<ArrowLeft size={16} weight="bold" />}
                            label={t("back")}
                            onClick={() => onMenuMode("root")}
                          />
                        </>
                      ) : (
                        <>
                          {onRename && (
                            <MenuItem
                              icon={<PencilSimple size={16} weight="bold" />}
                              label={t("rename")}
                              onClick={() => { onMenuOpen(false); onRenameStart(); }}
                            />
                          )}
                          {onMoveToChapter && chapters.length > 0 && (
                            <MenuItem
                              icon={<FolderSimple size={16} weight="bold" />}
                              label={t("moveToChapter")}
                              onClick={() => onMenuMode("chapter")}
                            />
                          )}
                          {/* Only a recording carries a transcript, a document has none. */}
                          {onEditTranscript && ready && _isMediaFile(src.filename) && (
                            <MenuItem
                              icon={<TextAa size={16} weight="bold" />}
                              label={t("editTranscript")}
                              onClick={() => { onMenuOpen(false); onEditTranscript(src); }}
                            />
                          )}
                          {onEditText && ready && src.file_type === "text" && (
                            <MenuItem
                              icon={<TextAa size={16} weight="bold" />}
                              label={t("editText")}
                              onClick={() => { onMenuOpen(false); onEditText(src); }}
                            />
                          )}
                          {onSummarize && ready && !src.has_summary && (
                            <MenuItem
                              icon={<TextAlignLeft size={16} weight="bold" />}
                              label={t("summary.create")}
                              onClick={() => { onMenuOpen(false); onSummarize(src.uuid); }}
                            />
                          )}
                          {/* Zustand und Nachholen stehen zusammen im Menue, damit die
                              Zeile selbst ruhig bleibt. Nachholen heisst: die Quelle
                              laeuft komplett neu durch, diesmal mit Texterkennung.
                              showOcrWarning traegt den Admin-Schalter schon mit, der
                              Eintrag ist also nie eine Sackgasse. */}
                          {showOcrWarning && (
                            <>
                              <div className="my-1" style={{ height: 1, backgroundColor: "var(--border)" }} />
                              <div
                                className="flex items-start gap-2 px-4 py-2 text-sm leading-snug"
                                style={{ color: "var(--error-strong)" }}
                                title={ocrHint}
                              >
                                <span className="flex-shrink-0 mt-0.5">
                                  <WarningCircle size={16} weight="fill" />
                                </span>
                                <span>{ocrLabel}</span>
                              </div>
                              <MenuItem
                                icon={<TextT size={16} weight="bold" />}
                                label={t("ocrCatchUp")}
                                onClick={() => { onMenuOpen(false); onRetry(src.uuid); }}
                              />
                              <div className="my-1" style={{ height: 1, backgroundColor: "var(--border)" }} />
                            </>
                          )}
                          <MenuItem
                            icon={<Trash size={16} weight="bold" />}
                            label={t("delete")}
                            danger
                            onClick={() => { onMenuOpen(false); onDelete(src.uuid); }}
                          />
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          </OwnerOnly>
        </>
      )}
    </div>
  );
}

export function MenuItem({
  icon,
  label,
  onClick,
  danger,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  danger?: boolean;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="w-full flex items-center gap-2 px-4 py-2.5 text-base text-left transition-colors enabled:hover:bg-[var(--surface-dim)] disabled:opacity-40 disabled:cursor-default"
      style={{ color: danger ? "rgb(185, 28, 28)" : "var(--foreground)" }}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="truncate">{label}</span>
    </button>
  );
}
