import "mind-elixir/style.css";
import React, { useContext, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
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
import { _getChipIcon, _isMediaFile } from "../../_utils";
import { MinimizeContext } from "../../_context";
import { SubviewHeader, _getToolBadge, type BreadcrumbItem } from "../layout/SubviewHeader";
import { StudioSourceLegend } from "./StudioSourceLegend";

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
  sources, onPillClick, breadcrumbs,
  openInViewer, onViewerOpened,
}: {
  mindmap: MindmapNodeData | null;
  loading: boolean;
  onGenerate: () => void;
  onBack: () => void;
  savedList: { id: number; created_at: string | null; topic: string }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  onRename?: (id: number, title: string) => Promise<void>;
  sourceCount: number;
  sources?: Source[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  breadcrumbs?: BreadcrumbItem[];
  openInViewer?: boolean;
  onViewerOpened?: () => void;
}) {
  const t = useTranslations("workspace.detail.studio");
  const tMm = useTranslations("workspace.detail.studio.mindmap");
  const locale = useLocale();
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const meInstanceRef = useRef<any>(null);
  const [view, setView] = useState<"viewer" | "list">(openInViewer ? "viewer" : "list");
  // Welche Karte gerade umbenannt wird. Nur eine, mehr braucht niemand gleichzeitig.
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

  // Enter/exit native browser fullscreen and lock orientation to landscape
  // on mobile. Falls back to pure CSS fullscreen if the API is unavailable.
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
      if (document.fullscreenElement) {
        try { await document.exitFullscreen(); } catch { /* ignore */ }
      }
      const orientation = screen.orientation as ScreenOrientation & { unlock?: () => void };
      orientation?.unlock?.();
      setFullscreen(false);
    }
  }

  // Sync fullscreen state and release orientation lock if user exits via ESC,
  // system gesture, or unmounts — otherwise device stays locked in landscape.
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
  const nodeSourceMapRef = useRef(new Map<string, { source_label: string; page_number: number | string; keyword?: string }>());
  const sourceIndexRef = useRef(new Map<string, number>());

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
      const sourceIndexMap = new Map<string, number>();
      function collectSources(node: MindmapNodeData) {
        if (node.source_label && !sourceIndexMap.has(node.source_label)) {
          sourceIndexMap.set(node.source_label, sourceIndexMap.size + 1);
        }
        node.children?.forEach(collectSources);
      }
      collectSources(mindmap);
      sourceIndexRef.current = sourceIndexMap;

      let nid = 0;
      nodeSourceMapRef.current = new Map();
      function convert(node: MindmapNodeData): any {
        const id = `node-${nid++}`;
        const result: any = { id, topic: node.topic };
        if (node.source_label && node.page_number != null) {
          nodeSourceMapRef.current.set(id, { source_label: node.source_label, page_number: node.page_number, keyword: node.keyword });
          const srcNum = sourceIndexMap.get(node.source_label);
          if (srcNum) {
            const isMedia = _isMediaFile(node.source_label);
            const rawLabel = isMedia && typeof node.page_number === "string"
              ? node.page_number
              : tMm("pageLabel", { page: node.page_number ?? 0 });
            const esc = node.topic.replace(/&/g, "&amp;").replace(/</g, "&lt;");
            // Escape the chip label too (defense in depth, consistent with the
            // topic above) since it is interpolated into innerHTML below.
            const label = String(rawLabel).replace(/&/g, "&amp;").replace(/</g, "&lt;");
            const IconComp = _getChipIcon(node.source_label);
            const icon = renderToStaticMarkup(
              React.createElement(IconComp, {
                size: 8,
                weight: "bold",
                style: { verticalAlign: "-1px", flexShrink: 0 },
              })
            );
            result.dangerouslySetInnerHTML =
              `${esc} <span class="mm-src-chip">${icon} [${srcNum}] ${label}</span>`;
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

      // Node click → open source: use pointerdown/pointerup with move threshold
      // because mind-elixir pans on any mouse movement which shifts the DOM nodes,
      // causing the browser click target to miss the me-tpc element.
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
        const label = srcInfo.source_label.toLowerCase();
        const src = srcs.find((s) => s.filename === srcInfo.source_label)
          ?? srcs.find((s) => s.filename.toLowerCase() === label)
          ?? srcs.find((s) => label.includes(s.filename.toLowerCase()) || s.filename.toLowerCase().includes(label));
        if (src) {
          // Exit native browser fullscreen, otherwise the viewer container stays
          // in element fullscreen and the source panel in the workspace is not visible
          // (black borders + state mismatch).
          if (document.fullscreenElement) {
            try { await document.exitFullscreen(); } catch { /* ignore */ }
          }
          const orientation = screen.orientation as ScreenOrientation & { unlock?: () => void };
          orientation?.unlock?.();
          setFullscreenRef.current(false);
          const isMedia = _isMediaFile(src.filename);
          if (isMedia && typeof srcInfo.page_number === "string") {
            // Parse timestamp string "M:SS" or "H:MM:SS" → seconds
            const parts = srcInfo.page_number.split(":").map(Number);
            let startTime = 0;
            if (parts.length === 3) startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
            else if (parts.length === 2) startTime = parts[0] * 60 + parts[1];
            cb(src.uuid, 0, src.filename, undefined, startTime);
          } else {
            const pageNum = typeof srcInfo.page_number === "number" ? srcInfo.page_number : parseInt(String(srcInfo.page_number), 10) || 0;
            cb(src.uuid, pageNum, src.filename, undefined);
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
  }, [mindmap, view]);

  const activeTopicName = mindmap?.topic ?? tMm("fallbackTopic");
  const noSources = sourceCount === 0;
  const atLimit = savedList.length >= 20;

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title={tMm("title")} toolKey="Mindmap" onBack={onBack} breadcrumbs={breadcrumbs} />
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="rounded-xl px-3 py-2 text-sm font-medium flex items-center gap-2"
            style={{
              color: noSources ? "var(--error-strong)" : sourceCount > 5 ? "#c4820e" : "var(--kb)",
            }}>
            <Files size={13} weight="bold" />
            {noSources
              ? t("sources.none")
              : sourceCount === 1
                ? t("sources.one")
                : sourceCount <= 5
                  ? t("sources.few", { n: sourceCount })
                  : t("sources.tooMany", { n: sourceCount })}
          </div>

          {savedList.length === 0 && !loading ? (
            <EmptyState
              className="pt-[15%]"
              size="lg"
              icon={<TreeStructure size={48} weight="bold" />}
              text={tMm("emptyHint")}
              action={
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                  <Sparkle size={12} weight="bold" /> {t("generate.createCount", { current: savedList.length, max: 20 })}
                </button>
              }
            />
          ) : (
            <>
              <div className="flex justify-center">
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="btn-outline-accent inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all disabled:opacity-40">
                  <Sparkle size={12} weight="bold" /> {t("generate.createCount", { current: savedList.length, max: 20 })}
                </button>
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
          <button type="button" onClick={() => { if (fullscreen) setFullscreen(false); else setView("list"); }}
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
                <button type="button" onClick={() => { if (fullscreen) setFullscreen(false); setView("list"); }} className="font-medium shrink-0 px-1.5 py-0.5 rounded opacity-60 hover:opacity-100 transition-opacity" style={badge ? { color: badge.color } : {  }}>{tMm("title")}</button>
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
              {sourceIndexRef.current.size > 0 && (
                <StudioSourceLegend
                  count={sourceIndexRef.current.size}
                  className="px-4 py-2 flex-shrink-0"
                  listClassName="flex flex-wrap gap-x-4 gap-y-1 pl-4"
                  style={{ borderTop: "1px solid var(--border)" }}
                >
                  {Array.from(sourceIndexRef.current.entries()).map(([filename, num]) => (
                    <span key={num} className="text-xs leading-snug text-[var(--muted)]">
                      [{num}] {filename}
                    </span>
                  ))}
                </StudioSourceLegend>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
