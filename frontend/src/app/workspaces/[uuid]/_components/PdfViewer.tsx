import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CaretLeft, SidebarSimple } from "@phosphor-icons/react";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";
import { registerIcons } from "@embedpdf/snippet";
import type { ViewerState } from "../_types";
import { FileIcon } from "./FileIcon";

// Register Phosphor icons as custom EmbedPDF icons for the selection popup
registerIcons({
  "ph-binoculars": {
    viewBox: "0 0 256 256",
    path: "M241,150.65s0,0,0-.05a51.33,51.33,0,0,0-2.53-5.9L196.93,50.18a12,12,0,0,0-2.5-3.65,36,36,0,0,0-50.92,0A12,12,0,0,0,140,55V76H116V55a12,12,0,0,0-3.51-8.48,36,36,0,0,0-50.92,0,12,12,0,0,0-2.5,3.65L17.53,144.7A51.33,51.33,0,0,0,15,150.6s0,0,0,.05A52,52,0,1,0,116,168V100h24v68a52,52,0,1,0,101-17.35ZM80,62.28a12,12,0,0,1,12-1.22v63.15a51.9,51.9,0,0,0-35.9-7.62ZM64,196a28,28,0,1,1,28-28A28,28,0,0,1,64,196ZM164,61.06a12.06,12.06,0,0,1,12,1.22l23.87,54.31a51.9,51.9,0,0,0-35.9,7.62ZM192,196a28,28,0,1,1,28-28A28,28,0,0,1,192,196Z",
    fill: "primary",
    stroke: "none",
  },
  "ph-funnel-simple": {
    viewBox: "0 0 256 256",
    path: "M204,136a12,12,0,0,1-12,12H64a12,12,0,0,1,0-24H192A12,12,0,0,1,204,136Zm28-60H24a12,12,0,0,0,0,24H232a12,12,0,0,0,0-24Zm-80,96H104a12,12,0,0,0,0,24h48a12,12,0,0,0,0-24Z",
    fill: "primary",
    stroke: "none",
  },
  "ph-lightbulb": {
    viewBox: "0 0 256 256",
    path: "M180,232a12,12,0,0,1-12,12H88a12,12,0,0,1,0-24h80A12,12,0,0,1,180,232Zm40-128a91.51,91.51,0,0,1-35.17,72.35A12.26,12.26,0,0,0,180,186v2a20,20,0,0,1-20,20H96a20,20,0,0,1-20-20v-2a12,12,0,0,0-4.7-9.51A91.57,91.57,0,0,1,36,104.52C35.73,54.69,76,13.2,125.79,12A92,92,0,0,1,220,104Zm-24,0a68,68,0,0,0-69.65-68C89.56,36.88,59.8,67.55,60,104.38a67.71,67.71,0,0,0,26.1,53.19A35.87,35.87,0,0,1,100,184h56.1A36.13,36.13,0,0,1,170,157.49,67.68,67.68,0,0,0,196,104Zm-20.07-5.32a48.5,48.5,0,0,0-31.91-40,12,12,0,0,0-8,22.62,24.31,24.31,0,0,1,16.09,20,12,12,0,0,0,23.86-2.64Z",
    fill: "primary",
    stroke: "none",
  },
  "ph-chat-circle": {
    viewBox: "0 0 256 256",
    path: "M128,20A108,108,0,0,0,31.85,177.23L21,209.66A20,20,0,0,0,46.34,235l32.43-10.81A108,108,0,1,0,128,20Zm0,192a84,84,0,0,1-42.06-11.27,12,12,0,0,0-6-1.62,12.1,12.1,0,0,0-3.8.62l-29.79,9.93,9.93-29.79a12,12,0,0,0-1-9.81A84,84,0,1,1,128,212Z",
    fill: "primary",
    stroke: "none",
  },
  "ph-book": {
    viewBox: "0 0 256 256",
    path: "M208,24H72A32,32,0,0,0,40,56V224a8,8,0,0,0,8,8H192a8,8,0,0,0,0-16H56a16,16,0,0,1,16-16H208a8,8,0,0,0,8-8V32A8,8,0,0,0,208,24Zm-8,168H72a31.82,31.82,0,0,0-16,4.29V56A16,16,0,0,1,72,40H200Z",
    fill: "primary",
    stroke: "none",
  },
});

