import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  SidebarSimple,
  Plus,
  FilePdf,
  FileAudio,
  FileVideo,
  FolderSimplePlus,
  FolderSimple,
  PencilSimple,
  Check,
  X,
} from "@phosphor-icons/react";
import type { Chapter, Source } from "../../_types";
import { OwnerOnly } from "../layout/OwnerOnly";
import { UploadErrorsBlock } from "./UploadErrorsBlock";
import { SourceRow } from "./SourceRow";
import { SourceSummaryModal } from "./SourceSummaryModal";
import { AddMaterialModal } from "./AddMaterialModal";
import { TextSourceEditModal } from "./TextSourceEditModal";
import { ChapterHead } from "./ChapterHead";
import { MenuItem } from "./SourceRow";
import { GroupCheckbox } from "./GroupCheckbox";
import { groupState, isFullyReady, toggleGroupTargets } from "./_selection";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";

export function SourcesPanel({
  sources,
  selectedSourceIds,
  onToggleSource,
  onOpenViewer,
  onEditTranscript,
  onDeleteSource,
  onRenameSource,
  onRetrySource,
  onSummarizeSource,
  onUpload,
  onAddLink,
  onAddYoutube,
  onAddPage,
  onAddText,
  onEditText,
  textMaxChars,
  uploadProgress,
  uploadErrors,
  onDismissUploadErrors,
  isOwner,
  ocrEnabled = true,
  onMinimize,
  workspaceUuid,
  hideHeader,
  chapters,
  onCreateChapter,
  onRenameChapter,
  onDeleteChapter,
  onMoveChapter,
  onSetSourceChapter,
  onMoveSource,
  closedChapters,
  onToggleChapterOpen,
}: {
  sources: Source[];
  selectedSourceIds: string[];
  onToggleSource: (uuid: string) => void;
  onOpenViewer: (source: Source) => void;
  onEditTranscript?: (source: Source) => void;
  onDeleteSource: (uuid: string) => void;
  onRenameSource?: (uuid: string, name: string) => Promise<void>;
  onRetrySource: (uuid: string) => void;
  /** Catches up on the summary of a finished source that has none. */
  onSummarizeSource?: (uuid: string) => void;
  onUpload: (files: File[], chapterUuid?: string | null) => void;
  /** Reads in a web page by link, missing means the plus opens the file picker straight away. */
  onAddLink?: (url: string, chapterUuid?: string | null) => Promise<void>;
  /** Adds a YouTube video with its pasted transcript. */
  onAddYoutube?: (url: string, transcript: string, chapterUuid?: string | null) => Promise<void>;
  /** Puts one of the person's pages from Pages into the workspace. */
  onAddPage?: (jobUuid: string, chapterUuid?: string | null) => Promise<void>;
  /** Adds a pasted text as a source. */
  onAddText?: (title: string, text: string, chapterUuid?: string | null) => Promise<void>;
  /** Saves the edited text of a text source. */
  onEditText?: (sourceUuid: string, text: string) => Promise<void>;
  textMaxChars?: number;
  uploadProgress: { current: number; total: number; percent: number; large: boolean } | null;
  uploadErrors: { filename: string; message: string }[];
  onDismissUploadErrors: () => void;
  isOwner: boolean;
  /** Text recognition on platform wide (admin switch), it only drives the catch-up. */
  ocrEnabled?: boolean;
  onMinimize: () => void;
  workspaceUuid: string;
  hideHeader?: boolean;
  /** Structure of the list, empty means one flat list as before. */
  chapters?: Chapter[];
  onCreateChapter?: (name: string) => Promise<void>;
  onRenameChapter?: (uuid: string, name: string) => Promise<void>;
  onDeleteChapter?: (uuid: string) => void;
  onMoveChapter?: (uuid: string, direction: "up" | "down") => void;
  onSetSourceChapter?: (sourceUuid: string, chapterUuid: string | null) => void;
  /** Moves a file one slot within its chapter. */
  onMoveSource?: (sourceUuid: string, direction: "up" | "down") => void;
  /** Folded chapters, kept by the page so the tour can unfold one. */
  closedChapters: string[];
  onToggleChapterOpen: (chapterUuid: string) => void;
}) {
  const t = useTranslations("workspace.detail.sources");
  const tPanels = useTranslations("workspace.detail.panels");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [addOpen, setAddOpen] = useState(false);
  // Chapter picked in the add dialog, empty on every opening.
  const [addChapter, setAddChapter] = useState("");
  const panelRef = useRef<HTMLDivElement>(null);
  const newChapterRef = useRef<HTMLInputElement>(null);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [deleteChapterTarget, setDeleteChapterTarget] = useState<Chapter | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [summarySource, setSummarySource] = useState<Source | null>(null);
  const [editTextSource, setEditTextSource] = useState<Source | null>(null);
  const [menuMode, setMenuMode] = useState<"root" | "chapter">("root");
  const [renameId, setRenameId] = useState<string | null>(null);
  const [compact, setCompact] = useState(false);
  const [creatingChapter, setCreatingChapter] = useState(false);
  const [newChapterName, setNewChapterName] = useState("");
  const [newChapterError, setNewChapterError] = useState<string | null>(null);
  const [newChapterBusy, setNewChapterBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  // Moving has its own picks, starts empty and leaves the chat selection alone.
  const [moving, setMoving] = useState(false);
  const [movePicked, setMovePicked] = useState<string[]>([]);
  const [bulkMenuOpen, setBulkMenuOpen] = useState(false);
  const chapterList = useMemo(
    () => [...(chapters ?? [])].sort((a, b) => a.position - b.position),
    [chapters]
  );

  // The target chapter unfolds so the new row is in sight.
  const targetChapter = () => {
    const id = chapterList.some((c) => c.uuid === addChapter) ? addChapter : "";
    if (id && closedChapters.includes(id)) onToggleChapterOpen(id);
    return id || null;
  };

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 220);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (creatingChapter) newChapterRef.current?.focus();
  }, [creatingChapter]);

  const selectable = moving ? () => true : isFullyReady;
  const picked = moving ? movePicked : selectedSourceIds;
  const togglePick = moving
    ? (id: string) => setMovePicked((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
    : onToggleSource;
  const readySources = sources.filter(selectable);
  const allSelected = readySources.length > 0 && readySources.every((s) => picked.includes(s.uuid));

  function toggleAll() {
    if (allSelected) {
      // deselect all
      sources.forEach((s) => { if (picked.includes(s.uuid)) togglePick(s.uuid); });
    } else {
      // select all ready
      sources.filter((s) => selectable(s) && !picked.includes(s.uuid))
        .forEach((s) => togglePick(s.uuid));
    }
  }

  function startMoving() {
    setMovePicked([]);
    setBulkMenuOpen(false);
    setMoving(true);
  }

  function stopMoving() {
    setMoving(false);
    setMovePicked([]);
    setBulkMenuOpen(false);
  }

  // Whatever points at a foreign chapter lands under 'no chapter'.
  const known = new Set(chapterList.map((c) => c.uuid));
  const checkedSources = sources.filter((s) => movePicked.includes(s.uuid));
  const chapterOf = (s: Source) => (s.chapter_uuid && known.has(s.chapter_uuid) ? s.chapter_uuid : null);

  // Moves every picked file at once and ends the mode.
  function moveChecked(chapterUuid: string | null) {
    if (!onSetSourceChapter) return;
    checkedSources
      .filter((s) => chapterOf(s) !== chapterUuid)
      .forEach((s) => onSetSourceChapter(s.uuid, chapterUuid));
    if (chapterUuid && closedChapters.includes(chapterUuid)) onToggleChapterOpen(chapterUuid);
    stopMoving();
  }

  const canMove = isOwner && !!onSetSourceChapter && chapterList.length > 0;
  // The pen orders chapters and files, moving into chapters only exists with chapters.
  const canArrange = isOwner && (canMove || !!onMoveSource);
  // A mode without anything to do ends by itself.
  useEffect(() => {
    if (moving && !canArrange) stopMoving();
  }, [moving, canArrange]);
  const loose = sources.filter((s) => !s.chapter_uuid || !known.has(s.chapter_uuid));

  const toggleGroup = (list: Source[]) =>
    toggleGroupTargets(list, picked, selectable).forEach(togglePick);

  async function commitNewChapter() {
    if (newChapterBusy || !onCreateChapter) return;
    const name = newChapterName.trim();
    if (!name) { setCreatingChapter(false); setNewChapterError(null); return; }
    setNewChapterBusy(true);
    try {
      await onCreateChapter(name);
      setCreatingChapter(false);
      setNewChapterName("");
      setNewChapterError(null);
    } catch (e) {
      setNewChapterError(e instanceof Error && e.message ? e.message : t("chapterCreateFailed"));
    } finally {
      setNewChapterBusy(false);
    }
  }

  // The position counts within the file's own group, not the whole list.
  function renderRow(src: Source, nested: boolean, group: Source[]) {
    const index = group.indexOf(src);
    return (
      <SourceRow
        key={src.uuid}
        src={src}
        checked={picked.includes(src.uuid)}
        hideCheck={moving && !canMove}
        selectAny={moving}
        isOwner={isOwner}
        ocrEnabled={ocrEnabled}
        compact={compact}
        nested={nested}
        chapters={chapterList}
        menuOpen={menuOpenId === src.uuid}
        menuMode={menuMode}
        onMenuOpen={(open) => { setMenuOpenId(open ? src.uuid : null); setMenuMode("root"); }}
        onMenuMode={setMenuMode}
        renaming={renameId === src.uuid}
        onRenameStart={() => setRenameId(src.uuid)}
        onRenameEnd={() => setRenameId(null)}
        onToggle={togglePick}
        onOpenViewer={onOpenViewer}
        onEditTranscript={onEditTranscript}
        onEditText={onEditText ? setEditTextSource : undefined}
        onDelete={setDeleteSourceId}
        onRename={onRenameSource}
        onRetry={onRetrySource}
        onSummarize={onSummarizeSource}
        onMoveToChapter={onSetSourceChapter}
        onShowSummary={setSummarySource}
        arranging={moving}
        isFirst={index === 0}
        isLast={index === group.length - 1}
        onMove={isOwner ? onMoveSource : undefined}
      />
    );
  }

  // Create in house blue, in the header or the narrow row below it.
  const ownerActions = isOwner ? (
    <>
      <IconButton
        data-tour="add-source"
        onClick={() => {
          setAddChapter("");
          if (onAddLink) setAddOpen(true);
          else fileInputRef.current?.click();
        }}
        title={t("addSources")}
        aria-label={t("addSources")}
        className="text-[var(--kb)]"
        style={{ backgroundColor: "rgba(var(--kb-rgb),0.10)" }}
      >
        <Plus size={14} weight="bold" />
      </IconButton>
      {onCreateChapter && (
        <IconButton
          onClick={() => { setCreatingChapter(true); setNewChapterError(null); }}
          title={t("addChapter")}
          aria-label={t("addChapter")}
          className="text-[var(--kb)]"
          style={{ backgroundColor: "rgba(var(--kb-rgb),0.10)" }}
        >
          <FolderSimplePlus size={14} weight="bold" />
        </IconButton>
      )}
    </>
  ) : null;

  return (
    <div ref={panelRef} data-tour="sources-panel" className="sources-panel flex flex-col h-full">
      {/* Panel header. Anlegen sitzt hier, deshalb kostet es keine eigene Zeile. */}
      {!hideHeader && (
        <div
          data-panel-header=""
          className="flex items-center gap-1.5 px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span className="flex-1 min-w-0 truncate text-base font-semibold tracking-wide" style={{ color: "var(--foreground)" }}>
            {t("title")}
            {sources.length > 0 && (
              <span className="ml-1.5 font-normal" style={{ color: "var(--foreground-soft)" }}>
                ({sources.length})
              </span>
            )}
          </span>
          {isOwner && (
            <>
              {/* Ansicht bleibt grau. Der Strich zieht die Grenze. */}
              {/* Nur die Bedienelemente werden markiert, der Trennstrich nicht. */}
              <OwnerOnly show>{ownerActions}</OwnerOnly>
              <span className="mx-1 flex-shrink-0" style={{ width: 1, height: 18, backgroundColor: "var(--border)" }} />
            </>
          )}
          <IconButton onClick={onMinimize} title={tPanels("minimize")}>
            <SidebarSimple size={13} />
          </IconButton>
        </div>
      )}

      {/* Mobil: die Kopfzeile ist weg, den Titel traegt die Tab-Leiste. Die
          Anlegen-Knoepfe brauchen trotzdem einen Platz, also bekommen sie eine
          eigene schmale Zeile ohne Titel und ohne Minimieren. */}
      {hideHeader && ownerActions && (
        <div
          className="flex items-center justify-end gap-1.5 px-3 py-1.5 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <OwnerOnly show>{ownerActions}</OwnerOnly>
        </div>
      )}

      {/* Das Dateifeld liegt ausserhalb der Kopfzeile, damit es auch dann da ist,
          wenn die Kopfzeile ausgeblendet ist (mobil). */}
      {isOwner && (
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.pptx,.mp3,.mp4,.wav,.flac,.m4a,.webm"
          className="hidden"
          onChange={(e) => {
            const fs = Array.from(e.target.files ?? []);
            if (fs.length > 0) { onUpload(fs, targetChapter()); e.target.value = ""; }
          }}
        />
      )}

      <SourceSummaryModal source={summarySource} onClose={() => setSummarySource(null)} />

      {isOwner && onAddLink && (
        <AddMaterialModal
          open={addOpen}
          onClose={() => setAddOpen(false)}
          onPickFile={() => fileInputRef.current?.click()}
          onAddLink={(url) => onAddLink(url, targetChapter())}
          onAddYoutube={onAddYoutube && ((url, transcript) => onAddYoutube(url, transcript, targetChapter()))}
          onAddPage={onAddPage && ((jobUuid) => onAddPage(jobUuid, targetChapter()))}
          onAddText={onAddText && ((title, text) => onAddText(title, text, targetChapter()))}
          textMaxChars={textMaxChars}
          chapters={onSetSourceChapter ? chapterList : undefined}
          chapterUuid={addChapter}
          onChapterChange={setAddChapter}
        />
      )}

      {isOwner && onEditText && textMaxChars && (
        <TextSourceEditModal
          source={editTextSource}
          workspaceUuid={workspaceUuid}
          maxChars={textMaxChars}
          onClose={() => setEditTextSource(null)}
          onSave={onEditText}
        />
      )}

      {/* Fortschritt und Fehler des Hochladens. Stehen direkt unter dem Knopf,
          der sie ausgeloest hat, und sind sonst nicht da. */}
      {isOwner && (uploadProgress !== null || uploadErrors.length > 0) && (
        <div className="px-4 py-2 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          {uploadProgress !== null && (
            <>
              <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress.percent}%`, backgroundColor: "var(--kb)" }}
                />
              </div>
              <p className="text-xs mt-1">
                {uploadProgress.total > 1
                  ? t("uploadingMulti", { current: uploadProgress.current, total: uploadProgress.total, percent: uploadProgress.percent })
                  : t("uploadingSingle", { percent: uploadProgress.percent })}
              </p>
              {uploadProgress.large && (
                <p className="text-xs mt-1" style={{ color: "var(--foreground-soft)" }}>{t("uploadingLarge")}</p>
              )}
            </>
          )}
          {uploadErrors.length > 0 && (
            <UploadErrorsBlock errors={uploadErrors} onDismiss={onDismissUploadErrors} />
          )}
        </div>
      )}

      {/* Neues Kapitel */}
      {creatingChapter && (
        <div
          className="relative px-3 py-2 flex items-center gap-2 flex-shrink-0"
          style={{ backgroundColor: "var(--surface-dim)", borderBottom: "1px solid var(--border)" }}
        >
          <input
            ref={newChapterRef}
            value={newChapterName}
            disabled={newChapterBusy}
            placeholder={t("chapterNamePlaceholder")}
            onChange={(e) => setNewChapterName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); commitNewChapter(); }
              if (e.key === "Escape") { e.preventDefault(); setCreatingChapter(false); setNewChapterError(null); }
            }}
            className="flex-1 min-w-0 text-sm px-2 py-1 rounded-md border-2 bg-background"
            style={{ borderColor: "var(--kb)", color: "var(--foreground)" }}
          />
          <button
            type="button"
            onClick={commitNewChapter}
            disabled={newChapterBusy}
            className="px-3 py-1.5 text-sm rounded-lg btn-primary flex-shrink-0"
          >
            {t("chapterCreate")}
          </button>
          <IconButton
            onClick={() => { setCreatingChapter(false); setNewChapterName(""); setNewChapterError(null); }}
            disabled={newChapterBusy}
            aria-label={t("cancel")}
            title={t("cancel")}
          >
            <X size={13} weight="bold" />
          </IconButton>
          {newChapterError && (
            <div
              className="absolute left-3 right-3 top-full z-10 mt-1 rounded-lg px-3 py-2 text-xs leading-snug shadow-lg"
              style={{ backgroundColor: "#FEF2F2", border: "1px solid var(--error-border)", color: "var(--error-strong)" }}
            >
              {newChapterError}
            </div>
          )}
        </div>
      )}

      {/* Select all row. Der Stift schaltet in den Verschiebe-Modus, dann
          zeigt die Zeile in Hausblau, dass jetzt fuers Verschieben gewaehlt wird. */}
      {sources.length > 0 && (
        <div
          onClick={moving && !canMove ? undefined : toggleAll}
          data-testid={moving ? "move-bar" : undefined}
          className="sources-select-all flex items-center gap-3 px-4 py-2 flex-shrink-0 cursor-pointer"
          style={moving
            ? { backgroundColor: "rgba(var(--kb-rgb),0.12)", borderBottom: "2px solid var(--kb)" }
            : { borderBottom: "1px solid var(--border)" }}
        >
          <button
            type="button"
            aria-label={allSelected ? t("deselectAll") : t("selectAll")}
            className={`${moving && !canMove ? "invisible" : ""} flex-shrink-0 w-5 h-5 rounded-md flex items-center justify-center transition-colors border-2 ${
              allSelected
                ? "border-[var(--kb)] bg-[var(--kb)]"
                : "border-[var(--border)] bg-background hover:border-[var(--kb)]"
            }`}
            style={{ color: "#fff" }}
          >
            {allSelected && <Check size={11} weight="bold" />}
          </button>
          <span
            className={`flex-1 min-w-0 truncate text-sm ${moving ? "font-medium" : ""}`}
            style={moving ? { color: "var(--kb)" } : undefined}
          >
            {moving ? (canMove ? t("moveModeHint") : t("arrangeModeHint")) : t("selectAll")}
          </span>
          <OwnerOnly show={canArrange}>
            <div className="relative flex-shrink-0 flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
              {moving ? (
                <>
                  {canMove && <button
                    type="button"
                    data-testid="move-checked"
                    disabled={checkedSources.length === 0}
                    onClick={() => setBulkMenuOpen((o) => !o)}
                    className="btn-primary flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium disabled:opacity-50"
                  >
                    <FolderSimple size={13} weight="bold" />
                    {compact ? checkedSources.length : t("moveChecked", { count: checkedSources.length })}
                  </button>}
                  <IconButton
                    data-testid="move-cancel"
                    onClick={stopMoving}
                    title={t("cancel")}
                    aria-label={t("cancel")}
                  >
                    <X size={13} weight="bold" />
                  </IconButton>
                </>
              ) : (
                <IconButton
                  data-testid="move-mode"
                  onClick={startMoving}
                  title={canMove ? t("moveModeStart") : t("arrangeModeStart")}
                  aria-label={canMove ? t("moveModeStart") : t("arrangeModeStart")}
                  className="text-[var(--kb)]"
                  style={{ backgroundColor: "rgba(var(--kb-rgb),0.10)" }}
                >
                  <PencilSimple size={13} weight="bold" />
                </IconButton>
              )}
              {moving && bulkMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setBulkMenuOpen(false)} />
                  <div
                    className="absolute right-0 top-8 z-50 rounded-xl py-1"
                    style={{
                      backgroundColor: "var(--surface)",
                      border: "1px solid var(--border)",
                      minWidth: 200,
                      maxHeight: "16rem",
                      overflowY: "auto",
                      boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                    }}
                  >
                    {chapterList.map((c) => (
                      <MenuItem
                        key={c.uuid}
                        icon={<FolderSimple size={16} weight="bold" />}
                        label={c.name}
                        disabled={checkedSources.every((s) => chapterOf(s) === c.uuid)}
                        onClick={() => moveChecked(c.uuid)}
                      />
                    ))}
                    <MenuItem
                      icon={<FolderSimple size={16} weight="bold" />}
                      label={t("noChapter")}
                      disabled={checkedSources.every((s) => chapterOf(s) === null)}
                      onClick={() => moveChecked(null)}
                    />
                  </div>
                </>
              )}
            </div>
          </OwnerOnly>
        </div>
      )}

      {/* Source list. Die ganze Liste nimmt gezogene Dateien an, den Rahmen
          dazu gibt es nur waehrend des Ziehens. */}
      <div
        className="relative flex-1 overflow-y-auto transition-colors"
        style={moving ? { backgroundColor: "rgba(var(--kb-rgb),0.05)" } : undefined}
        onDragOver={isOwner ? (e) => { e.preventDefault(); e.stopPropagation(); } : undefined}
        onDragEnter={isOwner ? (e) => { e.preventDefault(); e.stopPropagation(); setDragOver(true); } : undefined}
        onDragLeave={isOwner ? (e) => {
          e.preventDefault(); e.stopPropagation();
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setDragOver(false);
        } : undefined}
        onDrop={isOwner ? (e) => {
          e.preventDefault(); e.stopPropagation(); setDragOver(false);
          const fs = Array.from(e.dataTransfer.files ?? []);
          if (fs.length > 0) onUpload(fs);
        } : undefined}
      >
        {dragOver && (
          <div
            className="absolute inset-1.5 z-30 rounded-xl border-2 border-dashed flex items-center justify-center text-sm font-semibold pointer-events-none"
            style={{
              borderColor: "var(--kb)",
              backgroundColor: "rgba(var(--kb-rgb),0.08)",
              color: "var(--kb)",
            }}
          >
            {t("dropHere")}
          </div>
        )}

        {sources.length === 0 ? (
          <EmptyState
            size="lg"
            icon={
              <span className="flex items-center gap-3">
                <FilePdf size={32} weight="bold" />
                <FileAudio size={32} weight="bold" />
                <FileVideo size={32} weight="bold" />
              </span>
            }
            text={isOwner ? t("emptyHint") : t("emptyHintStudent")}
          />
        ) : (
          <>
            {chapterList.map((chapter, i) => {
              const mine = sources.filter((s) => s.chapter_uuid === chapter.uuid);
              const open = !closedChapters.includes(chapter.uuid);
              return (
                <div key={chapter.uuid}>
                  <ChapterHead
                    chapter={chapter}
                    count={mine.length}
                    selectState={groupState(mine, picked, selectable)}
                    selectDisabled={mine.filter(selectable).length === 0}
                    onToggleSelect={() => toggleGroup(mine)}
                    open={open}
                    isOwner={isOwner}
                    compact={compact}
                    isFirst={i === 0}
                    isLast={i === chapterList.length - 1}
                    menuOpen={menuOpenId === chapter.uuid}
                    onMenuOpen={(o) => setMenuOpenId(o ? chapter.uuid : null)}
                    renaming={renameId === chapter.uuid}
                    onRenameStart={() => setRenameId(chapter.uuid)}
                    onRenameEnd={() => setRenameId(null)}
                    onToggleOpen={() => onToggleChapterOpen(chapter.uuid)}
                    onRename={onRenameChapter ?? (async () => {})}
                    onMove={onMoveChapter ?? (() => {})}
                    onDelete={setDeleteChapterTarget}
                    arranging={moving}
                  />
                  {open && mine.length === 0 && (
                    <p
                      className="px-4 py-3 text-sm"
                      style={{ color: "var(--muted)", borderBottom: "1px solid var(--border)" }}
                    >
                      {t("chapterEmpty")}
                    </p>
                  )}
                  {open && mine.map((src) => renderRow(src, true, mine))}
                </div>
              );
            })}

            {/* Ohne Kapitel bekommt nur dann eine Ueberschrift, wenn es
                ueberhaupt Kapitel gibt. Ohne Gliederung bleibt es die
                schlichte Liste von vorher. */}
            {loose.length > 0 && chapterList.length > 0 && (
              <div
                className="flex items-center gap-2 pl-4 pr-2 py-2"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <GroupCheckbox
                  state={groupState(loose, picked, selectable)}
                  disabled={loose.filter(selectable).length === 0}
                  onToggle={() => toggleGroup(loose)}
                />
                <span className="flex-1 text-sm font-medium truncate" style={{ color: "var(--foreground-soft)" }}>
                  {t("noChapter")}
                </span>
                <span className="text-xs flex-shrink-0" style={{ color: "var(--foreground-soft)" }}>
                  {loose.length}
                </span>
              </div>
            )}
            {loose.map((src) => renderRow(src, chapterList.length > 0, loose))}
          </>
        )}
      </div>

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

      {/* Kapitel loeschen. Andere Warnung als bei der Quelle, weil hier nichts
          verloren geht. */}
      {deleteChapterTarget && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteChapterTitle")}</h3>
            <p className="text-sm text-foreground-soft mb-1 break-all">
              <span className="font-medium">{deleteChapterTarget.name}</span>
            </p>
            <p className="text-sm text-foreground-soft mb-6">
              {t("deleteChapterWarning")}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteChapterTarget(null)}
                className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
              >
                {t("cancel")}
              </button>
              <button
                onClick={() => { onDeleteChapter?.(deleteChapterTarget.uuid); setDeleteChapterTarget(null); }}
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
