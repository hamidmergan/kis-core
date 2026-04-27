import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CaretLeft, SidebarSimple } from "@phosphor-icons/react";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";
import type { ViewerState } from "../../_types";
import { FileIcon } from "../sources/FileIcon";

import { EMBEDPDF_ICON_MAP } from "./_icons";
import { wrapEngineGeometry } from "./_geometry";
import { doHighlightSearch, type HighlightRefs } from "./_highlight";
import { copyTextFromPromise } from "@/lib/clipboard";


export function PdfViewer({
  source, onClose, moduleUuid, onAskWithSelection, onCustomQuestion, popupActions, onMinimize, onAddToGlossary,
}: {
  source: ViewerState;
  onClose: () => void;
  moduleUuid: string;
  onAskWithSelection?: (text: string, sourceInfo: { uuid: string; filename: string; page: number; selectedText?: string }) => void;
  onCustomQuestion?: (selectedText: string) => void;
  popupActions?: { key: string; label: string; icon: string; prompt: string; min_words: number }[];
  onMinimize?: () => void;
  onAddToGlossary?: (text: string, sourceUuid: string, page: number) => void;
}) {
  const [page, setPage] = useState(source.page);
  const [showAnnotations, setShowAnnotations] = useState(false);
  const [pageSummaries, setPageSummaries] = useState<Record<number, string>>({});
  const [summariesStatus, setSummariesStatus] = useState<string>("none");
  const [summariesLoaded, setSummariesLoaded] = useState(false);
  const [sidebarTarget, setSidebarTarget] = useState<Element | null>(null);
  const [registryReady, setRegistryReady] = useState(false);
  const viewerRef = useRef<PDFViewerRef>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const themeModeRef = useRef<"light" | "dark">(
    (typeof window !== "undefined" && window.localStorage?.getItem("kis.pdf-theme") === "dark") ? "dark" : "light",
  );
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const registryRef = useRef<any>(null);
  const sourcePageRef = useRef(source.page);
  sourcePageRef.current = source.page;
  // Stable refs so command actions always have latest values without re-initializing EmbedPDF
  const sourceRef = useRef(source);
  sourceRef.current = source;
  const onAskWithSelectionRef = useRef(onAskWithSelection);
  onAskWithSelectionRef.current = onAskWithSelection;
  const onCustomQuestionRef = useRef(onCustomQuestion);
  onCustomQuestionRef.current = onCustomQuestion;
  const onAddToGlossaryRef = useRef(onAddToGlossary);
  onAddToGlossaryRef.current = onAddToGlossary;
  const popupActionsRef = useRef(popupActions);
  popupActionsRef.current = popupActions;

  // Block EmbedPDF's document-level Ctrl+C handler when focus is outside the viewer
  // so native copy works in chat / tools panels
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "c" || e.key === "C") && (e.ctrlKey || e.metaKey)) {
        // window.getSelection() only sees selections outside shadow DOM.
        // If text is selected outside (chat/tools) → block EmbedPDF, let native copy run.
        // If empty → selection is likely inside EmbedPDF's shadow DOM → let EmbedPDF handle it.
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) {
          e.stopImmediatePropagation();
        }
      }
    };
    document.addEventListener("keydown", handler, true); // capture phase
    return () => document.removeEventListener("keydown", handler, true);
  }, []);

  // Watch for EmbedPDF summary sidebar DOM (shadow root) to sync React state + portal target
  useEffect(() => {
    if (!registryReady) return;
    const embedEl = containerRef.current?.querySelector("embedpdf-container");
    const shadow = embedEl?.shadowRoot;
    if (!shadow) return;
    const check = () => {
      const el = shadow.querySelector('[data-sidebar-id="summary-panel"]');
      setSidebarTarget(prev => (el === prev ? prev : (el as Element | null)));
      setShowAnnotations(!!el);
    };
    check();
    const obs = new MutationObserver(check);
    obs.observe(shadow, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, [registryReady]);

  // Lazy-fetch summaries when toggle is activated, poll while generating
  useEffect(() => {
    if (!showAnnotations) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const fetchSummaries = async () => {
      try {
        const res = await fetch(
          `/api/ki-assistent/modules/${moduleUuid}/sources/${source.uuid}/summaries`,
          { credentials: "include" },
        );
        if (res.ok && !cancelled) {
          const data = await res.json();
          setSummariesStatus(data.status);
          const pages: Record<number, string> = {};
          if (data.pages) {
            for (const [k, v] of Object.entries(data.pages)) pages[Number(k)] = v as string;
            setPageSummaries(pages);
          }
          if (data.status === "generating") {
            timer = setTimeout(fetchSummaries, 10000);
          } else {
            setSummariesLoaded(true);
          }
        }
      } catch { /* ignore */ }
    };
    if (!summariesLoaded) fetchSummaries();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [showAnnotations, summariesLoaded, moduleUuid, source.uuid]);

  // Scroll to page + highlight text when nonce changes (pill click on same document)
  const pendingHighlightRef = useRef<{ page: number; text: string; exact?: boolean } | null>(null);
  const prevHighlightRef = useRef<{ pageIndex: number; ids: string[] } | null>(null);
  const highlightRefs: HighlightRefs = { prevHighlightRef };

  // When the document changes, the inner PDFViewer remounts (keyed by uuid) but this
  // outer component does not — so registryRef still points at the previous document's
  // registry. Reset it so the highlight effect below defers until the new registry is
  // ready via onLayoutReady, instead of firing search on a stale registry.
  const loadedUuidRef = useRef<string | null>(null);
  useEffect(() => {
    if (loadedUuidRef.current !== source.uuid) {
      loadedUuidRef.current = source.uuid;
      registryRef.current = null;
      setRegistryReady(false);
    }
  }, [source.uuid]);

  useEffect(() => {
    if (source.nonce == null) return;
    const reg = registryRef.current;
    if (!reg) {
      // Viewer not ready yet — save for later
      if (source.highlightText) {
        pendingHighlightRef.current = { page: source.page, text: source.highlightText, exact: !!source.exactSelection };
      }
      return;
    }

    if (source.highlightText) {
      doHighlightSearch(highlightRefs, reg, source.page, source.highlightText, !!source.exactSelection);
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const scroll = (reg as any).getPlugin?.("scroll")?.provides?.();
      scroll?.scrollToPage?.({ pageNumber: source.page, behavior: "instant", alignY: 50 });
    }

  }, [source.nonce, source.page, source.highlightText, source.exactSelection]);

  const handleReady = useCallback((registry: unknown) => {
    registryRef.current = registry;
    setRegistryReady(true);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const reg = registry as any;

    // Fix oversized selection highlights on PDFs with inflated font bbox
    // (e.g. LibreOffice-embedded Cambria). See wrapEngineGeometry above.
    wrapEngineGeometry(reg.getEngine?.());

    // On touch devices the Pan plugin activates "panMode" as the default
    // interaction mode. The Selection plugin only ships rect-rendering
    // config for "pointerMode", so in panMode SelectionLayer never
    // receives rects — chip highlights scroll-to-page but stay invisible.
    // Enable rect rendering for panMode without enabling drag-to-select,
    // so mobile keeps drag-to-pan while programmatic highlights display.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const selCap = reg.getPlugin?.("selection")?.provides?.() as any;
    try {
      selCap?.enableForMode?.("panMode", { enableSelection: false, showSelectionRects: true });
    } catch { /* ignore */ }

    // Match scrollbar width to app (5px instead of default 8px)
    const injectScrollbarStyle = () => {
      const embedEl = containerRef.current?.querySelector("embedpdf-container");
      const shadow = embedEl?.shadowRoot;
      if (shadow && !shadow.querySelector("[data-kis-scrollbar]")) {
        const s = document.createElement("style");
        s.setAttribute("data-kis-scrollbar", "");
        s.textContent = `
          :host *::-webkit-scrollbar { width: 5px !important; height: 5px !important; }
          :host *::-webkit-scrollbar-track { background: transparent !important; }
          :host *::-webkit-scrollbar-thumb { background: #d8d8d8 !important; border-radius: 999px !important; }
          :host *::-webkit-scrollbar-thumb:hover { background: #bbb !important; }
          :host * { scrollbar-width: thin !important; scrollbar-color: #d8d8d8 transparent !important; }
        `;
        shadow.appendChild(s);
        return true;
      }
      return false;
    };
    if (!injectScrollbarStyle()) {
      // Shadow DOM might not be ready yet — retry briefly
      const t = setInterval(() => { if (injectScrollbarStyle()) clearInterval(t); }, 100);
      setTimeout(() => clearInterval(t), 3000);
    }

    // Track current page
    const scroll = reg.getPlugin?.("scroll")?.provides?.();
    if (scroll) {
      scroll.onPageChange(({ pageNumber }: { pageNumber: number }) => setPage(pageNumber));
      const unsub = scroll.onLayoutReady?.(() => {
        const p = sourcePageRef.current;
        if (p > 1) scroll.scrollToPage({ pageNumber: p, behavior: "instant" });
        // Run pending highlight search after layout is ready
        const pending = pendingHighlightRef.current;
        if (pending) {
          pendingHighlightRef.current = null;
          doHighlightSearch(highlightRefs, registry, pending.page, pending.text, !!pending.exact);
        }
        unsub?.();
      });
    }

    // Clear search highlight when user clicks empty space or starts a new selection
    const selectionForClear = reg.getPlugin?.("selection")?.provides?.();
    const searchForClear = reg.getPlugin?.("search")?.provides?.();
    if (selectionForClear && searchForClear) {
      selectionForClear.onEmptySpaceClick?.(() => searchForClear.stopSearch?.());
      selectionForClear.onBeginSelection?.(() => searchForClear.stopSearch?.());
    }

    // Register KI actions as commands in EmbedPDF's selection menu
    const commands = reg.getPlugin?.("commands")?.provides?.();
    const ui = reg.getPlugin?.("ui")?.provides?.();
    if (!commands || !ui) return;

    const actions = popupActionsRef.current;
    if (actions?.length && onAskWithSelectionRef.current) {
      for (const action of actions) {
        commands.registerCommand({
          id: `kis.${action.key}`,
          label: action.label,
          description: action.label,
          icon: EMBEDPDF_ICON_MAP[action.icon] ?? "info",
          iconProps: { title: action.label },
          categories: ["kis-actions"],
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          visible: ({ state, documentId }: any) => {
            const doc = state?.plugins?.selection?.documents?.[documentId];
            if (!doc?.slices) return true;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const totalChars = Object.values(doc.slices as Record<string, any>).reduce((sum: number, s: any) => sum + (s.count || 0), 0);
            if (action.min_words <= 1) return totalChars > 0;
            // Average word ~6 chars; use conservative factor of 4
            return totalChars >= action.min_words * 4;
          },
          action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const sel = (r as any).getPlugin?.("selection")?.provides?.();
            if (!sel) return;
            const textTask = sel.getSelectedText?.(documentId);
            const promise: Promise<string[]> = textTask?.toPromise?.() ?? Promise.resolve([]);
            promise.then((lines: string[]) => {
              const text = (Array.isArray(lines) ? lines : [lines]).join(" ").trim();
              const bRects: Array<{ page: number }> = sel.getBoundingRects?.(documentId) ?? [];
              const selPage = bRects.length > 0 ? bRects[0].page + 1 : 1;
              onAskWithSelectionRef.current?.(
                `${action.prompt}\n\n"${text}"`,
                { uuid: sourceRef.current.uuid, filename: sourceRef.current.filename, page: selPage, selectedText: text },
              );
            }).catch(() => { /* ignore */ });
          },
        });
      }
    }

    // Register custom question command – prefills chat input with selected text
    commands.registerCommand({
      id: "kis.custom-question",
      label: "Frage stellen",
      description: "Frage stellen",
      icon: "ph-chat-circle",
      iconProps: { title: "Frage stellen" },
      categories: ["kis-actions"],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      visible: ({ state, documentId }: any) => {
        const doc = state?.plugins?.selection?.documents?.[documentId];
        if (!doc?.slices) return true;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const totalChars = Object.values(doc.slices as Record<string, any>).reduce((sum: number, s: any) => sum + (s.count || 0), 0);
        return totalChars > 0;
      },
      action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const sel = (r as any).getPlugin?.("selection")?.provides?.();
        if (!sel) return;
        const textTask = sel.getSelectedText?.(documentId);
        const promise: Promise<string[]> = textTask?.toPromise?.() ?? Promise.resolve([]);
        promise.then((lines: string[]) => {
          const text = (Array.isArray(lines) ? lines : [lines]).join(" ").trim();
          onCustomQuestionRef.current?.(text);
        }).catch(() => { /* ignore */ });
      },
    });

    // Replace EmbedPDF's default copy-selection. Its action awaits getSelectedText()
    // before calling navigator.clipboard.writeText(), which loses transient activation
    // on iOS Safari touch (silent failure). copyTextFromPromise passes a Promise to
    // ClipboardItem so the user gesture is preserved across the await.
    commands.registerCommand({
      id: "kis.copy-selection",
      label: "Kopieren",
      description: "Auswahl kopieren",
      icon: "copy",
      iconProps: { title: "Kopieren" },
      categories: ["selection", "selection-copy"],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      visible: ({ state, documentId }: any) => {
        const doc = state?.plugins?.selection?.documents?.[documentId];
        if (!doc?.slices) return true;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const totalChars = Object.values(doc.slices as Record<string, any>).reduce((sum: number, s: any) => sum + (s.count || 0), 0);
        return totalChars > 0;
      },
      action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const sel = (r as any).getPlugin?.("selection")?.provides?.();
        if (!sel) return;
        const textTask = sel.getSelectedText?.(documentId);
        const textPromise: Promise<string> = (textTask?.toPromise?.() ?? Promise.resolve([]))
          .then((lines: string[] | string) => (Array.isArray(lines) ? lines : [lines]).join("\n"));
        copyTextFromPromise(textPromise);
        textPromise.finally(() => sel.forDocument?.(documentId)?.clear?.());
      },
    });

    // Register glossary extract command
    commands.registerCommand({
      id: "kis.add-to-glossary",
      label: "Zum Glossar",
      description: "Fachbegriffe zum Glossar hinzufügen",
      icon: "ph-book",
      iconProps: { title: "Zum Glossar hinzufügen" },
      categories: ["kis-actions"],
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      visible: ({ state, documentId }: any) => {
        const doc = state?.plugins?.selection?.documents?.[documentId];
        if (!doc?.slices) return true;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const totalChars = Object.values(doc.slices as Record<string, any>).reduce((sum: number, s: any) => sum + (s.count || 0), 0);
        return totalChars > 0;
      },
      action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const sel = (r as any).getPlugin?.("selection")?.provides?.();
        if (!sel) return;
        const textTask = sel.getSelectedText?.(documentId);
        const promise: Promise<string[]> = textTask?.toPromise?.() ?? Promise.resolve([]);
        promise.then((lines: string[]) => {
          const text = (Array.isArray(lines) ? lines : [lines]).join(" ").trim();
          const bRects: Array<{ page: number }> = sel.getBoundingRects?.(documentId) ?? [];
          const selPage = bRects.length > 0 ? bRects[0].page + 1 : 1;
          onAddToGlossaryRef.current?.(text, sourceRef.current.uuid, selPage);
        }).catch(() => { /* ignore */ });
      },
    });

    // Register summary toggle command (opens EmbedPDF sidebar like comments)
    commands.registerCommand({
      id: "kis.toggle-summaries",
      label: "Zusammenfassungen",
      description: "Zusammenfassungen",
      icon: "ph-funnel-simple",
      categories: ["panel", "panel-summaries"],
      action: ({ registry: r, documentId }: { registry: unknown; documentId: string }) => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const uiCap = (r as any).getPlugin?.("ui")?.provides?.();
        uiCap?.forDocument?.(documentId)?.toggleSidebar?.("right", "main", "summary-panel");
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      active: ({ state, documentId }: any) => {
        const sidebar = state?.plugins?.ui?.documents?.[documentId]?.activeSidebars?.["right-main"];
        return sidebar?.isOpen && sidebar?.sidebarId === "summary-panel";
      },
    });

    // Merge: add KI actions to selection menu + summary button to main toolbar.
    // EmbedPDF-Defaults bis auf copy-selection rauswerfen — wir wollen weder
    // highlight/underline/strikeout/squiggly/link/redact noch deren Trenner.
    const existingSchema = ui.getSchema?.();
    // copy-selection ersetzen wir durch kis.copy-selection (Touch-Fix, siehe oben)
    const KEEP_DEFAULT_IDS = new Set(["add-highlight"]);
    const existingSelItems: unknown[] = (existingSchema?.selectionMenus?.selection?.items ?? [])
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((it: any) => it?.type !== "command-button" || KEEP_DEFAULT_IDS.has(it?.id))
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((it: any, idx: number, arr: any[]) => {
        // Verwaiste Trenner am Anfang/Ende oder direkt nebeneinander entfernen
        if (it?.type !== "divider") return true;
        const next = arr[idx + 1];
        const prev = arr[idx - 1];
        return prev?.type === "command-button" && next?.type === "command-button";
      });
    const mainToolbar = existingSchema?.toolbars?.["main-toolbar"];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const newToolbarItems = mainToolbar?.items?.map((item: any) =>
      item.id === "right-group"
        ? { ...item, items: [...(item.items ?? []), { type: "command-button", id: "summaries-button", commandId: "kis.toggle-summaries", variant: "icon", categories: ["panel", "panel-summaries"] }] }
        : item,
    );
    ui.mergeSchema?.({
      selectionMenus: {
        selection: {
          id: "selection",
          items: [
            { type: "command-button", id: "kis.copy-selection", commandId: "kis.copy-selection", variant: "icon", categories: ["selection", "selection-copy"] },
            ...existingSelItems,
            { type: "divider", id: "kis-custom-divider", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.add-to-glossary", commandId: "kis.add-to-glossary", variant: "icon", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.custom-question", commandId: "kis.custom-question", variant: "icon", categories: ["kis-actions"] },
            ...(actions?.length ? actions.map(a => ({
              type: "command-button",
              id: `kis.${a.key}`,
              commandId: `kis.${a.key}`,
              variant: "icon",
              categories: ["kis-actions"],
            })) : []),
          ],
        },
      },
      ...(newToolbarItems ? { toolbars: { "main-toolbar": { ...mainToolbar, items: newToolbarItems } } } : {}),
      sidebars: {
        "summary-panel": {
          id: "summary-panel",
          position: { placement: "right", slot: "main", order: 1 },
          content: { type: "tabs", tabs: [] },
          width: "250px",
          collapsible: true,
          defaultOpen: false,
        },
      },
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full relative viewer-short" ref={containerRef}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <button type="button" onClick={onClose}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }} title="Zurück">
          <CaretLeft size={13} weight="bold" color="var(--muted)" />
        </button>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--text)" }}>{source.filename}</span>
        {onMinimize && (
          <button type="button" onClick={onMinimize}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity ml-2"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }} title="Panel minimieren">
            <SidebarSimple size={13} />
          </button>
        )}
      </div>


      {/* PDF Viewer */}
      <div key={source.uuid} style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <PDFViewer
          ref={viewerRef}
          config={{
            src: `/api/ki-assistent/modules/${moduleUuid}/sources/${source.uuid}/file`,
            worker: true,
            search: { showAllResults: false },
            annotations: { locked: { type: "all" } },
            theme: {
              preference: themeModeRef.current,
              light: {
                scrollbar: { track: "transparent", thumb: "#d8d8d8", thumbHover: "#bbb" },
              },
              dark: {
                scrollbar: { track: "transparent", thumb: "#d8d8d8", thumbHover: "#bbb" },
              },
            },
          }}
          style={{ width: "100%", height: "100%" }}
          onReady={handleReady}
        />
      </div>
      {/* Summary content portaled into EmbedPDF's sidebar (shadow DOM) */}
      {sidebarTarget && createPortal(
        <div style={{ height: "100%", display: "flex", flexDirection: "column", fontFamily: "inherit" }}>
          <div style={{ padding: "8px 12px", borderBottom: "1px solid var(--color-border-default, #e5e7eb)", fontWeight: 600, fontSize: 12, color: "var(--color-fg-primary, #1f2937)" }}>
            Seite {page} – Zusammenfassung
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: 12, fontSize: 12, lineHeight: 1.6, color: "var(--color-fg-primary, #1f2937)" }}>
            {summariesStatus === "generating" && !pageSummaries[page] ? (
              <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>Wird generiert...</span>
            ) : pageSummaries[page] ? (
              <div dangerouslySetInnerHTML={{ __html: pageSummaries[page].replace(/\n/g, "<br/>") }} />
            ) : (summariesStatus === "none" || summariesStatus === "failed" || summariesStatus === "rate_limited") ? (
              <div style={{ textAlign: "center", padding: "16px 12px" }}>
                <span style={{ color: "#6b7280", display: "block", marginBottom: 10, fontSize: 12 }}>
                  {summariesStatus === "rate_limited" ? "API-Limit erreicht. Bitte spaeter erneut versuchen."
                    : summariesStatus === "failed" ? "Generierung fehlgeschlagen."
                    : "Noch keine Zusammenfassungen vorhanden."}
                </span>
                <button
                  onClick={async () => {
                    setSummariesStatus("generating");
                    setSummariesLoaded(false);
                    try {
                      await fetch(`/api/ki-assistent/modules/${moduleUuid}/sources/${source.uuid}/summaries/generate`, { method: "POST", credentials: "include" });
                    } catch { /* ignore */ }
                  }}
                  style={{ padding: "6px 16px", fontSize: 12, borderRadius: 6, border: "1px solid var(--color-accent, #3b82f6)", background: "var(--color-accent, #3b82f6)", color: "var(--color-accent-fg, #fff)", cursor: "pointer", fontWeight: 500 }}
                >
                  Zusammenfassungen generieren
                </button>
              </div>
            ) : (
              <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>Keine Zusammenfassung fuer diese Seite.</span>
            )}
          </div>
        </div>,
        sidebarTarget,
      )}
    </div>
  );
}
