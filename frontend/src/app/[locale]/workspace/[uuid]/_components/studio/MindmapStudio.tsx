import "mind-elixir/style.css";
import React, { useContext, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import {
  ArrowsInLineVertical,
  ArrowsOutLineVertical,
  CaretLeft,
  CaretRight,
  CornersIn,
  CornersOut,
  Files,
  MagnifyingGlassMinus,
  MagnifyingGlassPlus,
  PencilSimple,
  SidebarSimple,
  Sparkle,
  Trash,
  TreeStructure,
} from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { InlineRename } from "@/components/ui/InlineRename";
import type { Source } from "../../_types";
import { _isMediaFile } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { STUDIO_ITEM_MAX } from "../../_constants";
import { SubviewHeader, _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";
import { chipTargetKey, getActiveChipTarget, setActiveChipTarget, subscribeActiveChip } from "../chat/_citations";
import { StudioSourceLegend } from "./StudioSourceLegend";
import { InstructionNote } from "./InstructionField";
import { GenerateModal } from "./GenerateModal";

// A source label rarely matches a filename exactly, so fall back to a loose match.
function _findSource(sources: Source[], label: string): Source | undefined {
  const lower = label.toLowerCase();
  return sources.find((s) => s.filename === label)
    ?? sources.find((s) => s.filename.toLowerCase() === lower)
    ?? sources.find((s) => lower.includes(s.filename.toLowerCase()) || s.filename.toLowerCase().includes(lower));
}

// Turns a timestamp label "M:SS" or "H:MM:SS" into seconds.
function _labelSeconds(label: string): number {
  const parts = label.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

// The chip key has to match the one the chat chips use, both mark the same target.
function _chipKey(src: Source, pageNumber: number | string | undefined): string {
  if (_isMediaFile(src.filename) && typeof pageNumber === "string") {
    return chipTargetKey(src.uuid, 0, _labelSeconds(pageNumber));
  }
  const page = typeof pageNumber === "number" ? pageNumber : parseInt(String(pageNumber), 10) || 0;
  return chipTargetKey(src.uuid, page, undefined);
}

export interface MindmapNodeData {
  topic: string;
  children?: MindmapNodeData[];
  source_label?: string;
  page_number?: number | string;
  keyword?: string;
}

export function MindmapStudio({
  mindmap, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, onRename, sourceCount,
  sources, pickedSources, onPillClick, breadcrumbs,
  openInViewer, onViewerOpened, instruction, instructionUnmatched,
}: {
  mindmap: MindmapNodeData | null;
  loading: boolean;
  onGenerate: (instruction: string) => void;
  onBack: () => void;
  savedList: { id: number; created_at: string | null; topic: string; user_instruction?: string }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onRename?: (id: number, title: string) => Promise<void>;
  sourceCount: number;
  sources?: Source[];
  /** What the user ticked when this map was made, used ones and unused ones. */
  pickedSources?: { number: number; filename: string }[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  openInViewer?: boolean;
  onViewerOpened?: () => void;
  /** The instruction the shown map was made with, and whether the sources had nothing on it. */
  instruction?: string;
  instructionUnmatched?: boolean;
}) {
  const t = useTranslations("workspace.detail.studio");
  const tMm = useTranslations("workspace.detail.studio.mindmap");
  // The create dialog with the instruction field, opened by the Create button.
  const [dialogOpen, setDialogOpen] = useState(false);
  const locale = useLocale();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const meInstanceRef = useRef<any>(null);
  const [view, setView] = useState<"viewer" | "list">(openInViewer ? "viewer" : "list");
  // Which card is currently being renamed, only one, nobody needs more at once.
  const [umbenennt, setUmbenennt] = useState<number | null>(null);
  const [allExpanded, setAllExpanded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const minimize = useContext(MinimizeContext);

  useEffect(() => {
    if (openInViewer) {
      setView("viewer");
      onViewerOpened?.();
    }
  }, [openInViewer, onViewerOpened]);

  // Leaves the browser full screen too, not just the CSS overlay.
  async function leaveFullscreen() {
    if (document.fullscreenElement) {
      try { await document.exitFullscreen(); } catch { /* ignore */ }
    }
    const orientation = screen.orientation as ScreenOrientation & { unlock?: () => void };
    orientation?.unlock?.();
    setFullscreen(false);
  }

  // Full screen with an orientation lock, otherwise plain CSS full screen.
  async function handleFullscreenToggle() {
    const el = viewerRef.current;
    if (!fullscreen) {
      if (el?.requestFullscreen) {
        try { await el.requestFullscreen(); } catch { /* user gesture or permission denied */ }
      }
      const orientation = screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> };
      if (orientation?.lock) {
        try { await orientation.lock("landscape"); } catch { /* desktop or unsupported */ }
      }
      setFullscreen(true);
    } else {
      await leaveFullscreen();
    }
  }

  // Release the lock, even when full screen is left another way.
  useEffect(() => {
    function unlockOrientation() {
      const o = screen.orientation as ScreenOrientation & { unlock?: () => void };
      o?.unlock?.();
    }
    function onChange() {
      if (!document.fullscreenElement) {
        setFullscreen(false);
        unlockOrientation();
      }
    }
    document.addEventListener("fullscreenchange", onChange);
    return () => {
      document.removeEventListener("fullscreenchange", onChange);
      unlockOrientation();
    };
  }, []);

  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;
  const onPillClickRef = useRef(onPillClick);
  onPillClickRef.current = onPillClick;
  const nodeClickCleanupRef = useRef<(() => void) | null>(null);
  const setFullscreenRef = useRef(setFullscreen);
  setFullscreenRef.current = setFullscreen;
  const nodeSourceMapRef = useRef(new Map<string, { source_label: string; page_number?: number | string; keyword?: string; topic: string }>());
  const sourceIndexRef = useRef(new Map<string, number>());
  const usedNamesRef = useRef(new Set<string>());

  // Frames the chip that was clicked last, the same mark the chat chips carry.
  function paintActiveChip() {
    const active = getActiveChipTarget();
    containerRef.current?.querySelectorAll<HTMLElement>(".mm-src-chip").forEach((chip) => {
      chip.classList.toggle("mm-src-chip--active", !!active && chip.dataset.chipTarget === active);
    });
  }

  useEffect(() => subscribeActiveChip(() => paintActiveChip()), []);

  function expandAll(node: any) {
    if (node.children && node.children.length > 0) {
      node.expanded = true;
      node.children.forEach(expandAll);
    }
  }
  function collapseAll(me: any) {
    const root = me.nodeData;
    function collapseDeep(node: any) {
      if (node.children && node.children.length > 0) {
        node.expanded = false;
        node.children.forEach(collapseDeep);
      }
    }
    if (root.children) {
      root.children.forEach(collapseDeep);
    }
  }

  function handleToggleExpand() {
    const me = meInstanceRef.current;
    if (!me) return;
    if (allExpanded) {
      collapseAll(me);
    } else {
      expandAll(me.nodeData);
    }
    me.refresh();
    me.toCenter();
    paintActiveChip();
    setAllExpanded(!allExpanded);
  }

  function handleZoomIn() {
    const me = meInstanceRef.current;
    if (!me) return;
    me.scale((me.scaleVal || 1) * 1.4);
  }

  function handleZoomOut() {
    const me = meInstanceRef.current;
    if (!me) return;
    me.scale((me.scaleVal || 1) * 0.6);
  }

  useEffect(() => {
    if (!mindmap || !containerRef.current || view !== "viewer") return;

    let cancelled = false;

    (async () => {
      const MindElixir = (await import("mind-elixir")).default;
      if (cancelled || !containerRef.current) return;

      // Build source index: filename → [N]
      // Numbered the way the user ticked, the same rule the data table follows.
      const sourceIndexMap = new Map<string, number>();
      for (const s of pickedSources || []) {
        if (!sourceIndexMap.has(s.filename)) sourceIndexMap.set(s.filename, s.number);
      }
      const benutzteNamen = new Set<string>();
      function collectSources(node: MindmapNodeData) {
        if (node.source_label) {
          benutzteNamen.add(node.source_label);
          // Older maps carry no picked list, then the tree order numbers them.
          if (!sourceIndexMap.has(node.source_label)) {
            sourceIndexMap.set(node.source_label, sourceIndexMap.size + 1);
          }
        }
        node.children?.forEach(collectSources);
      }
      collectSources(mindmap);
      sourceIndexRef.current = sourceIndexMap;
      usedNamesRef.current = benutzteNamen;

      let nid = 0;
      nodeSourceMapRef.current = new Map();
      function convert(node: MindmapNodeData): any {
        const id = `node-${nid++}`;
        const result: any = { id, topic: node.topic };
        if (node.source_label) {
          nodeSourceMapRef.current.set(id, { source_label: node.source_label, page_number: node.page_number, keyword: node.keyword, topic: node.topic });
          const srcNum = sourceIndexMap.get(node.source_label);
          if (srcNum) {
            // Without a verified spot the chip names the file alone, it still opens it.
            const isMedia = _isMediaFile(node.source_label);
            const rawLabel = node.page_number == null
              ? ""
              : isMedia && typeof node.page_number === "string"
                ? node.page_number
                : tMm("pageLabel", { page: node.page_number });
            const esc = node.topic.replace(/&/g, "&amp;").replace(/</g, "&lt;");
            // The chip label is escaped too, it ends up in innerHTML.
            const label = String(rawLabel).replace(/&/g, "&amp;").replace(/</g, "&lt;");
            const chipSrc = sourcesRef.current ? _findSource(sourcesRef.current, node.source_label) : undefined;
            const keyAttr = chipSrc ? ` data-chip-target="${_chipKey(chipSrc, node.page_number)}"` : "";
            result.dangerouslySetInnerHTML =
              `${esc} <span class="mm-src-chip"${keyAttr}>[${srcNum}]${label ? ` ${label}` : ""}</span>`;
          }
        }
        if (node.children && node.children.length > 0) {
          result.children = node.children.map(convert);
        }
        return result;
      }

      containerRef.current.innerHTML = "";

      const baseTheme = MindElixir.THEME;
      const me = new MindElixir({
        el: containerRef.current,
        direction: MindElixir.SIDE,
        editable: false,
        contextMenu: false,
        toolBar: false,
        keypress: false,
        allowUndo: false,
        scaleMin: 0.1,
        scaleMax: 5,
        theme: {
          ...baseTheme,
          name: "kis-mindmap",
          palette: ["var(--mm-c1)", "var(--mm-c2)", "var(--mm-c3)", "var(--mm-c4)", "var(--mm-c5)", "var(--mm-c6)"],
        },
      });

      me.init({ nodeData: convert(mindmap) });

      collapseAll(me);
      me.refresh();
      me.toCenter();

      // Click via pointer events, because the map shifts on every movement.
      let downTpc: HTMLElement | null = null;
      let downX = 0;
      let downY = 0;
      const CLICK_THRESHOLD = 6;
      const onDown = (ev: PointerEvent) => {
        if (ev.button !== 0) return;
        const tpc = (ev.target as HTMLElement).closest("me-tpc") as any;
        if (!tpc) { downTpc = null; return; }
        downTpc = tpc;
        downX = ev.clientX;
        downY = ev.clientY;
      };
      const onUp = async (ev: PointerEvent) => {
        if (!downTpc || ev.button !== 0) return;
        const dx = ev.clientX - downX;
        const dy = ev.clientY - downY;
        if (dx * dx + dy * dy > CLICK_THRESHOLD * CLICK_THRESHOLD) { downTpc = null; return; }
        const tpc = downTpc as any;
        downTpc = null;
        const nId = tpc.nodeObj?.id;
        if (!nId) return;
        const srcInfo = nodeSourceMapRef.current.get(nId);
        if (!srcInfo) return;
        const srcs = sourcesRef.current;
        const cb = onPillClickRef.current;
        if (!srcs || !cb) return;
        const src = _findSource(srcs, srcInfo.source_label);
        if (src) {
          setActiveChipTarget(_chipKey(src, srcInfo.page_number));
          paintActiveChip();
          // Leave full screen, otherwise the sources panel stays invisible.
          if (document.fullscreenElement) {
            try { await document.exitFullscreen(); } catch { /* ignore */ }
          }
          const orientation = screen.orientation as ScreenOrientation & { unlock?: () => void };
          orientation?.unlock?.();
          setFullscreenRef.current(false);
          const isMedia = _isMediaFile(src.filename);
          if (isMedia && typeof srcInfo.page_number === "string") {
            cb(src.uuid, 0, src.filename, undefined, _labelSeconds(srcInfo.page_number));
          } else {
            const pageNum = typeof srcInfo.page_number === "number" ? srcInfo.page_number : parseInt(String(srcInfo.page_number), 10) || 0;
            // Keyword and topic together name the passage to mark.
            cb(src.uuid, pageNum, src.filename, [srcInfo.keyword, srcInfo.topic].filter(Boolean).join(" "));
          }
        }
      };
      containerRef.current.addEventListener("pointerdown", onDown);
      containerRef.current.addEventListener("pointerup", onUp);
      nodeClickCleanupRef.current = () => {
        containerRef.current?.removeEventListener("pointerdown", onDown);
        containerRef.current?.removeEventListener("pointerup", onUp);
      };

      meInstanceRef.current = me;
    })();

    return () => {
      cancelled = true;
      nodeClickCleanupRef.current?.();
      nodeClickCleanupRef.current = null;
      if (meInstanceRef.current) {
        try { meInstanceRef.current.destroy?.(); } catch { /* ignore */ }
      }
      meInstanceRef.current = null;
      if (containerRef.current) containerRef.current.innerHTML = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mindmap, view, pickedSources]);

  const activeTopicName = mindmap?.topic ?? tMm("fallbackTopic");
  const noSources = sourceCount === 0;
  const atLimit = savedList.length >= STUDIO_ITEM_MAX;

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title={tMm("title")} toolKey="Mindmap" onBack={onBack} breadcrumbs={breadcrumbs} />
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="rounded-xl px-3 py-2 text-sm font-medium flex items-center gap-2"
            style={{
              color: noSources ? "var(--error-strong)" : "var(--kb)",
            }}>
            <Files size={13} weight="bold" />
            {noSources
              ? t("sources.none")
              : sourceCount === 1
                ? t("sources.one")
                : t("sources.few", { n: sourceCount })}
          </div>

          {dialogOpen && (
            <GenerateModal id="mindmap-instruction" toolName={tMm("title")}
              onClose={() => setDialogOpen(false)}
              onCreate={(text) => { setDialogOpen(false); onGenerate(text); }} />
          )}
          {savedList.length === 0 && !loading ? (
            <EmptyState
              className="pt-[15%]"
              size="lg"
              icon={<TreeStructure size={48} weight="bold" />}
              text={tMm("emptyHint")}
              action={
                <span title={atLimit ? t("generate.limitReached") : undefined}>
                  <button type="button" onClick={() => setDialogOpen(true)}
                    disabled={noSources || loading || atLimit}
                    className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                    <Sparkle size={12} weight="bold" /> {t("generate.create")}
                  </button>
                </span>
              }
            />
          ) : (
            <>
              <div className="flex justify-center">
                <span title={atLimit ? t("generate.limitReached") : undefined}>
                  <button type="button" onClick={() => setDialogOpen(true)}
                    disabled={noSources || loading || atLimit}
                    className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                    <Sparkle size={12} weight="bold" /> {t("generate.create")}
                  </button>
                </span>
              </div>
              <div className="flex items-center justify-between px-1">
                <span className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>{savedList.length} {savedList.length === 1 ? tMm("countOne") : tMm("countMany")}</span>
              </div>
              <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
                {loading && (
                  <div className="bg-background rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden opacity-70"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Spinner size="sm" />
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-2" style={{ color: "var(--foreground)" }}>{t("generate.generating")}</span>
                    </div>
                  </div>
                )}
                {savedList.map((item) => (
                  <div key={item.id}
                    onClick={() => { onSelect(item.id); setView("viewer"); }}
                    className="bg-background rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group cursor-pointer hover:outline-2 hover:outline-[var(--kb)] -outline-offset-2 transition"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <TreeStructure size={16} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
                      {umbenennt === item.id && onRename ? (
                        <InlineRename
                          value={item.topic}
                          errorText={t("common.renameFailed")}
                          onSave={(next) => onRename(item.id, next)}
                          onCancel={() => setUmbenennt(null)}
                        />
                      ) : (
                        <span className="text-sm font-semibold leading-snug flex-1 line-clamp-3 kis-tooltip" style={{ color: "var(--foreground)" }}
                          onDoubleClick={(e) => { if (onRename) { e.stopPropagation(); setUmbenennt(item.id); } }}
                          data-tip={item.topic}>
                          {item.topic}
                        </span>
                      )}
                    </div>
                    {item.user_instruction && (
                      <span className="text-xs text-muted line-clamp-1" title={item.user_instruction}>
                        {t("generate.instructionShown", { text: item.user_instruction })}
                      </span>
                    )}
                    <div className="flex items-center justify-between mt-auto pt-1">
                      <span className="text-xs font-medium" >
                        {item.created_at ? new Date(item.created_at).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {onRename && (
                          <button type="button" onClick={(e) => { e.stopPropagation(); setUmbenennt(item.id); }}
                            className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                            style={{ backgroundColor: "var(--surface-dim)" }}
                            title={t("common.rename")}
                            aria-label={t("common.rename")}>
                            <PencilSimple size={12} />
                          </button>
                        )}
                        <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                          className="w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                          style={{ backgroundColor: "var(--surface-dim)" }}>
                          <Trash size={12} />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── Mindmap Viewer ── */}
      <div ref={viewerRef} style={{
        display: view === "viewer" ? "flex" : "none",
        ...(fullscreen ? { position: "fixed" as const, inset: 0, zIndex: 9999, backgroundColor: "var(--background)" } : {}),
      }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => { if (fullscreen) void leaveFullscreen(); else setView("list"); }}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (() => {
            const badge = _getToolBadge("Mindmap");
            return (
              <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
                {breadcrumbs.map((b, i) => (
                  <React.Fragment key={i}>
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 text-muted hover:text-kb transition-colors">{b.label}</button>
                    <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
                  </React.Fragment>
                ))}
                <button type="button" onClick={() => { if (fullscreen) void leaveFullscreen(); setView("list"); }} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={badge ? { color: badge.color } : {  }}>{tMm("title")}</button>
                <CaretRight size={10} weight="bold" style={{ opacity: 0.5 }} className="shrink-0" />
                <span className="font-semibold truncate" style={{ color: "var(--foreground)" }}>{activeTopicName}</span>
              </div>
            );
          })() : (<span className="text-base font-bold flex-1 truncate" style={{ color: "var(--foreground)" }}>{activeTopicName}</span>)}
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={handleZoomOut} title={tMm("zoomOut")}
              className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
              style={{ backgroundColor: "var(--surface-dim)" }}>
              <MagnifyingGlassMinus size={13} />
            </button>
            <button type="button" onClick={handleZoomIn} title={tMm("zoomIn")}
              className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
              style={{ backgroundColor: "var(--surface-dim)" }}>
              <MagnifyingGlassPlus size={13} />
            </button>
            <button type="button" onClick={handleToggleExpand} title={allExpanded ? tMm("collapseAll") : tMm("expandAll")}
              className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
              style={{ backgroundColor: "var(--surface-dim)" }}>
              {allExpanded ? <ArrowsInLineVertical size={13} /> : <ArrowsOutLineVertical size={13} />}
            </button>
            <button type="button" onClick={handleFullscreenToggle} title={fullscreen ? tMm("exitFullscreen") : tMm("fullscreen")}
              className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
              style={{ backgroundColor: "var(--surface-dim)" }}>
              {fullscreen ? <CornersIn size={13} /> : <CornersOut size={13} />}
            </button>
            {minimize && (
              <button type="button" onClick={minimize} title={t("minimizePanel")}
                className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
                style={{ backgroundColor: "var(--surface-dim)" }}>
                <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
              </button>
            )}
          </div>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col">
          {mindmap && (instruction || instructionUnmatched) && (
            <div className="px-4 pt-3">
              <InstructionNote instruction={instruction} unmatched={instructionUnmatched}
                shownText={t("generate.instructionShown", { text: instruction || "" })}
                unmatchedText={t("generate.instructionUnmatched")} />
            </div>
          )}
          {!mindmap && loading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Spinner size="lg" />
                <p className="text-sm" >{tMm("loadingViewer")}</p>
              </div>
            </div>
          )}
          {mindmap && (
            <>
              <div
                ref={containerRef}
                className="flex-1"
                style={{ minHeight: 300 }}
              />
              {(() => {
                const eintraege = (pickedSources && pickedSources.length > 0)
                  ? pickedSources
                  : Array.from(sourceIndexRef.current.entries())
                      .map(([filename, number]) => ({ number, filename }));
                if (eintraege.length === 0) return null;
                return (
                <StudioSourceLegend
                  count={eintraege.length}
                  className="px-4 py-2 flex-shrink-0"
                  listClassName="flex flex-wrap gap-x-4 gap-y-1 pl-4"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  {eintraege.map((s) => (
                    <span key={s.number}
                          className={`text-xs leading-snug text-[var(--muted)]${usedNamesRef.current.has(s.filename) ? "" : " opacity-60"}`}>
                      [{s.number}] {s.filename}
                    </span>
                  ))}
                </StudioSourceLegend>
                );
              })()}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
