import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowDown, ArrowUp, CaretLeft, FileX, SidebarSimple, X } from "@phosphor-icons/react";
import { PDFViewer } from "@embedpdf/react-pdf-viewer";
import { LockModeType } from "@embedpdf/plugin-annotation";
import { PdfErrorCode } from "@embedpdf/models";
import type { ViewerState } from "../../_types";
import { FileIcon } from "../sources/FileIcon";
import { EmptyState } from "@/components/ui/EmptyState";

import { wrapEngineGeometry } from "./_geometry";
import { buildSelfHostedFontFallback } from "./_fontFallback";
import { doHighlightSearch, clearCitationHighlight, scrollToCitationPage, markCitationSpot, CITATION_HL_COLOR, type HighlightRefs } from "./_highlight";
import { clearActiveChipTarget } from "../chat/_citations";
import { useTheme } from "@/hooks/useTheme";
import { registerSelectionCommands, type AskWithSelection, type PopupAction } from "./_pdfCommands";
import { injectShadowStyle } from "./_pdfShadowStyle";
import { PDF_THEME_COLORS } from "./_pdfTheme";


export function PdfViewer({
  source, onClose, workspaceUuid, onAskWithSelection, onCustomQuestion, popupActions, onMinimize, onAddToGlossary, onAddToNote,
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onAskWithSelection?: AskWithSelection;
  onCustomQuestion?: (selectedText: string) => void;
  popupActions?: PopupAction[];
  onMinimize?: () => void;
  onAddToGlossary?: (text: string, sourceUuid: string, page: number) => void;
  onAddToNote?: (text: string, sourceUuid: string, page: number) => void;
}) {
  const t = useTranslations("workspace.detail.pdf");
  const tViewer = useTranslations("workspace.detail.viewer");
  const tPanels = useTranslations("workspace.detail.panels");
  // The viewer speaks the language chosen in the settings.
  const locale = useLocale();
  const [page, setPage] = useState(source.page);
  // "retrying" hides the viewer's error screen during the one silent retry.
  const [loadState, setLoadState] = useState<"ok" | "retrying" | "failed">("ok");
  const containerRef = useRef<HTMLDivElement>(null);
  // A theme change forces a remount, the viewer cannot switch on the fly.
  const { theme } = useTheme();
  const themeModeRef = useRef<"light" | "dark">(theme);
  themeModeRef.current = theme;
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
  const onAddToNoteRef = useRef(onAddToNote);
  onAddToNoteRef.current = onAddToNote;
  const popupActionsRef = useRef(popupActions);
  popupActionsRef.current = popupActions;

  // Blocks copying from the viewer when the focus lies outside.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.key === "c" || e.key === "C") && (e.ctrlKey || e.metaKey)) {
        // A selection outside means native copying, otherwise the viewer's.
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) {
          e.stopImmediatePropagation();
        }
      }
    };
    document.addEventListener("keydown", handler, true); // capture phase
    return () => document.removeEventListener("keydown", handler, true);
  }, []);

  // Jumps to the page, a chip also marks the spot its claim rests on.
  const pendingHighlightRef = useRef<{ page: number; text: string; isCitation?: boolean; claim?: string } | null>(null);
  const citationHighlightRef = useRef<{ pageIndex: number; ids: string[]; scrollY?: number } | null>(null);
  // Controls the "Markierung aufheben" button shown while a citation highlight is active.
  const [citationActive, setCitationActive] = useState(false);
  const highlightRefs: HighlightRefs = { citationHighlightRef, onHighlightActive: setCitationActive };

  // Reset the old reference when the document changes.
  const loadedUuidRef = useRef<string | null>(null);
  useEffect(() => {
    if (loadedUuidRef.current !== source.uuid) {
      loadedUuidRef.current = source.uuid;
      registryRef.current = null;
      setLoadState("ok");
    }
  }, [source.uuid]);

  useEffect(() => {
    if (source.nonce == null) return;
    const reg = registryRef.current;
    if (!reg) {
      // Viewer not ready yet — save for later (drawn/scrolled on layout-ready).
      pendingHighlightRef.current = { page: source.page, text: source.highlightText ?? "", isCitation: source.isCitation, claim: source.citationClaim };
      return;
    }

    if (source.highlightText) {
      // Popup / action-bar exact selection: highlight the verbatim text.
      doHighlightSearch(highlightRefs, reg, source.page, source.highlightText);
    } else {
      // A chip draws the page frame and marks the passage behind its claim.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const scroll = (reg as any).getPlugin?.("scroll")?.provides?.();
      scroll?.scrollToPage?.({ pageNumber: source.page, behavior: "instant" });
      if (source.isCitation) markCitationSpot(highlightRefs, reg, source.page, source.citationClaim, source.filename);
    }

  }, [source.nonce, source.page, source.highlightText, source.isCitation, source.citationClaim]);

  // A new document discards the transient highlight.
  useEffect(() => {
    citationHighlightRef.current = null;
    setCitationActive(false);
  }, [source.uuid]);

  const handleReady = useCallback((registry: unknown) => {
    registryRef.current = registry;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const reg = registry as any;

    // Corrects oversized highlights with inflated font metrics.
    wrapEngineGeometry(reg.getEngine?.());

    // One silent retry clears a transient permission hiccup (e.g. demo enrollment not yet
    // visible server-side), a second failure shows our own notice instead of the viewer's
    // error screen, whose close button leads on to "open a file of your own".
    const docManager = reg.getPlugin?.("document-manager")?.provides?.();
    let hasRetriedLoad = false;
    type LoadTask = { wait: (ok: () => void, fail: () => void) => void };
    docManager?.onDocumentError?.((evt: { documentId: string; code?: number }) => {
      // The password prompt is the viewer's own and stays visible.
      if (evt.code === PdfErrorCode.Password) return;
      if (hasRetriedLoad) { setLoadState("failed"); return; }
      hasRetriedLoad = true;
      setLoadState("retrying");
      // The viewer does not report the same error twice, so the retry's own load task decides.
      setTimeout(() => {
        docManager.retryDocument(evt.documentId).wait(
          ({ task }: { task: LoadTask }) => task.wait(() => setLoadState("ok"), () => setLoadState("failed")),
          () => setLoadState("failed"),
        );
      }, 600);
    });
    docManager?.onDocumentOpened?.(() => setLoadState("ok"));

    // On a touch device the rectangles have to be drawn in pan mode too.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const selCap = reg.getPlugin?.("selection")?.provides?.() as any;
    try {
      selCap?.enableForMode?.("panMode", { enableSelection: false, showSelectionRects: true });
    } catch { /* ignore */ }

    // Injects the house styling into the sandboxed viewer.
    const inject = () => injectShadowStyle(containerRef.current);
    if (!inject()) {
      // Shadow DOM might not be ready yet — retry briefly
      const t = setInterval(() => { if (inject()) clearInterval(t); }, 100);
      setTimeout(() => clearInterval(t), 3000);
    }

    // Track current page
    const scroll = reg.getPlugin?.("scroll")?.provides?.();
    if (scroll) {
      scroll.onPageChange(({ pageNumber }: { pageNumber: number }) => setPage(pageNumber));
      const unsub = scroll.onLayoutReady?.(() => {
        const p = sourcePageRef.current;
        if (p > 1) scroll.scrollToPage({ pageNumber: p, behavior: "instant" });
        // The highlight only after the layout, and only on a selection of your own.
        const pending = pendingHighlightRef.current;
        if (pending) {
          pendingHighlightRef.current = null;
          if (pending.text) {
            doHighlightSearch(highlightRefs, registry, pending.page, pending.text);
          } else if (pending.isCitation) {
            markCitationSpot(highlightRefs, registry, pending.page, pending.claim, sourceRef.current.filename);
          }
        }
        unsub?.();
      });
    }

    // Clears the highlight on a click outside or a new selection.
    const selectionForClear = reg.getPlugin?.("selection")?.provides?.();
    const searchForClear = reg.getPlugin?.("search")?.provides?.();
    if (selectionForClear && searchForClear) {
      selectionForClear.onEmptySpaceClick?.(() => searchForClear.stopSearch?.());
      selectionForClear.onBeginSelection?.(() => searchForClear.stopSearch?.());
    }

    registerSelectionCommands(reg, {
      t,
      actions: popupActionsRef.current,
      sourceRef,
      onAskWithSelectionRef,
      onCustomQuestionRef,
      onAddToGlossaryRef,
      onAddToNoteRef,
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div data-tour="pdf-viewer" className="flex flex-col h-full relative" ref={containerRef}>
      {/* Header */}
      <div data-panel-header="" className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <button type="button" onClick={onClose}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }} title={tViewer("back")}>
          <CaretLeft size={13} weight="bold" />
        </button>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--foreground)" }}>{source.filename}</span>
        {onMinimize && (
          <button type="button" onClick={onMinimize}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon ml-2"
            style={{ backgroundColor: "var(--surface-dim)" }} title={tPanels("minimize")}>
            <SidebarSimple size={13} />
          </button>
        )}
      </div>


      {/* The key includes theme and locale so a switch remounts EmbedPDF cleanly. */}
      <div key={`${source.uuid}-${theme}-${locale}`} style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <PDFViewer
          config={{
            src: `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`,
            worker: true,
            // Self-hosted so the rendering engine never leaves our own domain (default would fetch it from jsDelivr).
            // Must be absolute: the worker runs from a blob: URL, where a relative path doesn't resolve against our origin.
            wasmUrl: `${window.location.origin}/pdfium.wasm`,
            // Same reasoning for non-embedded-font fallback glyphs (CJK/Arabic/Hebrew/Cyrillic PDFs).
            fontFallback: buildSelfHostedFontFallback(window.location.origin),
            // The viewer shows the workspace file only, never one of your own.
            disabledCategories: ["document-open", "document-close"],
            tabBar: "never",
            i18n: { defaultLocale: locale },
            search: { showAllResults: false },
            // Without this the render plugin never bakes annotations into the page bitmap,
            // so neither the highlight tool nor a citation's own highlight ever show.
            render: { withAnnotations: true },
            annotations: {
              locked: { type: LockModeType.All },
              // The highlighter tool paints in house blue instead of the viewer's yellow.
              tools: [{ id: "highlight", defaults: { color: CITATION_HL_COLOR, strokeColor: CITATION_HL_COLOR } }],
            },
            theme: {
              preference: themeModeRef.current,
              ...PDF_THEME_COLORS,
            },
          }}
          style={{ width: "100%", height: "100%" }}
          onReady={handleReady}
        />
        {loadState !== "ok" && (
          <div className="absolute inset-0 z-20 flex items-center justify-center" style={{ backgroundColor: "var(--surface)" }}>
            {loadState === "failed" && (
              <div data-testid="pdf-load-failed">
                <EmptyState icon={<FileX size={32} weight="bold" />} title={t("loadFailedTitle")} text={t("loadFailedText")} />
              </div>
            )}
          </div>
        )}
        {/* Citation highlight controls — bottom-right corner, clear of EmbedPDF's
            centered page-nav. Icon-only to stay out of the way; full text lives in
            title/aria for hover + screen readers. */}
        {citationActive && (
          <div className="absolute bottom-6 right-4 z-10 flex items-center gap-1.5">
            {/* Jump-to-highlight: shown only after the user has paged away. Arrow
                points toward the highlight (down = further into the document),
                number = its page. */}
            {page !== source.page && (
              <button
                type="button"
                onClick={() => scrollToCitationPage(highlightRefs, registryRef.current)}
                className="flex items-center gap-1 pl-2 pr-2.5 py-1.5 rounded-full text-xs font-medium shadow-md btn-icon"
                style={{ backgroundColor: "var(--surface)", color: "var(--kb)", border: "1px solid var(--kb)" }}
                title={tViewer("jumpToHighlightPage", { page: source.page })}
                aria-label={tViewer("jumpToHighlightPage", { page: source.page })}
              >
                {page < source.page ? <ArrowDown size={13} weight="bold" /> : <ArrowUp size={13} weight="bold" />}
                <span className="tabular-nums">{source.page}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => { clearCitationHighlight(highlightRefs, registryRef.current); clearActiveChipTarget(); }}
              className="flex items-center justify-center w-7 h-7 rounded-full shadow-md btn-icon"
              style={{ backgroundColor: "var(--surface)", color: "var(--foreground)", border: "1px solid var(--border)" }}
              title={tViewer("dismissHighlight")}
              aria-label={tViewer("dismissHighlight")}
            >
              <X size={13} weight="bold" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
