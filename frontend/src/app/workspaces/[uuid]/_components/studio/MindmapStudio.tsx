import "mind-elixir/style.css";
import React, { useEffect, useRef, useState } from "react";
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
  Sparkle,
  Trash,
  TreeStructure,
} from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Source, StudentStats } from "../../_types";
import { _getChipIcon, _isMediaFile } from "../../_utils";
import { SubviewHeader, _getToolBadge } from "../layout/SubviewHeader";

export interface MindmapNodeData {
  topic: string;
  children?: MindmapNodeData[];
  source_label?: string;
  page_number?: number | string;
  keyword?: string;
}

export function MindmapStudio({
  mindmap, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, sourceCount,
  sources, onPillClick, stats, breadcrumbs,
  openInViewer, onViewerOpened,
}: {
  mindmap: MindmapNodeData | null;
  loading: boolean;
  onGenerate: () => void;
  onBack: () => void;
  savedList: { id: number; created_at: string | null; topic: string }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  sourceCount: number;
  sources?: Source[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
  openInViewer?: boolean;
  onViewerOpened?: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<HTMLDivElement>(null);
  const meInstanceRef = useRef<any>(null);
  const [view, setView] = useState<"viewer" | "list">(openInViewer ? "viewer" : "list");
  const [allExpanded, setAllExpanded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

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
            const label = isMedia && typeof node.page_number === "string"
              ? node.page_number
              : `S. ${node.page_number}`;
            const esc = node.topic.replace(/&/g, "&amp;").replace(/</g, "&lt;");
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
        scaleVal: 1,
        scaleMin: 0.1,
        scaleMax: 5,
        theme: {
          ...baseTheme,
          name: "kis-mindmap",
          palette: ["var(--kb)", "#0E7490", "#166534", "#A16207", "#534AB7", "#B91C1C"],
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
      const onUp = (ev: PointerEvent) => {
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
          setFullscreenRef.current(false);
          const isMedia = _isMediaFile(src.filename);
          if (isMedia && typeof srcInfo.page_number === "string") {
            // Parse timestamp string "M:SS" or "H:MM:SS" → seconds
            const parts = srcInfo.page_number.split(":").map(Number);
            let startTime = 0;
            if (parts.length === 3) startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
            else if (parts.length === 2) startTime = parts[0] * 60 + parts[1];
            cb(src.uuid, 0, src.filename, srcInfo.keyword || undefined, startTime);
          } else {
            const pageNum = typeof srcInfo.page_number === "number" ? srcInfo.page_number : parseInt(String(srcInfo.page_number), 10) || 0;
            cb(src.uuid, pageNum, src.filename, srcInfo.keyword || undefined);
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

  const activeTopicName = mindmap?.topic ?? "Mindmap";
  const noSources = sourceCount === 0;
  const atLimit = savedList.length >= 20;

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title="Mindmap" onBack={onBack} breadcrumbs={breadcrumbs} />
        <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
          <div className="rounded-xl px-3 py-2 text-xs font-medium flex items-center gap-2"
            style={{
              color: noSources ? "#B91C1C" : sourceCount > 5 ? "#c4820e" : "var(--kb)",
            }}>
            <Files size={13} weight="bold" />
            {noSources
              ? "Keine Quelle ausgewählt"
              : sourceCount === 1
                ? "1 Quelle ausgewählt"
                : sourceCount <= 5
                  ? `${sourceCount} Quellen ausgewählt`
                  : `${sourceCount} Quellen vorhanden, es werden maximal 5 berücksichtigt`}
          </div>

          {savedList.length === 0 && !loading ? (
            <div className="flex flex-col items-center gap-3 pt-[15%]">
              <TreeStructure size={48} weight="duotone" style={{ color: "var(--border)" }} />
              <p className="text-sm text-center" style={{ color: "var(--muted)" }}>Wähle Quellen aus und drücke auf Erstellen.</p>
              <button type="button" onClick={() => onGenerate()}
                disabled={noSources || loading || atLimit}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                <Sparkle size={12} weight="bold" /> Erstellen ({savedList.length}/20)
              </button>
            </div>
          ) : (
            <>
              <div className="flex justify-center">
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                  style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                  <Sparkle size={12} weight="bold" /> Erstellen ({savedList.length}/20)
                </button>
              </div>
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>{savedList.length} {savedList.length === 1 ? "Mindmap" : "Mindmaps"}</span>
              </div>
              <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
                {loading && (
                  <div className="bg-white rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden opacity-70"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <Spinner size="sm" />
                      <span className="text-[12px] font-semibold leading-snug flex-1 line-clamp-2" style={{ color: "var(--text)" }}>Wird generiert…</span>
                    </div>
                  </div>
                )}
                {savedList.map((item) => (
                  <div key={item.id}
                    onClick={() => { onSelect(item.id); setView("viewer"); }}
                    className="bg-white rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group cursor-pointer hover:opacity-80 transition-opacity"
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <TreeStructure size={16} weight="duotone" style={{ color: "var(--kb)", flexShrink: 0 }} />
                      <span className="text-[12px] font-semibold leading-snug flex-1 line-clamp-3 kis-tooltip" style={{ color: "var(--text)" }} data-tip={item.topic}>
                        {item.topic}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-auto pt-1">
                      <span className="text-[10px] font-medium" style={{ color: "var(--muted)" }}>
                        {item.created_at ? new Date(item.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                      </span>
                      <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(item.id); }}
                        className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                        style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                        <Trash size={12} />
                      </button>
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
        ...(fullscreen ? { position: "fixed" as const, inset: 0, zIndex: 9999, backgroundColor: "var(--bg)" } : {}),
      }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => { if (fullscreen) setFullscreen(false); else setView("list"); }}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (() => {
            const badge = _getToolBadge("Mindmap");
            return (
              <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
                {breadcrumbs.map((b, i) => (
                  <React.Fragment key={i}>
                    <button type="button" onClick={b.onClick} className="font-medium shrink-0 transition-colors" style={{ color: "var(--muted)" }} onMouseEnter={(e) => e.currentTarget.style.color = "var(--kb)"} onMouseLeave={(e) => e.currentTarget.style.color = "var(--muted)"}>{b.label}</button>
                    <CaretRight size={10} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" />
                  </React.Fragment>
                ))}
                <button type="button" onClick={() => { if (fullscreen) setFullscreen(false); setView("list"); }} className="font-medium shrink-0 px-1.5 py-0.5 rounded transition-opacity hover:opacity-80" style={badge ? { backgroundColor: badge.bg, color: badge.color } : { color: "var(--muted)" }}>Mindmap</button>
                <CaretRight size={10} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" />
                <span className="font-semibold truncate" style={{ color: "var(--text)" }}>{activeTopicName}</span>
              </div>
            );
          })() : (<span className="text-base font-bold flex-1 truncate" style={{ color: "var(--text)" }}>{activeTopicName}</span>)}
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={handleZoomOut} title="Verkleinern"
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
              <MagnifyingGlassMinus size={13} />
            </button>
            <button type="button" onClick={handleZoomIn} title="Vergrößern"
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
              <MagnifyingGlassPlus size={13} />
            </button>
            <button type="button" onClick={handleToggleExpand} title={allExpanded ? "Alle einklappen" : "Alle ausklappen"}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
              {allExpanded ? <ArrowsInLineVertical size={13} /> : <ArrowsOutLineVertical size={13} />}
            </button>
            <button type="button" onClick={handleFullscreenToggle} title={fullscreen ? "Vollbild beenden" : "Vollbild"}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
              {fullscreen ? <CornersIn size={13} /> : <CornersOut size={13} />}
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-hidden flex flex-col">
          {!mindmap && loading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <Spinner size="lg" />
                <p className="text-xs" style={{ color: "var(--muted)" }}>Mindmap wird generiert…</p>
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
                <div className="flex flex-wrap gap-x-4 gap-y-1 px-4 py-2 flex-shrink-0" style={{ borderTop: "1px solid var(--border)" }}>
                  {Array.from(sourceIndexRef.current.entries()).map(([filename, num]) => (
                    <span key={num} className="text-[11px] leading-snug" style={{ color: "var(--muted)" }}>
                      [{num}] {filename}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
