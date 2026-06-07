import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDown, ArrowUp, CaretLeft, SidebarSimple, X } from "@phosphor-icons/react";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";
import { LockModeType } from "@embedpdf/plugin-annotation";
import type { ViewerState } from "../../_types";
import { FileIcon } from "../sources/FileIcon";

import { EMBEDPDF_ICON_MAP } from "./_icons";
import { wrapEngineGeometry } from "./_geometry";
import { doHighlightSearch, clearCitationHighlight, scrollToCitationPage, flashPageBorder, type HighlightRefs } from "./_highlight";
import { copyTextFromPromise } from "@/lib/clipboard";
import { useTheme } from "@/hooks/useTheme";


export function PdfViewer({
  source, onClose, workspaceUuid, onAskWithSelection, onCustomQuestion, popupActions, onMinimize, onAddToGlossary, onAddToNote, isOwner = false,
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onAskWithSelection?: (text: string, sourceInfo: { uuid: string; filename: string; page: number; selectedText?: string; actionKey?: string }) => void;
  onCustomQuestion?: (selectedText: string) => void;
  popupActions?: { key: string; label: string; icon: string; prompt: string; min_words: number }[];
  onMinimize?: () => void;
  onAddToGlossary?: (text: string, sourceUuid: string, page: number) => void;
  onAddToNote?: (text: string, sourceUuid: string, page: number) => void;
  isOwner?: boolean;
}) {
  const t = useTranslations("workspace.detail.pdf");
  const tViewer = useTranslations("workspace.detail.viewer");
  const tPanels = useTranslations("workspace.detail.panels");
  const [page, setPage] = useState(source.page);
  const [registryReady, setRegistryReady] = useState(false);
  const viewerRef = useRef<PDFViewerRef>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // Theme drives EmbedPDF's internal light/dark — change forces a remount via key on the viewer
  // (EmbedPDF has no hot-swap API for theme).
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

  // Scroll to page (+ highlight text for popup/action-bar exact selections) when the
  // nonce changes (pill click on the same document). Citation chips set no text, so
  // they only scroll; a popup/action-bar selection sets `text` and gets highlighted.
  const pendingHighlightRef = useRef<{ page: number; text: string; isCitation?: boolean } | null>(null);
  const prevHighlightRef = useRef<{ pageIndex: number; ids: string[] } | null>(null);
  const citationHighlightRef = useRef<{ pageIndex: number; ids: string[]; scrollY?: number } | null>(null);
  // Controls the "Markierung aufheben" button shown while a citation highlight is active.
  const [citationActive, setCitationActive] = useState(false);
  const highlightRefs: HighlightRefs = { prevHighlightRef, citationHighlightRef, onHighlightActive: setCitationActive };

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
      // Viewer not ready yet — save for later (drawn/scrolled on layout-ready).
      pendingHighlightRef.current = { page: source.page, text: source.highlightText ?? "", isCitation: source.isCitation };
      return;
    }

    if (source.highlightText) {
      // Popup / action-bar exact selection: highlight the verbatim text.
      doHighlightSearch(highlightRefs, reg, source.page, source.highlightText);
    } else {
      // Scroll to the page. A citation chip also gets a yellow frame around the page
      // (cleared via the "Markierung aufheben" button or replaced by the next jump);
      // a plain document open just scrolls.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const scroll = (reg as any).getPlugin?.("scroll")?.provides?.();
      scroll?.scrollToPage?.({ pageNumber: source.page, behavior: "instant" });
      if (source.isCitation) flashPageBorder(highlightRefs, reg, source.page);
    }

  }, [source.nonce, source.page, source.highlightText, source.isCitation]);

  // A new document remounts EmbedPDF (keyed by uuid), discarding the ephemeral
  // citation highlight — reset its tracking + dismiss button.
  useEffect(() => {
    citationHighlightRef.current = null;
    setCitationActive(false);
  }, [source.uuid]);

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

    // Inject KIS Corporate Design overrides into EmbedPDF's shadow DOM:
    // - 5px scrollbar (instead of default 8px)
    // - 2px border on buttons (transparent default, KB-blue on hover/focus)
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
          /* KIS-CD: 2px outline on hover/focus for all interactive elements.
             outline (not border) — preserves EmbedPDF's own border-b tab indicator
             and doesn't shift layout. Matches KIS pattern from globals.css. */
          :host button,
          :host [role="button"],
          :host [class*="command-button"],
          :host [class*="-button"] {
            outline: 2px solid transparent !important;
            outline-offset: 0 !important;
          }
          :host button:hover,
          :host button:focus-visible,
          :host [role="button"]:hover,
          :host [role="button"]:focus-visible,
          :host [class*="command-button"]:hover,
          :host [class*="command-button"]:focus-visible,
          :host [class*="-button"]:hover,
          :host [class*="-button"]:focus-visible {
            outline-color: var(--kb) !important;
            /* Suppress EmbedPDFs hover ring (Tailwind ring + box-shadow) so only our outline shows */
            box-shadow: none !important;
            --tw-ring-shadow: 0 0 transparent !important;
            --tw-ring-offset-shadow: 0 0 transparent !important;
          }
          /* Mode tabs: inactive ones get rounded + hover outline; bottom border off */
          :host [data-epdf-i="mode-tabs"] button {
            border-radius: 6px !important;
            border-bottom: 0 !important;
          }
          /* Active mode tab: only bottom strich (no outline, no radius, no hover effect) */
          :host [data-epdf-i="mode-tabs"] button[class*="text-accent"],
          :host [data-epdf-i="mode-tabs"] button[class*="text-accent"]:hover,
          :host [data-epdf-i="mode-tabs"] button[class*="text-accent"]:focus-visible {
            outline: none !important;
            border-bottom: 2px solid var(--kb) !important;
            border-radius: 0 !important;
          }
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
        // Run pending highlight after layout is ready. Only a popup/action-bar exact
        // selection carries text to highlight; a plain/citation open just scrolled
        // to the page above.
        const pending = pendingHighlightRef.current;
        if (pending) {
          pendingHighlightRef.current = null;
          if (pending.text) {
            doHighlightSearch(highlightRefs, registry, pending.page, pending.text);
          } else if (pending.isCitation) {
            flashPageBorder(highlightRefs, registry, pending.page);
          }
        }
        unsub?.();
      });
    }

    // Clear search highlight when user clicks empty space or starts a new selection.
    // NOTE: onEmptySpaceClick/onBeginSelection are EmbedPDF-internal hooks — re-verify on bump.
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
              const formatted: Array<{ pageIndex: number }> = sel.forDocument?.(documentId)?.getFormattedSelection?.() ?? [];
              const selPage = formatted.length > 0 ? formatted[0].pageIndex + 1 : 1;
              onAskWithSelectionRef.current?.(
                `${action.prompt}\n\n"${text}"`,
                { uuid: sourceRef.current.uuid, filename: sourceRef.current.filename, page: selPage, selectedText: text, actionKey: action.key },
              );
            }).catch(() => { /* ignore */ });
          },
        });
      }
    }

    // Register custom question command – prefills chat input with selected text
    commands.registerCommand({
      id: "kis.custom-question",
      label: t("askQuestion"),
      description: t("askQuestion"),
      icon: "ph-chat-circle",
      iconProps: { title: t("askQuestion") },
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
      label: t("copy"),
      description: t("copySelection"),
      icon: "copy",
      iconProps: { title: t("copy") },
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
      label: t("addToGlossary"),
      description: t("addToGlossaryDescription"),
      icon: "ph-book",
      iconProps: { title: t("addToGlossaryTitle") },
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
          const formatted: Array<{ pageIndex: number }> = sel.forDocument?.(documentId)?.getFormattedSelection?.() ?? [];
          const selPage = formatted.length > 0 ? formatted[0].pageIndex + 1 : 1;
          onAddToGlossaryRef.current?.(text, sourceRef.current.uuid, selPage);
        }).catch(() => { /* ignore */ });
      },
    });

    // Register add-to-note command – stores selection as a new note with source chip
    commands.registerCommand({
      id: "kis.add-to-note",
      label: t("addToNote"),
      description: t("addToNoteDescription"),
      icon: "ph-note-pencil",
      iconProps: { title: t("addToNoteTitle") },
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
          const formatted: Array<{ pageIndex: number }> = sel.forDocument?.(documentId)?.getFormattedSelection?.() ?? [];
          const selPage = formatted.length > 0 ? formatted[0].pageIndex + 1 : 1;
          onAddToNoteRef.current?.(text, sourceRef.current.uuid, selPage);
        }).catch(() => { /* ignore */ });
      },
    });

    // Merge: add KI actions to the selection menu.
    // Drop EmbedPDF defaults except copy-selection: we want neither
    // highlight/underline/strikeout/squiggly/link/redact nor their dividers.
    const existingSchema = ui.getSchema?.();
    // We replace copy-selection with kis.copy-selection (touch fix, see above)
    const KEEP_DEFAULT_IDS = new Set(["add-highlight"]);
    const existingSelItems: unknown[] = (existingSchema?.selectionMenus?.selection?.items ?? [])
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((it: any) => it?.type !== "command-button" || KEEP_DEFAULT_IDS.has(it?.id))
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      .filter((it: any, idx: number, arr: any[]) => {
        // Remove orphaned dividers at start/end or directly next to each other
        if (it?.type !== "divider") return true;
        const next = arr[idx + 1];
        const prev = arr[idx - 1];
        return prev?.type === "command-button" && next?.type === "command-button";
      });
    ui.mergeSchema?.({
      selectionMenus: {
        selection: {
          id: "selection",
          items: [
            { type: "command-button", id: "kis.copy-selection", commandId: "kis.copy-selection", variant: "icon", categories: ["selection", "selection-copy"] },
            ...existingSelItems,
            { type: "divider", id: "kis-custom-divider", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.add-to-glossary", commandId: "kis.add-to-glossary", variant: "icon", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.add-to-note", commandId: "kis.add-to-note", variant: "icon", categories: ["kis-actions"] },
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
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col h-full relative viewer-short" ref={containerRef}>
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
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


      {/* PDF Viewer — key includes theme so a Light/Dark switch remounts EmbedPDF cleanly */}
      <div key={`${source.uuid}-${theme}`} style={{ flex: 1, position: "relative", minHeight: 0 }}>
        <PDFViewer
          ref={viewerRef}
          config={{
            src: `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`,
            worker: true,
            search: { showAllResults: false },
            annotations: { locked: { type: LockModeType.All } },
            // KIS Corporate Design — values mirror tokens in globals.css.
            // Update both files together when CD changes.
            theme: {
              preference: themeModeRef.current,
              light: {
                accent: {
                  primary:           "#004261", // --kb
                  primaryHover:      "#003350", // --kb-dark
                  primaryActive:     "#00293d", // --kb-darker
                  primaryLight:      "#EBEDF0", // --surface-dim (text-selection background)
                  primaryForeground: "#ffffff",
                },
                background: {
                  app:        "#F3F4F6", // --surface
                  surface:    "#ffffff", // --background (toolbars, panels)
                  surfaceAlt: "#EBEDF0", // --surface-dim
                  elevated:   "#ffffff",
                  input:      "#ffffff",
                },
                foreground: {
                  primary:   "#0D1F2D", // --foreground
                  secondary: "#2F4D5C", // --foreground-soft
                  muted:     "#668DA0", // --muted
                  disabled:  "#8FAEC0", // --muted-soft
                  onAccent:  "#ffffff",
                },
                border: {
                  default: "#B8CDD5", // --border
                  subtle:  "#D9E2E6", // --border-soft
                  strong:  "#8FAEC0", // --muted-soft
                },
                interactive: {
                  hover:    "#F3F4F6", // --surface
                  active:   "#EBEDF0", // --surface-dim
                  selected: "#EBEDF0", // --surface-dim
                  focus:    "#004261", // --kb
                },
                state: {
                  error:        "#DC2626", errorLight:   "#FEF2F2",
                  warning:      "#D97706", warningLight: "#FFFBEB",
                  success:      "#16A34A", successLight: "#F0FDF4",
                  info:         "#2563EB", infoLight:    "#EFF6FF",
                },
                scrollbar: { track: "transparent", thumb: "#d8d8d8", thumbHover: "#bbb" },
              },
              dark: {
                accent: {
                  primary:           "#5BA3CE", // --kb (dark)
                  primaryHover:      "#7BBDE5", // --kb-dark (dark)
                  primaryActive:     "#9BD2F0", // --kb-darker (dark)
                  primaryLight:      "#1C2A33", // --kb20 (dark)
                  primaryForeground: "#0A0B0D", // text on lifted accent
                },
                background: {
                  app:        "#0A0B0D", // --background (dark)
                  surface:    "#141519", // --surface (dark)
                  surfaceAlt: "#1C1D22", // --surface-dim (dark)
                  elevated:   "#141519",
                  input:      "#1C1D22",
                },
                foreground: {
                  primary:   "#F5F5F7", // --foreground (dark)
                  secondary: "#C8CACF", // --foreground-soft (dark)
                  muted:     "#8B8E97", // --muted (dark)
                  disabled:  "#6E7079", // --muted-soft (dark)
                  onAccent:  "#0A0B0D",
                },
                border: {
                  default: "#2A2C32", // --border (dark)
                  subtle:  "#23252B", // --border-soft (dark)
                  strong:  "#3A3C42",
                },
                interactive: {
                  hover:    "#1C1D22", // --surface-dim (dark)
                  active:   "#23252B",
                  selected: "#23252B",
                  focus:    "#5BA3CE", // --kb (dark)
                },
                state: {
                  error:        "#F87171", errorLight:   "#2A1414",
                  warning:      "#FBBF24", warningLight: "#2A1F0A",
                  success:      "#4ADE80", successLight: "#0F2818",
                  info:         "#60A5FA", infoLight:    "#0F1A2E",
                },
                scrollbar: { track: "transparent", thumb: "#3A3C42", thumbHover: "#52545C" },
              },
            },
          }}
          style={{ width: "100%", height: "100%" }}
          onReady={handleReady}
        />
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
              onClick={() => clearCitationHighlight(highlightRefs, registryRef.current)}
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