// Map Phosphor icon names → EmbedPDF icon names (built-in or custom registered)
const EMBEDPDF_ICON_MAP: Record<string, string> = {
  Binoculars: "ph-binoculars",
  FunnelSimple: "ph-funnel-simple",
  ListBullets: "listTree",
  Lightbulb: "ph-lightbulb",
  ArrowsCounterClockwise: "arrowBackUp",
  Scissors: "redact",
  MagnifyingGlassPlus: "search",
  BookOpenText: "file",
};

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
  const pendingHighlightRef = useRef<{ page: number; text: string } | null>(null);
  const prevHighlightRef = useRef<{ pageIndex: number; ids: string[] } | null>(null);

  // Try to find and highlight text on a specific page. Returns true if found.
  function tryHighlightOnPage(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    r: any, doc: any, engine: any, docMgr: any, scroll: any,
    targetPageIndex: number, searchText: string,
  ): Promise<boolean> {
    const pageObj = doc.pages?.[targetPageIndex];
    if (!pageObj) return Promise.resolve(false);

    const selection = r.getPlugin?.("selection")?.provides?.();
    const cachedGeo = selection?.getState?.()?.geometry?.[targetPageIndex];
    const geoPromise: Promise<unknown> = cachedGeo
      ? Promise.resolve(cachedGeo)
      : (engine.getPageGeometry?.(doc, pageObj)?.toPromise?.() ?? Promise.resolve(null));

    return geoPromise.then((geo: unknown) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const g = geo as any;
      if (!g?.runs?.length) return false;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const lastRun = g.runs[g.runs.length - 1] as any;
      const totalChars = lastRun.charStart + lastRun.glyphs.length;
      if (totalChars === 0) return false;

      const sliceTask = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: totalChars }]);
      const slicePromise: Promise<unknown> = sliceTask?.toPromise?.() ?? Promise.resolve(null);

      return slicePromise.then((slices: unknown) => {
        const arr = slices as string[] | null;
        if (!arr?.[0]) return false;
        const rawPageText = arr[0];

        // Normalize whitespace for robust search, track mapping to raw indices
        const cleanToRaw: number[] = [];
        let cleanText = "";
        let inSpace = false;
        for (let i = 0; i < rawPageText.length; i++) {
          const ch = rawPageText[i];
          if (ch === "\r" || ch === "\n" || ch === " " || ch === "\t") {
            if (!inSpace) { cleanText += " "; cleanToRaw.push(i); inSpace = true; }
          } else { cleanText += ch; cleanToRaw.push(i); inSpace = false; }
        }

        const cleanInput = searchText.replace(/\s+/g, " ").trim()
          .replace(/^\d{1,3}\s+/, "").trim();
        const ptLower = cleanText.toLowerCase();
        const inputWords = cleanInput.toLowerCase().split(" ").filter(w => w.length > 0);

        // Find keywords on the page — try as phrase first, then individual keywords
        let matchStart = -1;
        let matchEnd = -1;
        // If the full search text matches verbatim AND is long enough to span multiple
        // sentences (e.g. a user-selected paragraph), use the match bounds directly instead
        // of expanding via sentence boundaries — the selection already defines exact bounds.
        // Short keyword phrases still get sentence expansion as before.
        let exactFullMatch = false;

        // 1. Try full phrase match
        const fullPhrase = inputWords.join(" ");
        const fullIdx = ptLower.indexOf(fullPhrase);
        if (fullIdx >= 0) {
          matchStart = fullIdx;
          matchEnd = fullIdx + fullPhrase.length - 1;
          if (fullPhrase.length >= 120) exactFullMatch = true;
        }

        // 2. Try sliding windows (decreasing size)
        if (matchStart < 0) {
          outer:
          for (let windowSize = inputWords.length; windowSize >= 2; windowSize--) {
            for (let skip = 0; skip <= inputWords.length - windowSize; skip++) {
              const phrase = inputWords.slice(skip, skip + windowSize).join(" ");
              const idx = ptLower.indexOf(phrase);
              if (idx >= 0) {
                matchStart = idx;
                matchEnd = idx + phrase.length - 1;
                break outer;
              }
            }
          }
        }

        // 3. Find individual keywords and use the position of the most specific one (longest word)
        if (matchStart < 0) {
          const sorted = [...inputWords].sort((a, b) => b.length - a.length);
          for (const word of sorted) {
            if (word.length < 4) continue;
            const idx = ptLower.indexOf(word);
            if (idx >= 0) {
              matchStart = idx;
              matchEnd = idx + word.length - 1;
              break;
            }
          }
        }

        if (matchStart < 0 || matchEnd < 0) return false;

        // Expand to sentence boundaries (period, newline, or start/end of text)
        // Skip abbreviation dots: bzw. z.B. u.a. etc. ca. vs. Dr. Nr. Prof. d.h. o.ä. ggf. S. Abs.
        const _abbrPattern = /(?:bzw|z\.B|u\.a|etc|ca|vs|Dr|Nr|Prof|d\.h|o\.ä|ggf|Abs|Abb|vgl|inkl|sog|evtl|S)\s*$/i;
        const _isAbbrevDot = (text: string, dotIdx: number) => {
          if (dotIdx < 1) return false;
          // Dot directly followed by a letter (no space) is inside an abbreviation
          // (e.g. "z.B.", "d.h.", "U.S.A."). Digits after a dot are NOT treated as
          // abbreviation to keep footnote markers ("erprobt.11") as real sentence ends —
          // decimal numbers like "3.14" are covered by the digit-before-dot rule below.
          const next = text[dotIdx + 1];
          if (next && /[A-Za-zÄÖÜäöüß]/.test(next)) return true;
          const before = text.slice(Math.max(0, dotIdx - 6), dotIdx);
          if (_abbrPattern.test(before)) return true;
          // Single uppercase letter + dot (e.g. "S." "A.")
          if (dotIdx >= 1 && /^[A-ZÄÖÜ]$/.test(text[dotIdx - 1]) && (dotIdx < 2 || text[dotIdx - 2] === " ")) return true;
          // Number + dot (e.g. "3." "49%.")
          if (/\d$/.test(text.slice(Math.max(0, dotIdx - 1), dotIdx))) return true;
          return false;
        };
        // Helper: find sentence boundaries around a position
        const _findSentBounds = (startPos: number, endPos: number): [number, number] => {
          let sStart = startPos, sEnd = endPos;
          for (let i = startPos - 1; i >= 0; i--) {
            const ch = cleanText[i];
            if (ch === "\n" || ch === "!" || ch === "?") {
              sStart = i + 1;
              while (sStart < startPos && cleanText[sStart] === " ") sStart++;
              break;
            }
            if (ch === "." && !_isAbbrevDot(cleanText, i)) {
              sStart = i + 1;
              while (sStart < startPos && cleanText[sStart] === " ") sStart++;
              break;
            }
            if (i === 0) sStart = 0;
          }
          for (let i = endPos + 1; i < cleanText.length; i++) {
            const ch = cleanText[i];
            if (ch === "\n" || ch === "!" || ch === "?") { sEnd = i; break; }
            if (ch === "." && !_isAbbrevDot(cleanText, i)) { sEnd = i; break; }
            if (i === cleanText.length - 1) sEnd = i;
          }
          return [sStart, sEnd];
        };

        // Paragraph-break detection: double newline in raw text, or a heading pattern
        // ("Kapitel:", "1.2 Titel") at the start of the next line.
        const _isHeading = (text: string): boolean => {
          const t = text.replace(/^\s+/, "");
          // Colon-terminated heading: "International Coach:", "Fachlandkarte:"
          if (/^[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ]?[\wäöüß-]+){0,3}\s*:/.test(t)) return true;
          // Numbered section heading: "1. Management Summary", "4.4 Transferpotential",
          // "2.1.3 Skizze der Ausgangslage"
          if (/^\d+(?:\.\d+)*\.?\s+[A-ZÄÖÜ][\wäöüß-]+/.test(t)) return true;
          return false;
        };
        const _isParagraphBreakBefore = (startInClean: number): boolean => {
          if (startInClean <= 0) return false;
          // cleanToRaw points at the FIRST whitespace char of the run — scan forward
          // through raw to count newlines until a non-whitespace char appears.
          const rawPos = cleanToRaw[startInClean - 1];
          if (rawPos == null) return false;
          let nlCount = 0;
          for (let i = rawPos; i < rawPageText.length; i++) {
            const ch = rawPageText[i];
            if (ch === "\n") nlCount++;
            else if (ch !== " " && ch !== "\r" && ch !== "\t") break;
          }
          if (nlCount >= 2) return true;
          const preview = cleanText.slice(startInClean, Math.min(cleanText.length, startInClean + 80));
          if (_isHeading(preview)) return true;
          // Skip a leading footnote-digit marker ("11 International Coach:") and re-test
          const skipped = preview.replace(/^\s*\d{1,3}\s+/, "");
          return skipped !== preview && _isHeading(skipped);
        };
        // True only if the WHOLE text is a heading (with optional leading page-num /
        // footnote digit), not just its prefix — otherwise "4.4. Title Actual paragraph
        // content..." would falsely match and cause the first paragraph sentence to be
        // dropped from the highlight.
        const _isFullHeading = (text: string): boolean => {
          const t = text.replace(/^\s+|\s+$/g, "");
          if (/^[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ]?[\wäöüß-]+){0,4}\s*:$/.test(t)) return true;
          if (/^\d+(?:\.\d+)*\.?\s+[A-ZÄÖÜ][\wäöüß-]+(?:\s+[A-ZÄÖÜ]?[\wäöüß-]+){0,5}$/.test(t)) return true;
          return false;
        };
        const _isHeadingLike = (text: string): boolean => {
          if (_isFullHeading(text)) return true;
          const skipped = text.replace(/^\s*\d{1,3}\s+/, "");
          return skipped !== text && _isFullHeading(skipped);
        };
        // Strip a leading "page-number [+ numbered heading]" prefix from a position.
        // Needed because _findSentBounds scans backward for a sentence-ending period and
        // treats "1." / "4.4." as abbreviations, so pStart often lands at position 0 on
        // pages that begin with a section heading — swallowing page number and heading
        // into the highlight.
        // Check whether the whitespace run starting at a given raw index contains a newline.
        const _wsRunHasNewline = (rawIdx: number): boolean => {
          for (let i = rawIdx; i < rawPageText.length; i++) {
            const ch = rawPageText[i];
            if (ch === "\n") return true;
            if (ch !== " " && ch !== "\r" && ch !== "\t") return false;
          }
          return false;
        };
        // Split cleanText (starting at pos) into "lines" using whitespace runs that cross
        // a newline in raw as line boundaries. Strip leading lines that are page numbers
        // or numbered section headings; stop at the first content line.
        const _stripLeadingHeading = (pos: number): number => {
          let p = pos;
          const ws = cleanText.slice(p, Math.min(cleanText.length, p + 10)).match(/^\s+/);
          if (ws) p += ws[0].length;
          const endScan = Math.min(cleanText.length, p + 200);
          const lines: Array<[number, number]> = [];
          let lineStart = p;
          for (let i = p; i < endScan; i++) {
            if (cleanText[i] === " ") {
              const rawIdx = cleanToRaw[i];
              if (rawIdx != null && _wsRunHasNewline(rawIdx)) {
                lines.push([lineStart, i]);
                lineStart = i + 1;
              }
            }
          }
          lines.push([lineStart, endScan]);
          let result = p;
          // Only strip pure page-number lines; keep heading lines (e.g. "4.4. Transferpotential")
          // as part of the marked content.
          for (const [ls, le] of lines) {
            const lineText = cleanText.slice(ls, le).trim();
            if (/^\d{1,3}$/.test(lineText)) { result = le + 1; continue; }
            break;
          }
          return Math.min(result, cleanText.length);
        };
        // Expand to paragraph bounds: walk sentence-by-sentence backwards/forwards,
        // stopping at a paragraph break or heading.
        const _findParaBounds = (startPos: number, endPos: number): [number, number] => {
          const [sStart0, sEnd0] = _findSentBounds(startPos, endPos);
          let pStart = _stripLeadingHeading(sStart0);
          if (pStart >= endPos) pStart = sStart0; // safety: don't strip past the match
          for (let attempts = 0; attempts < 40 && pStart > 0; attempts++) {
            if (_isParagraphBreakBefore(pStart)) break;
            let prevEnd = pStart - 1;
            while (prevEnd > 0 && cleanText[prevEnd] === " ") prevEnd--;
            if (prevEnd <= 0) { pStart = 0; break; }
            const [rawPrevStart] = _findSentBounds(prevEnd, prevEnd);
            // Skip any leading page-num lines so prevStart lands at real content.
            const prevStart = _stripLeadingHeading(rawPrevStart);
            if (prevStart >= pStart) break;
            const prevText = cleanText.slice(prevStart, prevEnd + 1);
            if (_isHeadingLike(prevText)) break;
            pStart = prevStart;
          }
          let pEnd = sEnd0;
          for (let attempts = 0; attempts < 40 && pEnd < cleanText.length - 1; attempts++) {
            let nextStart = pEnd + 1;
            while (nextStart < cleanText.length && cleanText[nextStart] === " ") nextStart++;
            if (nextStart >= cleanText.length) break;
            if (_isParagraphBreakBefore(nextStart)) break;
            const [, nextEnd] = _findSentBounds(nextStart, nextStart);
            if (nextEnd <= pEnd) break;
            const nextText = cleanText.slice(nextStart, nextEnd + 1);
            if (_isHeadingLike(nextText)) break;
            pEnd = nextEnd;
          }
          return [pStart, pEnd];
        };

        // Default to paragraph expansion. Skip when the full search text matched verbatim
        // (popup selection — user already defined the bounds). Fall back to sentence
        // expansion if the paragraph is unreasonably long (wall-of-text PDFs).
        let sentStart: number, sentEnd: number;
        if (exactFullMatch) {
          const stripped = _stripLeadingHeading(matchStart);
          sentStart = stripped < matchEnd ? stripped : matchStart;
          sentEnd = matchEnd;
        } else {
          [sentStart, sentEnd] = _findParaBounds(matchStart, matchEnd);
          if (sentEnd - sentStart > 2500) {
            [sentStart, sentEnd] = _findSentBounds(matchStart, matchEnd);
          }
        }

        const rawStart = cleanToRaw[sentStart];
        const rawEnd = cleanToRaw[sentEnd];

        const phantoms = totalChars - rawPageText.length;
        const findGeo = (rawIdx: number): Promise<number> => {
          if (phantoms === 0) return Promise.resolve(rawIdx);
          let lo = rawIdx + 1, hi = Math.min(rawIdx + 1 + phantoms, totalChars);
          const step = (): Promise<number> => {
            if (lo >= hi) return Promise.resolve(lo - 1);
            const mid = (lo + hi) >> 1;
            const t = engine.getTextSlices?.(doc, [{ pageIndex: targetPageIndex, charIndex: 0, charCount: mid }]);
            return (t?.toPromise?.() ?? Promise.resolve(null)).then((res: unknown) => {
              const len = (res as string[])?.[0]?.length ?? 0;
              if (len < rawIdx + 1) lo = mid + 1; else hi = mid;
              return step();
            });
          };
          return step();
        };

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const selInstance = (r.getPlugin?.("selection") as any);
        const docId2 = docMgr.getActiveDocumentId?.();
        if (!selInstance?.applyInstantSelection || !docId2) return false;

        return Promise.all([findGeo(rawStart), findGeo(rawEnd)]).then(([geoStart, geoEnd]) => {
          selInstance.applyInstantSelection(docId2, targetPageIndex, geoStart, geoEnd, "default");
          prevHighlightRef.current = { pageIndex: targetPageIndex, ids: [] };

          // Scroll to center the highlighted text
          let targetRun = g.runs[0];
          for (const run of g.runs) {
            if (run.charStart > geoStart) break;
            targetRun = run;
          }
          if (targetRun?.rect && scroll) {
            scroll.scrollToPage({
              pageNumber: targetPageIndex + 1,
              pageCoordinates: { x: 0, y: targetRun.rect.y },
              behavior: "instant",
              alignY: 50,
            });
          }
          return true;
        });
      });
    }).catch(() => false);
  }

  function doHighlightSearch(reg: unknown, page: number, text: string) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = reg as any;
    const scroll = r.getPlugin?.("scroll")?.provides?.();
    scroll?.scrollToPage?.({ pageNumber: page, behavior: "instant" });

    const engine = r.getEngine?.();
    const docMgr = r.getPlugin?.("document-manager")?.provides?.();
    if (!engine || !docMgr) return;

    const doc = docMgr.getActiveDocument?.();
    if (!doc) return;

    // Clear previous highlight (selection) before applying a new one — otherwise
    // successive chip clicks accumulate marks across pages.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const selCap = r.getPlugin?.("selection")?.provides?.() as any;
    const activeDocId = docMgr.getActiveDocumentId?.();
    try { selCap?.clear?.(activeDocId); } catch { /* ignore */ }
    prevHighlightRef.current = null;

    if (!text?.trim()) return;

    const pageIndex = page - 1;
    const totalPages = doc.pages?.length ?? 0;

    // Try cited page first, then nearby pages, then all others
    tryHighlightOnPage(r, doc, engine, docMgr, scroll, pageIndex, text).then((found) => {
      if (found) return;
      // Search nearby pages first (±2), then remaining
      const nearby = [pageIndex - 1, pageIndex + 1, pageIndex - 2, pageIndex + 2];
      const remaining: number[] = [];
      for (let i = 0; i < totalPages; i++) {
        if (i !== pageIndex && !nearby.includes(i)) remaining.push(i);
      }
      const candidates = [...nearby.filter(i => i >= 0 && i < totalPages), ...remaining];

      let chain: Promise<boolean> = Promise.resolve(false);
      for (const pi of candidates) {
        chain = chain.then((f) => f ? Promise.resolve(true) : tryHighlightOnPage(r, doc, engine, docMgr, scroll, pi, text));
      }
    });
  }

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
        pendingHighlightRef.current = { page: source.page, text: source.highlightText };
      }
      return;
    }

    if (source.highlightText) {
      doHighlightSearch(reg, source.page, source.highlightText);
    } else {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const scroll = (reg as any).getPlugin?.("scroll")?.provides?.();
      scroll?.scrollToPage?.({ pageNumber: source.page, behavior: "instant", alignY: 50 });
    }

  }, [source.nonce, source.page, source.highlightText]);

  const handleReady = useCallback((registry: unknown) => {
    registryRef.current = registry;
    setRegistryReady(true);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const reg = registry as any;

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
          doHighlightSearch(registry, pending.page, pending.text);
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

    // Merge: add KI actions to selection menu + summary button to main toolbar
    const existingSchema = ui.getSchema?.();
    const existingSelItems: unknown[] = existingSchema?.selectionMenus?.selection?.items ?? [];
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
            ...existingSelItems,
            { type: "divider", id: "kis-custom-divider", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.add-to-glossary", commandId: "kis.add-to-glossary", variant: "icon", categories: ["kis-actions"] },
            { type: "command-button", id: "kis.custom-question", commandId: "kis.custom-question", variant: "icon", categories: ["kis-actions"] },
            ...(actions?.length ? [
              { type: "divider", id: "kis-divider", categories: ["kis-actions"] },
              ...actions.map(a => ({
                type: "command-button",
                id: `kis.${a.key}`,
                commandId: `kis.${a.key}`,
                variant: "icon",
                categories: ["kis-actions"],
              })),
            ] : []),
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
                  style={{ padding: "6px 16px", fontSize: 12, borderRadius: 6, border: "1px solid var(--color-fg-accent, #60a5fa)", background: "var(--color-bg-accent, #1e3a5f)", color: "#fff", cursor: "pointer", fontWeight: 500 }}
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
