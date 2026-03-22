"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowSquareOut,
  CaretLeft,
  CaretRight,
  Chat,
  Check,
  FilePdf,
  PaperPlaneRight,
  Plus,
  SidebarSimple,
  Cards,
  Question,
  Wrench,
  XIcon,
  ArrowsCounterClockwise,
  Scissors,
  MagnifyingGlassPlus,
  ListBullets,
  Lightbulb,
  BookOpenText,
  GearSix,
} from "@phosphor-icons/react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import type { AuthStatus } from "@/types";
import { Document, Page as PdfPage, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

// ─── Types ────────────────────────────────────────────────────────────────────

interface ModuleDetail {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  is_active: boolean;
  sources: Source[];
}

interface Source {
  uuid: string;
  filename: string;
  status: "pending" | "indexing" | "ready" | "failed";
  error_message?: string | null;
}

interface SourceRef {
  source_uuid: string;
  filename?: string;
  page_number: number;
}

interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  source_pages?: SourceRef[];
}

interface LernKarte {
  front: string;
  back: string;
}

interface QuizQuestion {
  question: string;
  options: string[];
  correct: number;
}

interface ViewerState {
  uuid: string;
  filename: string;
  page: number;
}

type StudioView = "overview" | "lernkarten" | "quiz";
type PanelKey = "quellen" | "chat" | "studio";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseLernkarten(text: string): LernKarte[] {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const karten: LernKarte[] = [];
  for (const line of lines) {
    const sepIdx = line.indexOf(" | ");
    if (sepIdx !== -1) {
      const front = line.slice(0, sepIdx).replace(/^\d+[.)]\s*/, "").trim();
      const back = line.slice(sepIdx + 3).trim();
      if (front && back) karten.push({ front, back });
    }
  }
  return karten;
}

function parseQuiz(text: string): QuizQuestion[] {
  const questions: QuizQuestion[] = [];
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  let current: { question: string; options: string[]; correct: number } | null = null;
  for (const line of lines) {
    const qMatch = line.match(/^\d+[.)]\s+(.+)$/);
    const optMatch = line.match(/^[A-Da-d][.)]\s+(.+)$/);
    if (qMatch) {
      if (current && current.options.length > 0) questions.push(current);
      current = { question: qMatch[1], options: [], correct: 0 };
    } else if (optMatch && current) {
      const isCorrect = line.includes("✓") || line.includes("(richtig)");
      const optText = optMatch[1].replace(/[✓(richtig)]/g, "").trim();
      if (isCorrect) current.correct = current.options.length;
      current.options.push(optText);
    }
  }
  if (current && current.options.length > 0) questions.push(current);
  return questions;
}

// ─── Source Status ─────────────────────────────────────────────────────────────

function SourceStatus({ status }: { status: string }) {
  if (status === "pending" || status === "indexing")
    return (
      <span
        className="inline-block h-3 w-3 rounded-full border-[1.5px] border-transparent animate-spin flex-shrink-0"
        style={{ borderTopColor: "#B45309", borderRightColor: "#B45309" }}
        title={status === "pending" ? "Warte auf Verarbeitung" : "Wird indiziert"}
      />
    );
  if (status === "ready")
    return <Check size={12} weight="bold" className="flex-shrink-0" style={{ color: "#15803D" }} />;
  return (
    <span title="Indizierung fehlgeschlagen" className="flex-shrink-0 inline-flex">
      <XIcon size={12} weight="bold" style={{ color: "#B91C1C" }} />
    </span>
  );
}

// ─── File Icon ─────────────────────────────────────────────────────────────────

function FileIcon({ filename }: { filename: string }) {
  const isPdf = filename.toLowerCase().endsWith(".pdf");
  return (
    <div
      className="flex-shrink-0 w-8 h-8 rounded flex items-center justify-center"
      style={{ backgroundColor: isPdf ? "#FEE2E2" : "#DBEAFE" }}
    >
      <FilePdf size={16} weight="bold" color={isPdf ? "#B91C1C" : "#1D4ED8"} />
    </div>
  );
}

// ─── PDF Viewer ────────────────────────────────────────────────────────────────

function PdfViewer({
  source, onClose, moduleUuid, onAskWithSelection,
}: {
  source: ViewerState;
  onClose: () => void;
  moduleUuid: string;
  onAskWithSelection?: (text: string) => void;
}) {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(source.page);
  const [containerWidth, setContainerWidth] = useState(0);
  const [showSearch, setShowSearch] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchMatches, setSearchMatches] = useState<number[]>([]);
  const [searchMatchIdx, setSearchMatchIdx] = useState(0);
  const [searchLoading, setSearchLoading] = useState(false);
  const [selectionPopup, setSelectionPopup] = useState<{ x: number; y: number; text: string } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setPage(source.page), [source.page]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width - 32));
    ro.observe(el);
    setContainerWidth(el.clientWidth - 32);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (showSearch) setTimeout(() => searchInputRef.current?.focus(), 50);
  }, [showSearch]);

  // Highlight search matches using CSS Highlight API (exact text, no DOM mutation)
  useEffect(() => {
    const hl = (CSS as any).highlights as Map<string, unknown> | undefined;
    if (hl) { hl.delete('pdf-search'); hl.delete('pdf-search-active'); }
    const q = searchQuery.trim();
    if (!q) return;
    const apply = () => {
      const textLayer = containerRef.current?.querySelector('.textLayer');
      if (!textLayer) return;
      const lq = q.toLowerCase();
      const allRanges: Range[] = [];
      const walker = document.createTreeWalker(textLayer, NodeFilter.SHOW_TEXT);
      let node: Node | null;
      while ((node = walker.nextNode())) {
        const text = node.textContent ?? '';
        const lower = text.toLowerCase();
        let idx = 0;
        while ((idx = lower.indexOf(lq, idx)) !== -1) {
          const r = document.createRange();
          r.setStart(node, idx);
          r.setEnd(node, idx + q.length);
          allRanges.push(r);
          idx += lq.length;
        }
      }
      if (allRanges.length > 0 && hl) {
        const HLClass = (window as any).Highlight;
        hl.set('pdf-search', new HLClass(...allRanges));
        hl.set('pdf-search-active', new HLClass(allRanges[searchMatchIdx] ?? allRanges[0]));
      }
    };
    const timer = setTimeout(apply, 350);
    return () => {
      clearTimeout(timer);
      const h = (CSS as any).highlights as Map<string, unknown> | undefined;
      if (h) { h.delete('pdf-search'); h.delete('pdf-search-active'); }
    };
  }, [searchQuery, page, searchMatchIdx]);

  // Text selection popup
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    function onMouseUp() {
      setTimeout(() => {
        const sel = window.getSelection();
        const text = sel?.toString().trim() ?? "";
        if (text.length > 5) {
          const range = sel!.getRangeAt(0).getBoundingClientRect();
          const cont = containerRef.current!.getBoundingClientRect();
          setSelectionPopup({ x: range.left - cont.left + range.width / 2, y: range.top - cont.top - 8, text });
        } else {
          setSelectionPopup(null);
        }
      }, 10);
    }
    function onMouseDown(e: MouseEvent) {
      // Don't clear popup if clicking the popup button itself
      const target = e.target as HTMLElement;
      if (target.closest('[data-selection-popup]')) return;
      setSelectionPopup(null);
    }
    el.addEventListener("mouseup", onMouseUp);
    el.addEventListener("mousedown", onMouseDown);
    return () => { el.removeEventListener("mouseup", onMouseUp); el.removeEventListener("mousedown", onMouseDown); };
  }, []);

  async function runSearch(q: string, goToIdx = 0) {
    if (!q) return;
    setSearchLoading(true);
    try {
      const pdfjsLib = await import("pdfjs-dist");
      const pdf = await pdfjsLib.getDocument(`/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/file`).promise;
      const matches: number[] = [];
      for (let i = 1; i <= pdf.numPages; i++) {
        const pg = await pdf.getPage(i);
        const content = await pg.getTextContent();
        const text = content.items.map((item: any) => ("str" in item ? item.str : "")).join(" ").toLowerCase();
        if (text.includes(q)) matches.push(i);
      }
      setSearchMatches(matches);
      if (matches.length > 0) {
        const idx = Math.max(0, Math.min(goToIdx, matches.length - 1));
        setSearchMatchIdx(idx);
        setPage(matches[idx]);
      }
    } catch { /* ignore */ } finally {
      setSearchLoading(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = searchQuery.trim().toLowerCase();
    if (!q) return;
    if (searchMatches.length > 0) {
      // Already searched — go to next match
      const nextIdx = (searchMatchIdx + 1) % searchMatches.length;
      setSearchMatchIdx(nextIdx);
      setPage(searchMatches[nextIdx]);
    } else {
      await runSearch(q, 0);
    }
  }

  function searchNav(dir: 1 | -1) {
    if (searchMatches.length === 0) return;
    const nextIdx = (searchMatchIdx + dir + searchMatches.length) % searchMatches.length;
    setSearchMatchIdx(nextIdx);
    setPage(searchMatches[nextIdx]);
  }

  return (
    <div className="flex flex-col h-full relative" ref={containerRef}>
      {/* Selection popup */}
      {selectionPopup && onAskWithSelection && (
        <div
          data-selection-popup
          className="absolute z-50"
          style={{ left: selectionPopup.x, top: selectionPopup.y, transform: "translate(-50%, -100%)", pointerEvents: "auto" }}
        >
          <div
            className="grid grid-cols-2 gap-1 rounded-xl p-2 shadow-xl"
            style={{ backgroundColor: "#004261", border: "1px solid rgba(255,255,255,0.15)", minWidth: 340 }}
          >
            {([
              { label: "Umformulieren", Icon: ArrowsCounterClockwise, prompt: "Formuliere diese Textstelle in anderen Worten um, verständlich für Studierende:", minWords: 1 },
              { label: "Kürzen", Icon: Scissors, prompt: "Kürze diesen Text auf das Wesentliche. Antworte nur mit dem gekürzten Text, ohne Erklärungen:", minWords: 3 },
              { label: "Genauer ausführen", Icon: MagnifyingGlassPlus, prompt: "Führe diese Textstelle genauer aus. Erkläre die Konzepte ausführlich und gib konkrete Beispiele:", minWords: 1 },
              { label: "Zusammenfassung", Icon: BookOpenText, prompt: "Fasse diese Textstelle kompakt zusammen und hebe die Kernaussagen hervor:", minWords: 1 },
              { label: "Stichpunkte", Icon: ListBullets, prompt: "Wandle diese Textstelle in prägnante Stichpunkte um:", minWords: 1 },
              { label: "Vereinfachen", Icon: Lightbulb, prompt: "Erkläre diese Textstelle auf einem einfachen Sprachniveau (B1-Niveau). Nutze kurze Sätze, einfache Wörter und vermeide komplizierte Fachausdrücke soweit möglich:", minWords: 1 },
            ] as const).filter(({ minWords }) => selectionPopup.text.trim().split(/\s+/).length >= minWords)
            .map(({ label, Icon, prompt }) => (
              <button
                key={label}
                type="button"
                onClick={() => { onAskWithSelection(`${prompt}\n\n"${selectionPopup.text}"`); setSelectionPopup(null); window.getSelection()?.removeAllRanges(); }}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-white hover:bg-white/20 transition-colors w-full"
                style={{ border: "1px solid rgba(255,255,255,0.15)" }}
              >
                <Icon size={13} weight="bold" />
                {label}
              </button>
            ))}
          </div>
          <div style={{ width: 0, height: 0, borderLeft: "8px solid transparent", borderRight: "8px solid transparent", borderTop: "8px solid #004261", margin: "0 auto" }} />
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--text)" }}>{source.filename}</span>
        <button
          type="button"
          onClick={() => { setShowSearch((v) => { if (v) { setSearchQuery(""); setSearchMatches([]); setSearchMatchIdx(0); } return !v; }); }}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: showSearch ? "#004261" : "var(--border)" }}
          title="Suchen"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke={showSearch ? "white" : "var(--muted)"} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--border)" }}
        >
          <XIcon size={13} color="var(--muted)" />
        </button>
      </div>

      {/* Search bar */}
      {showSearch && (
        <form onSubmit={handleSearch} className="flex items-center gap-2 px-3 py-2 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
          <input
            ref={searchInputRef}
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setSearchMatches([]); setSearchMatchIdx(0); }}
            onKeyDown={(e) => { if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); searchNav(-1); } }}
            placeholder="Suchen…"
            className="flex-1 text-sm bg-transparent focus:outline-none min-w-0"
            style={{ color: "var(--text)" }}
          />
          {searchLoading && <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 flex-shrink-0" style={{ borderColor: "#004261" }} />}
          {searchMatches.length > 0 && !searchLoading && (
            <span className="text-xs flex-shrink-0 tabular-nums" style={{ color: "var(--muted)" }}>{searchMatchIdx + 1}/{searchMatches.length}</span>
          )}
          {searchMatches.length === 0 && !searchLoading && searchQuery.trim() && (
            <span className="text-xs flex-shrink-0" style={{ color: "#B91C1C" }}>–</span>
          )}
          <button type="button" onClick={() => searchNav(-1)} disabled={searchMatches.length === 0}
            className="w-6 h-6 flex items-center justify-center rounded disabled:opacity-30" title="Vorheriger Treffer (Shift+Enter)">
            <CaretLeft size={12} />
          </button>
          <button type="submit" className="w-6 h-6 flex items-center justify-center rounded disabled:opacity-30" title="Nächster Treffer (Enter)">
            <CaretRight size={12} />
          </button>
          <button type="button" onClick={() => { setShowSearch(false); setSearchQuery(""); setSearchMatches([]); setSearchMatchIdx(0); }}>
            <XIcon size={13} color="var(--muted)" />
          </button>
        </form>
      )}

      <div className="flex-1 overflow-y-auto p-4 flex flex-col items-center">
        {containerWidth > 0 && (
          <Document
            file={`/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/file`}
            onLoadSuccess={({ numPages: n }) => setNumPages(n)}
            loading={<div className="flex items-center justify-center py-10"><div className="animate-spin rounded-full h-6 w-6 border-b-2" style={{ borderColor: "#004261" }} /></div>}
            error={<p className="text-sm text-center py-8" style={{ color: "#B91C1C" }}>PDF konnte nicht geladen werden.</p>}
          >
            <PdfPage pageNumber={page} width={containerWidth} renderTextLayer renderAnnotationLayer={false} />
          </Document>
        )}
      </div>

      {numPages > 0 && (
        <div className="flex items-center justify-center gap-3 px-4 py-3 flex-shrink-0" style={{ borderTop: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
            className="w-8 h-8 flex items-center justify-center rounded-full disabled:opacity-30 hover:opacity-70 transition-opacity" style={{ backgroundColor: "var(--border)" }}>
            <CaretLeft size={14} />
          </button>
          <span className="text-sm tabular-nums" style={{ color: "var(--muted)" }}>{page} / {numPages}</span>
          <button type="button" onClick={() => setPage((p) => Math.min(numPages, p + 1))} disabled={page >= numPages}
            className="w-8 h-8 flex items-center justify-center rounded-full disabled:opacity-30 hover:opacity-70 transition-opacity" style={{ backgroundColor: "var(--border)" }}>
            <CaretRight size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Sources Panel ─────────────────────────────────────────────────────────────

function SourcesPanel({
  sources,
  selectedSourceIds,
  onToggleSource,
  onOpenViewer,
  onDeleteSource,
  onUpload,
  uploadProgress,
  isLecturer,
  onMinimize,
}: {
  sources: Source[];
  selectedSourceIds: string[];
  onToggleSource: (uuid: string) => void;
  onOpenViewer: (source: Source) => void;
  onDeleteSource: (uuid: string) => void;
  onUpload: (file: File) => void;
  uploadProgress: number | null;
  isLecturer: boolean;
  onMinimize: () => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  useEffect(() => {
    if (!openMenuId) return;
    function handle(e: MouseEvent) {
      if (!(e.target as HTMLElement).closest("[data-source-menu]")) setOpenMenuId(null);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [openMenuId]);

  const allSelected = sources.length > 0 && sources.every((s) => selectedSourceIds.includes(s.uuid));

  function toggleAll() {
    if (allSelected) {
      // deselect all
      sources.forEach((s) => { if (selectedSourceIds.includes(s.uuid)) onToggleSource(s.uuid); });
    } else {
      // select all ready
      sources.filter((s) => s.status === "ready" && !selectedSourceIds.includes(s.uuid))
        .forEach((s) => onToggleSource(s.uuid));
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-4 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span className="text-sm font-semibold tracking-wide" style={{ color: "var(--text)" }}>
          Quellen
        </span>
        <button
          type="button"
          onClick={onMinimize}
          className="w-7 h-7 flex items-center justify-center rounded-lg hover:opacity-60 transition-opacity"
          style={{ color: "var(--muted)" }}
          title="Panel minimieren"
        >
          <SidebarSimple size={16} />
        </button>
      </div>

      {/* Upload button (lecturer) */}
      {isLecturer && (
        <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.docx,.pptx,.md"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) { onUpload(f); e.target.value = ""; }
            }}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
            style={{ backgroundColor: "rgba(0,66,97,0.08)", color: "#004261", border: "1.5px dashed rgba(0,66,97,0.3)" }}
          >
            <Plus size={15} weight="bold" />
            Quelle hinzufügen
          </button>

          {uploadProgress !== null && (
            <div className="mt-2">
              <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%`, backgroundColor: "#004261" }}
                />
              </div>
              <p className="text-[11px] mt-1" style={{ color: "var(--muted)" }}>
                Hochladen… {uploadProgress}%
              </p>
            </div>
          )}
        </div>
      )}

      {/* Select all row */}
      {sources.length > 0 && (
        <div
          className="flex items-center gap-3 px-4 py-2 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
            className="w-3.5 h-3.5 flex-shrink-0 accent-[#004261]"
          />
          <span className="text-xs" style={{ color: "var(--muted)" }}>
            Alle auswählen
          </span>
        </div>
      )}

      {/* Source list */}
      <div className="flex-1 overflow-y-auto">
        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 gap-2">
            <FilePdf size={32} color="var(--border)" />
            <p className="text-xs text-center" style={{ color: "var(--muted)" }}>
              Noch keine Quellen vorhanden.
            </p>
          </div>
        ) : (
          sources.map((src) => (
            <div
              key={src.uuid}
              className="relative flex items-center gap-3 px-4 py-2.5 transition-colors"
              style={{ borderBottom: "1px solid var(--border)" }}
            >
              <input
                type="checkbox"
                checked={selectedSourceIds.includes(src.uuid)}
                onChange={() => onToggleSource(src.uuid)}
                className="flex-shrink-0 w-3.5 h-3.5 accent-[#004261]"
                onClick={(e) => e.stopPropagation()}
              />
              <FileIcon filename={src.filename} />
              <span
                className="flex-1 text-xs leading-snug truncate min-w-0 font-medium"
                style={{ color: "var(--text)" }}
                title={src.filename}
              >
                {src.filename}
              </span>

              {src.status === "failed" && src.error_message && (
                <div
                  className="absolute left-4 right-4 top-full z-10 mt-1 rounded-lg px-3 py-2 text-[11px] leading-snug shadow-lg"
                  style={{ backgroundColor: "#FEF2F2", border: "1px solid #FECACA", color: "#991B1B" }}
                >
                  {src.error_message}
                </div>
              )}

              <div className="flex items-center gap-1 flex-shrink-0">
                <SourceStatus status={src.status} />
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onOpenViewer(src); }}
                  className="w-6 h-6 flex items-center justify-center rounded hover:opacity-70 transition-opacity"
                  style={{ color: "#004261" }}
                  title="Im Viewer öffnen"
                >
                  <ArrowSquareOut size={14} />
                </button>
                {isLecturer && (
                  <div className="relative" data-source-menu>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setOpenMenuId(openMenuId === src.uuid ? null : src.uuid); }}
                      className="w-6 h-6 flex items-center justify-center rounded hover:opacity-70 transition-opacity"
                      style={{ color: "var(--muted)" }}
                      title="Optionen"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
                      </svg>
                    </button>
                    {openMenuId === src.uuid && (
                      <div
                        className="absolute right-0 top-7 z-50 rounded-xl py-1"
                        style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 160, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}
                      >
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onDeleteSource(src.uuid); setOpenMenuId(null); }}
                          className="w-full text-left px-4 py-2.5 text-sm hover:bg-black/5 transition-colors"
                          style={{ color: "#B91C1C" }}
                        >
                          Löschen
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ─── Chat Panel ────────────────────────────────────────────────────────────────

function ChatPanel({
  messages,
  activeSourceIds,
  sources,
  loading,
  input,
  onInputChange,
  onSend,
  onPillClick,
  moduleReady,
  onClear,
}: {
  messages: ChatMessage[];
  activeSourceIds: string[];
  sources: Source[];
  loading: boolean;
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onPillClick: (sourceUuid: string, page: number, filename: string) => void;
  moduleReady: boolean;
  onClear: () => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const chatMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!chatMenuOpen) return;
    function handle(e: MouseEvent) {
      if (!chatMenuRef.current?.contains(e.target as Node)) setChatMenuOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [chatMenuOpen]);

  useEffect(() => {
    if (isFirstRender.current) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" });
      isFirstRender.current = false;
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const getFilename = (srcUuid: string) =>
    sources.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0 relative" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Chat</span>
        <div className="relative" ref={chatMenuRef}>
          <button
            type="button"
            onClick={() => setChatMenuOpen((v) => !v)}
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:opacity-70 transition-opacity"
            style={{ color: "var(--muted)" }}
            title="Optionen"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="5" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="12" cy="19" r="1.5"/>
            </svg>
          </button>
          {chatMenuOpen && (
            <div
              className="absolute right-0 top-8 z-50 rounded-xl py-1"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 220, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}
            >
              <button
                type="button"
                onClick={() => { onClear(); setChatMenuOpen(false); }}
                disabled={messages.length === 0}
                className="w-full text-left px-4 py-2.5 text-sm hover:bg-black/5 disabled:opacity-40 transition-colors"
                style={{ color: "var(--text)" }}
              >
                Chatprotokoll löschen
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full px-6 py-6 flex flex-col gap-5" style={{ maxWidth: 720 }}>
        {messages.length === 0 && !loading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 py-16">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: "rgba(0,66,97,0.08)" }}
            >
              <Chat size={22} style={{ color: "#004261" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
              Stell eine Frage
            </p>
            <p className="text-xs text-center max-w-xs" style={{ color: "var(--muted)" }}>
              Wähle Quellen links aus und stelle eine Frage – die KI antwortet auf Basis deiner Materialien.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={msg.id ?? i}
            className={`flex flex-col gap-1.5 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex items-center gap-2 mb-0.5">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: "#004261" }}
                >
                  KI
                </div>
                <span className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>
                  KI Tutor
                </span>
              </div>
            )}
            <div
              className="max-w-[84%] px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed"
              style={
                msg.role === "user"
                  ? { backgroundColor: "#004261", color: "white", borderBottomRightRadius: 6 }
                  : { backgroundColor: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderBottomLeftRadius: 6 }
              }
            >
              {msg.content}
            </div>
            {msg.source_pages && msg.source_pages.length > 0 && (
              <div className="flex flex-wrap gap-1.5 max-w-[84%] mt-0.5">
                {msg.source_pages.map((sp, j) => (
                  <button
                    key={j}
                    type="button"
                    onClick={() => onPillClick(sp.source_uuid, sp.page_number, getFilename(sp.source_uuid))}
                    className="text-[11px] px-2.5 py-1 rounded-full font-medium hover:opacity-80 transition-opacity flex items-center gap-1"
                    style={{ backgroundColor: "rgba(0,66,97,0.1)", color: "#004261" }}
                    title={`${getFilename(sp.source_uuid)}, S. ${sp.page_number}`}
                  >
                    <FilePdf size={10} weight="bold" />
                    S. {sp.page_number}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex flex-col gap-1.5 items-start">
            <div className="flex items-center gap-2 mb-0.5">
              <div
                className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                style={{ backgroundColor: "#004261" }}
              >
                KI
              </div>
            </div>
            <div
              className="px-4 py-3 rounded-2xl text-sm flex items-center gap-2"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", borderBottomLeftRadius: 6 }}
            >
              <span className="inline-flex gap-1">
                {[0, 1, 2].map((n) => (
                  <span
                    key={n}
                    className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                    style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                  />
                ))}
              </span>
              <span className="text-xs" style={{ color: "var(--muted)" }}>Denkt nach…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      </div>

      {/* Input area */}
      <div
        className="flex-shrink-0 px-6 pt-4 pb-0"
        style={{ borderTop: "1px solid var(--border)" }}
      >
      <div className="mx-auto w-full" style={{ maxWidth: 720 }}>
        {!moduleReady && (
          <div
            className="mb-2 rounded-xl px-3 py-2 text-[11px] text-center"
            style={{ backgroundColor: "rgba(0,66,97,0.06)", color: "var(--muted)" }}
          >
            Quellen werden noch indiziert – Chat steht gleich bereit.
          </div>
        )}
        <div
          className="flex items-end gap-2 rounded-2xl px-4 py-3"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <textarea
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
            }}
            placeholder="Frage stellen… (Enter zum Senden)"
            rows={1}
            disabled={loading}
            className="flex-1 text-sm resize-none focus:outline-none disabled:opacity-50 bg-transparent"
            style={{ color: "var(--text)", maxHeight: 120, overflowY: "auto" }}
          />
          <button
            type="button"
            onClick={onSend}
            disabled={loading || !input.trim() || activeSourceIds.length === 0}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-opacity hover:opacity-85"
            style={{ backgroundColor: "#004261" }}
            title="Senden"
          >
            <PaperPlaneRight size={16} weight="bold" />
          </button>
        </div>
        <div className="flex items-center justify-between mt-2 px-1">
          <span className="text-[11px]" style={{ color: "var(--muted)" }}>
            {activeSourceIds.length} {activeSourceIds.length === 1 ? "Quelle" : "Quellen"} aktiv
          </span>
          <span className="text-[11px]" style={{ color: "var(--muted)" }}>
            Shift+Enter für Zeilenumbruch
          </span>
        </div>
        <p className="text-center mt-3 pb-0 text-[10px]" style={{ color: "var(--muted)", opacity: 0.5 }}>
          Diese Plattform nutzt KI und kann Fehler machen. Bitte überprüfen Sie alle Ergebnisse.
        </p>
      </div>
      </div>
    </div>
  );
}

// ─── Flip Card ─────────────────────────────────────────────────────────────────

function FlipCard({ front, back, flipped, onFlip }: { front: string; back: string; flipped: boolean; onFlip: () => void }) {
  return (
    <div
      style={{ perspective: 1000, height: 120, cursor: "pointer" }}
      onClick={onFlip}
      title="Klicken zum Umdrehen"
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: "100%",
          transformStyle: "preserve-3d",
          transition: "transform 0.45s cubic-bezier(0.4,0,0.2,1)",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        <div
          style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            backgroundColor: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", padding: "12px 16px", gap: 6,
          }}
        >
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--muted)" }}>
            Vorderseite
          </span>
          <p className="text-xs text-center leading-snug" style={{ color: "var(--text)" }}>{front}</p>
        </div>
        <div
          style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
            backgroundColor: "rgba(0,66,97,0.06)", border: "1.5px solid rgba(0,66,97,0.2)",
            borderRadius: 12, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center", padding: "12px 16px", gap: 6,
          }}
        >
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(0,66,97,0.5)" }}>
            Rückseite
          </span>
          <p className="text-xs text-center leading-snug font-medium" style={{ color: "#004261" }}>{back}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Studio Subviews ──────────────────────────────────────────────────────────

function SubviewHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <div
      className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <button
        type="button"
        onClick={onBack}
        className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
        style={{ backgroundColor: "var(--border)" }}
      >
        <CaretLeft size={13} />
      </button>
      <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{title}</span>
    </div>
  );
}

function LernkartenStudio({
  karten, loading, flippedCards, onGenerate, onFlip, onBack,
}: {
  karten: LernKarte[]; loading: boolean; flippedCards: Set<number>;
  onGenerate: () => void; onFlip: (i: number) => void; onBack: () => void;
}) {
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Lernkarten" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
        <button
          type="button"
          onClick={onGenerate}
          disabled={loading}
          className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity hover:opacity-90"
          style={{ backgroundColor: "#004261" }}
        >
          {loading ? "Generieren…" : "🃏 Lernkarten generieren"}
        </button>
        {karten.length > 0 && (
          <p className="text-[11px] text-center" style={{ color: "var(--muted)" }}>
            Karte antippen zum Umdrehen
          </p>
        )}
        {karten.map((k, i) => (
          <FlipCard key={i} front={k.front} back={k.back} flipped={flippedCards.has(i)} onFlip={() => onFlip(i)} />
        ))}
      </div>
    </div>
  );
}

function QuizStudio({
  questions, loading, answers, onGenerate, onAnswer, onBack,
}: {
  questions: QuizQuestion[]; loading: boolean; answers: Record<number, number>;
  onGenerate: () => void; onAnswer: (qi: number, ai: number) => void; onBack: () => void;
}) {
  const correct = Object.entries(answers).filter(([qi, ai]) => questions[Number(qi)]?.correct === ai).length;
  const total = Object.keys(answers).length;

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Quiz" onBack={onBack} />
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        <button
          type="button"
          onClick={onGenerate}
          disabled={loading}
          className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity hover:opacity-90"
          style={{ backgroundColor: "#004261" }}
        >
          <span className="flex items-center justify-center gap-2">
            <Question size={16} weight="bold" />
            {loading ? "Generieren…" : "Quiz starten"}
          </span>
        </button>

        {total > 0 && questions.length > 0 && (
          <div
            className="rounded-xl p-3 text-center text-sm font-semibold"
            style={{ backgroundColor: "rgba(0,66,97,0.08)", color: "#004261" }}
          >
            {correct} / {questions.length} richtig
          </div>
        )}

        {questions.map((q, qi) => {
          const answered = answers[qi] !== undefined;
          const isCorrect = answered && answers[qi] === q.correct;
          return (
            <div key={qi} className="rounded-xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
              <p className="text-xs font-semibold mb-3 leading-snug" style={{ color: "var(--text)" }}>
                {qi + 1}. {q.question}
              </p>
              <div className="flex flex-col gap-2">
                {q.options.map((opt, ai) => {
                  let bg = "var(--bg)";
                  let border = "var(--border)";
                  let color = "var(--text)";
                  if (answered) {
                    if (ai === q.correct) { bg = "#DCFCE7"; border = "#86EFAC"; color = "#166534"; }
                    else if (ai === answers[qi]) { bg = "#FEE2E2"; border = "#FCA5A5"; color = "#991B1B"; }
                  }
                  return (
                    <button
                      key={ai}
                      type="button"
                      onClick={() => !answered && onAnswer(qi, ai)}
                      disabled={answered}
                      className="w-full text-left px-3 py-2 rounded-lg text-xs font-medium disabled:cursor-default transition-colors"
                      style={{ backgroundColor: bg, border: `1px solid ${border}`, color }}
                    >
                      {["A", "B", "C", "D"][ai]}. {opt}
                    </button>
                  );
                })}
              </div>
              {answered && (
                <p className="flex items-center gap-1 text-[11px] mt-2.5 font-semibold" style={{ color: isCorrect ? "#166534" : "#991B1B" }}>
                  {isCorrect ? <Check size={12} weight="bold" /> : <XIcon size={12} weight="bold" />}
                  {isCorrect ? "Richtig!" : "Leider falsch."}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Studio Overview ──────────────────────────────────────────────────────────

function StudioOverview({ onSelect, onMinimize, sprachtrainingActive }: { onSelect: (v: "lernkarten" | "quiz") => void; onMinimize: () => void; sprachtrainingActive: boolean }) {
  const [studioTab, setStudioTab] = useState<"tools" | "sprachtraining">("tools");
  const tiles = [
    { key: "lernkarten" as const, Icon: Cards, label: "Lernkarten", iconBg: "rgba(220,252,231,0.7)", iconColor: "#166534" },
    { key: "quiz" as const, Icon: Question, label: "Quiz", iconBg: "rgba(254,249,195,0.7)", iconColor: "#A16207" },
    { key: "pruefung" as const, Icon: BookOpenText, label: "Prüfungsfrage", iconBg: "rgba(237,233,254,0.7)", iconColor: "#534AB7" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Studio</span>
        <button
          type="button"
          onClick={onMinimize}
          className="w-7 h-7 flex items-center justify-center rounded-lg hover:opacity-60 transition-opacity"
          style={{ color: "var(--muted)" }}
          title="Panel minimieren"
        >
          <SidebarSimple size={16} style={{ transform: "scaleX(-1)" }} />
        </button>
      </div>

      {/* Tabs */}
      {sprachtrainingActive && (
        <div className="flex flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          {(["tools", "sprachtraining"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setStudioTab(tab)}
              className="flex-1 py-2 text-xs font-medium transition-colors"
              style={{
                color: studioTab === tab ? "#004261" : "var(--muted)",
                borderBottom: studioTab === tab ? "2px solid #004261" : "2px solid transparent",
              }}
            >
              {tab === "tools" ? "Lerntools" : "Sprachtraining"}
            </button>
          ))}
        </div>
      )}

      {/* Tile list */}
      {studioTab === "tools" && (
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-2">
          {tiles.map((tile) => (
            <button
              key={tile.key}
              type="button"
              onClick={() => tile.key !== "pruefung" && onSelect(tile.key as "lernkarten" | "quiz")}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-colors hover:bg-black/5"
              style={{ border: "1px solid var(--border)", backgroundColor: "var(--bg)" }}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ backgroundColor: tile.iconBg }}
              >
                <tile.Icon size={16} color={tile.iconColor} weight="bold" />
              </div>
              <span className="text-sm font-medium" style={{ color: "var(--text)" }}>
                {tile.label}
              </span>
            </button>
          ))}
        </div>
      )}

      {/* Sprachtraining Inhalt */}
      {studioTab === "sprachtraining" && (
        <div className="flex-1 p-3 overflow-y-auto flex flex-col gap-3">
          <p className="text-xs text-center py-8" style={{ color: "var(--muted)" }}>
            Glossar &amp; Vokabeltest — coming soon
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Mini Panel Strip ──────────────────────────────────────────────────────────

function MiniStrip({ label, onClick, side }: { label: string; onClick: () => void; side: "left" | "right" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center pt-4 h-full w-full gap-2 hover:opacity-70 transition-opacity"
      style={{ color: "var(--muted)" }}
      title={label}
    >
      <SidebarSimple
        size={18}
        style={{ transform: side === "right" ? "scaleX(-1)" : "none", flexShrink: 0 }}
      />
      <span
        className="text-[10px] font-semibold tracking-widest uppercase select-none"
        style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", color: "var(--muted)" }}
      >
        {label}
      </span>
    </button>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function KiTutorModulePage() {
  const params = useParams();
  const uuid = params.uuid as string;
  const router = useRouter();

  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [moduleDetail, setModuleDetail] = useState<ModuleDetail | null>(null);
  const [initialized, setInitialized] = useState(false);

  const [panels, setPanels] = useState<Record<PanelKey, boolean>>(() => {
    if (typeof window === "undefined") return { quellen: true, chat: true, studio: true };
    try {
      const stored = localStorage.getItem(`ki-tutor-panels-${uuid}`);
      if (stored) return JSON.parse(stored);
    } catch { /* ignore */ }
    return { quellen: true, chat: true, studio: true };
  });
  const [p1Width, setP1Width] = useState(360);
  const [p2Width, setP2Width] = useState(500);
  const [p3Width, setP3Width] = useState(380);
  const [activeTab, setActiveTab] = useState<PanelKey>("chat");
  const [isMobile, setIsMobile] = useState(false);
  const panelContainerRef = useRef<HTMLDivElement>(null);
  const p1Ref = useRef<HTMLDivElement>(null);
  const p2Ref = useRef<HTMLDivElement>(null);
  const p3Ref = useRef<HTMLDivElement>(null);
  const panelsRef = useRef(panels);
  panelsRef.current = panels;

  const MIN_PANEL = 240;
  const MOBILE_BREAKPOINT = 768;

  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [prevSelectedSourceIds, setPrevSelectedSourceIds] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const [showSettings, setShowSettings] = useState(false);
  const settingsRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!showSettings) return;
    function handle(e: MouseEvent) {
      if (!settingsRef.current?.contains(e.target as Node)) setShowSettings(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [showSettings]);

  const [chatLang, setChatLang] = useState<"de" | "en">("de");
  const [sprachtrainingActive, setSprachtrainingActive] = useState(false);

  const [studioView, setStudioView] = useState<StudioView>("overview");
  const [lernkarten, setLernkarten] = useState<LernKarte[]>([]);
  const [lernkartenLoading, setLernkartenLoading] = useState(false);
  const [flippedCards, setFlippedCards] = useState<Set<number>>(new Set());
  const [quiz, setQuiz] = useState<QuizQuestion[]>([]);
  const [quizLoading, setQuizLoading] = useState(false);
  const [quizAnswers, setQuizAnswers] = useState<Record<number, number>>({});

  // ─── Init ──────────────────────────────────────────────────────────────────

  const loadMessages = useCallback(async () => {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/messages`, { credentials: "include" });
      if (res.ok) setMessages(await res.json());
    } catch { /* ignore */ }
  }, [uuid]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const authData = await checkAuthStatus();
        if (cancelled) return;
        if (!authData.authenticated) { router.push("/"); return; }
        setAuth(authData);

        const modRes = await fetch(`/api/ki-tutor/modules/${uuid}`, { credentials: "include" });
        if (cancelled) return;
        if (!modRes.ok) { router.push("/ki-tutor"); return; }
        const mod: ModuleDetail = await modRes.json();
        setModuleDetail(mod);

        const srcs: Source[] = mod.sources ?? [];
        setSources(srcs);
        setSelectedSourceIds(srcs.filter((s) => s.status === "ready").map((s) => s.uuid));

        await loadMessages();

        const settingsRes = await fetch(`/api/ki-tutor/modules/${uuid}/settings`, { credentials: "include" });
        if (!cancelled && settingsRes.ok) {
          const s = await settingsRes.json();
          setChatLang(s.chat_lang ?? "de");
          setSprachtrainingActive(s.sprachtraining_active ?? false);
        }

        if (!cancelled) setInitialized(true);
      } catch {
        if (!cancelled) router.push("/ki-tutor");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [uuid, router, loadMessages]);

  // Persist panel collapse state to localStorage
  useEffect(() => {
    try { localStorage.setItem(`ki-tutor-panels-${uuid}`, JSON.stringify(panels)); } catch { /* ignore */ }
  }, [panels, uuid]);

  // Persist settings to DB (only after init to avoid overwriting with defaults)
  useEffect(() => {
    if (!initialized) return;
    fetch(`/api/ki-tutor/modules/${uuid}/settings`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_lang: chatLang, sprachtraining_active: sprachtrainingActive }),
    }).catch(() => { /* ignore */ });
  }, [chatLang, sprachtrainingActive, initialized, uuid]);

  useEffect(() => {
    const needsPoll = sources.some((s) => s.status === "indexing" || s.status === "pending");
    if (!needsPoll) return;
    const id = setInterval(async () => {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}`, { credentials: "include" });
      if (!res.ok) return;
      const mod: ModuleDetail = await res.json();
      const srcs: Source[] = mod.sources ?? [];
      setSources(srcs);
      setModuleDetail(mod);
      setSelectedSourceIds((prev) => {
        const newReady = srcs.filter((s) => s.status === "ready" && !prev.includes(s.uuid)).map((s) => s.uuid);
        return newReady.length > 0 ? [...prev, ...newReady] : prev;
      });
    }, 3000);
    return () => clearInterval(id);
  }, [sources, uuid]);

  // ─── Mobile breakpoint detection ─────────────────────────────────────────

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    setIsMobile(mq.matches);
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [MOBILE_BREAKPOINT]);


  // ─── Panel toggle ──────────────────────────────────────────────────────────

  function togglePanel(key: PanelKey) {
    setPanels((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      if (Object.values(next).every((v) => !v)) return prev;
      return next;
    });
  }

  // ─── Drag resize ──────────────────────────────────────────────────────────

  function startDrag(divider: 1 | 2, e: React.MouseEvent) {
    e.preventDefault();
    const refA = divider === 1 ? p1Ref : p2Ref;
    const refB = divider === 1 ? p2Ref : p3Ref;
    const startX = e.clientX;
    const startA = divider === 1 ? p1Width : p2Width;
    const startB = divider === 1 ? p2Width : p3Width;

    function clampDelta(raw: number) {
      return Math.min(startB - MIN_PANEL, Math.max(-(startA - MIN_PANEL), raw));
    }

    function onMove(ev: MouseEvent) {
      if (!refA.current || !refB.current) return;
      const d = clampDelta(ev.clientX - startX);
      // Direct DOM write — no React re-render during drag
      refA.current.style.flexBasis = `${startA + d}px`;
      refB.current.style.flexBasis = `${startB - d}px`;
    }

    function onUp(ev: MouseEvent) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const d = clampDelta(ev.clientX - startX);
      if (divider === 1) {
        setP1Width(startA + d);
        setP2Width(startB - d);
      } else {
        setP2Width(startA + d);
        setP3Width(startB - d);
      }
    }

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  // ─── Source actions ────────────────────────────────────────────────────────

  function handleToggleSource(srcUuid: string) {
    setSelectedSourceIds((prev) =>
      prev.includes(srcUuid) ? prev.filter((id) => id !== srcUuid) : [...prev, srcUuid]
    );
  }

  function handleOpenViewer(source: Source, page = 1) {
    setPrevSelectedSourceIds(selectedSourceIds);
    setSelectedSourceIds([source.uuid]);
    setViewerSource({ uuid: source.uuid, filename: source.filename, page });
    setPanels((prev) => ({ ...prev, quellen: true }));
  }

  function handleCloseViewer() {
    setSelectedSourceIds(prevSelectedSourceIds);
    setViewerSource(null);
  }

  async function handleDeleteSource(srcUuid: string) {
    if (!confirm("Quelle wirklich löschen?")) return;
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/sources/${srcUuid}`, { method: "DELETE", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.filter((s) => s.uuid !== srcUuid));
        setSelectedSourceIds((prev) => prev.filter((id) => id !== srcUuid));
      }
    } catch { /* ignore */ }
  }

  async function handleUpload(file: File) {
    setUploadProgress(0);
    try {
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/ki-tutor/modules/${uuid}/sources`);
        xhr.withCredentials = true;
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            const newSrc: Source = JSON.parse(xhr.responseText);
            setSources((prev) => [...prev, newSrc]);
            resolve();
          } else reject(new Error("Upload fehlgeschlagen"));
        };
        xhr.onerror = () => reject(new Error("Netzwerkfehler"));
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      });
    } catch { /* ignore */ } finally {
      setUploadProgress(null);
    }
  }

  // ─── Chat ──────────────────────────────────────────────────────────────────

  async function sendChatMessage(content: string, directText = false) {
    const effectiveSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;
    if (!content.trim()) return;
    if (!directText && effectiveSourceIds.length === 0) return;
    setMessages((prev) => [...prev, { role: "user", content: content.trim() }]);
    setChatInput("");
    setChatLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: content.trim(),
          active_source_ids: directText ? [] : effectiveSourceIds,
          direct_text: directText,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((prev) => [...prev, { role: "assistant", content: data.answer, source_pages: data.source_pages }]);
      } else if (res.status === 409) {
        setMessages((prev) => [...prev, { role: "assistant", content: "Das Modul wird noch indiziert. Bitte warte einen Moment und versuche es erneut." }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." }]);
      }
    } catch { /* ignore */ } finally {
      setChatLoading(false);
    }
  }

  function handleAskWithSelection(prompt: string) {
    if (isMobile) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    sendChatMessage(prompt, true);
  }

  function handlePillClick(sourceUuid: string, page: number, filename: string) {
    const src = sources.find((s) => s.uuid === sourceUuid);
    if (src) handleOpenViewer(src, page);
    else {
      setPrevSelectedSourceIds(selectedSourceIds);
      setSelectedSourceIds([sourceUuid]);
      setViewerSource({ uuid: sourceUuid, filename, page });
      setPanels((prev) => ({ ...prev, quellen: true }));
    }
  }

  // ─── Studio ────────────────────────────────────────────────────────────────

  async function generateLernkarten() {
    setLernkartenLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "Erstelle 5 Lernkarten aus den aktiven Quellen im Format: Vorderseite | Rückseite (eine Karte pro Zeile, nummeriert)",
          active_source_ids: selectedSourceIds,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setLernkarten(parseLernkarten(data.answer));
        setFlippedCards(new Set());
      }
    } catch { /* ignore */ } finally {
      setLernkartenLoading(false);
    }
  }

  async function generateQuiz() {
    setQuizLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "Erstelle 5 Multiple-Choice-Fragen aus den aktiven Quellen. Format: Nummer. Frage? dann A) B) C) D) Optionen. Markiere die richtige Antwort mit ✓",
          active_source_ids: selectedSourceIds,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setQuiz(parseQuiz(data.answer));
        setQuizAnswers({});
      }
    } catch { /* ignore */ } finally {
      setQuizLoading(false);
    }
  }

  function toggleFlipCard(i: number) {
    setFlippedCards((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  const isLecturer = auth?.role === "lecturer";
  const activeSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;

  const p1Style: React.CSSProperties = panels.quellen
    ? { flex: `1 1 ${p1Width}px`, minWidth: MIN_PANEL, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p2Style: React.CSSProperties = panels.chat
    ? { flex: `1 1 ${p2Width}px`, minWidth: MIN_PANEL, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const studioActive = studioView !== "overview";
  const p3Style: React.CSSProperties = panels.studio
    ? { flex: `1 1 ${studioActive ? Math.max(p3Width, 480) : p3Width}px`, minWidth: studioActive ? 480 : MIN_PANEL, overflow: "hidden", transition: "min-width 0.3s ease" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  if (!initialized) {
    return (
      <ProtectedRoute>
        <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          <Header showLogout />
          <div className="flex-1 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2" style={{ borderColor: "#004261" }} />
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
        <Header showLogout />

        {/* Topbar — Desktop only */}
        {!isMobile && (
          <div
            className="flex items-center px-5 flex-shrink-0 relative"
            style={{ height: 48, borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
          >
            <span className="flex-1 text-sm font-semibold truncate mr-4" style={{ color: "var(--text)" }}>
              {moduleDetail?.title ?? ""}
            </span>
            <div ref={settingsRef} className="relative flex-shrink-0">
            <button
              type="button"
              onClick={() => setShowSettings((v) => !v)}
              className="w-8 h-8 flex items-center justify-center rounded-lg hover:opacity-70 transition-opacity"
              style={{ backgroundColor: showSettings ? "rgba(0,66,97,0.1)" : "transparent", color: showSettings ? "#004261" : "var(--muted)" }}
              title="Einstellungen"
            >
              <GearSix size={17} weight={showSettings ? "fill" : "regular"} />
            </button>

            {/* Settings dropdown */}
            {showSettings && (
              <div
                className="absolute right-0 top-10 z-50 rounded-xl shadow-lg"
                style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", width: 260 }}
              >
                <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                  <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>Meine Einstellungen</p>
                </div>
                {/* Chat-Sprache */}
                <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Chat-Sprache</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Sprache der KI-Antworten</p>
                  </div>
                  <div className="flex gap-1">
                    {(["de", "en"] as const).map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        onClick={() => setChatLang(lang)}
                        className="text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors"
                        style={{
                          backgroundColor: chatLang === lang ? "#004261" : "var(--border)",
                          color: chatLang === lang ? "white" : "var(--muted)",
                        }}
                      >
                        {lang.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Sprachtraining */}
                <div className="flex items-center justify-between px-4 py-3">
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Sprachtraining</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Zeigt Sprachtraining-Tab im Studio</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={sprachtrainingActive}
                    onClick={() => setSprachtrainingActive((v) => !v)}
                    className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                    style={{ backgroundColor: sprachtrainingActive ? "#004261" : "#CBD5E1" }}
                  >
                    <span
                      className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                      style={{ transform: sprachtrainingActive ? "translateX(16px)" : "translateX(0)" }}
                    />
                  </button>
                </div>
              </div>
            )}
            </div>
          </div>
        )}

        {/* Tab bar — Mobile only */}
        {isMobile && (
          <div
            className="flex flex-shrink-0"
            style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
          >
            {(["quellen", "chat", "studio"] as PanelKey[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(key)}
                className="flex-1 py-3 text-sm font-medium transition-colors relative"
                style={{ color: activeTab === key ? "#004261" : "var(--muted)", background: "none", border: "none" }}
              >
                {key === "quellen" ? "Quellen" : key === "chat" ? "Chat" : "Studio"}
                {activeTab === key && (
                  <span
                    className="absolute bottom-0 left-0 right-0"
                    style={{ height: 2, backgroundColor: "#004261", display: "block" }}
                  />
                )}
              </button>
            ))}
          </div>
        )}

        {/* Panels */}
        <div
          ref={panelContainerRef}
          className="flex flex-1 overflow-hidden"
          style={{ padding: 8, gap: 0, backgroundColor: "var(--bg)" }}
        >
          {isMobile ? (
            /* Mobile: single panel, switched via activeTab */
            <div
              className="flex flex-col flex-1 overflow-hidden rounded-2xl"
              style={{ backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
            >
              {activeTab === "quellen" ? (
                viewerSource ? (
                  <PdfViewer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onAskWithSelection={handleAskWithSelection} />
                ) : (
                  <SourcesPanel
                    sources={sources}
                    selectedSourceIds={selectedSourceIds}
                    onToggleSource={handleToggleSource}
                    onOpenViewer={(src) => handleOpenViewer(src)}
                    onDeleteSource={handleDeleteSource}
                    onUpload={handleUpload}
                    uploadProgress={uploadProgress}
                    isLecturer={isLecturer}
                    onMinimize={() => setActiveTab("chat")}
                  />
                )
              ) : activeTab === "chat" ? (
                <ChatPanel
                  messages={messages}
                  activeSourceIds={activeSourceIds}
                  sources={sources}
                  loading={chatLoading}
                  input={chatInput}
                  onInputChange={setChatInput}
                  onSend={() => sendChatMessage(chatInput)}
                  onPillClick={handlePillClick}
                  moduleReady={moduleDetail?.status === "ready"}
                  onClear={() => setMessages([])}
                />
              ) : studioView === "overview" ? (
                <StudioOverview onSelect={setStudioView} onMinimize={() => setActiveTab("chat")} sprachtrainingActive={sprachtrainingActive} />
              ) : studioView === "lernkarten" ? (
                <LernkartenStudio
                  karten={lernkarten}
                  loading={lernkartenLoading}
                  flippedCards={flippedCards}
                  onGenerate={generateLernkarten}
                  onFlip={toggleFlipCard}
                  onBack={() => setStudioView("overview")}
                />
              ) : (
                <QuizStudio
                  questions={quiz}
                  loading={quizLoading}
                  answers={quizAnswers}
                  onGenerate={generateQuiz}
                  onAnswer={(qi, ai) => setQuizAnswers((prev) => ({ ...prev, [qi]: ai }))}
                  onBack={() => setStudioView("overview")}
                />
              )}
            </div>
          ) : (
            /* Desktop: 3 panels with drag handles */
            <>
              {/* Panel 1 — Quellen */}
              <div
                ref={p1Ref}
                className="flex flex-col overflow-hidden rounded-2xl"
                style={{ ...p1Style, backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
              >
                {!panels.quellen ? (
                  <MiniStrip label="Quellen" onClick={() => togglePanel("quellen")} side="left" />
                ) : viewerSource ? (
                  <PdfViewer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onAskWithSelection={handleAskWithSelection} />
                ) : (
                  <SourcesPanel
                    sources={sources}
                    selectedSourceIds={selectedSourceIds}
                    onToggleSource={handleToggleSource}
                    onOpenViewer={(src) => handleOpenViewer(src)}
                    onDeleteSource={handleDeleteSource}
                    onUpload={handleUpload}
                    uploadProgress={uploadProgress}
                    isLecturer={isLecturer}
                    onMinimize={() => togglePanel("quellen")}
                  />
                )}
              </div>

              {/* Drag handle 1 */}
              <div
                className="group flex-shrink-0 flex items-center justify-center"
                style={{ width: 8, cursor: panels.quellen && panels.chat ? "col-resize" : "default" }}
                onMouseDown={(e) => panels.quellen && panels.chat && startDrag(1, e)}
              >
                <div
                  className="w-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ height: 48, backgroundColor: "#004261" }}
                />
              </div>

              {/* Panel 2 — Chat */}
              <div
                ref={p2Ref}
                className="flex flex-col overflow-hidden rounded-2xl"
                style={{ ...p2Style, backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
              >
                {!panels.chat ? (
                  <MiniStrip label="Chat" onClick={() => togglePanel("chat")} side="left" />
                ) : (
                  <ChatPanel
                    messages={messages}
                    activeSourceIds={activeSourceIds}
                    sources={sources}
                    loading={chatLoading}
                    input={chatInput}
                    onInputChange={setChatInput}
                    onSend={() => sendChatMessage(chatInput)}
                    onPillClick={handlePillClick}
                    moduleReady={moduleDetail?.status === "ready"}
                    onClear={() => setMessages([])}
                  />
                )}
              </div>

              {/* Drag handle 2 */}
              <div
                className="group flex-shrink-0 flex items-center justify-center"
                style={{ width: 8, cursor: panels.chat && panels.studio ? "col-resize" : "default" }}
                onMouseDown={(e) => panels.chat && panels.studio && startDrag(2, e)}
              >
                <div
                  className="w-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                  style={{ height: 48, backgroundColor: "#004261" }}
                />
              </div>

              {/* Panel 3 — Studio */}
              <div
                ref={p3Ref}
                className="flex flex-col overflow-hidden rounded-2xl"
                style={{ ...p3Style, backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
              >
                {!panels.studio ? (
                  <MiniStrip label="Studio" onClick={() => togglePanel("studio")} side="right" />
                ) : studioView === "overview" ? (
                  <StudioOverview onSelect={setStudioView} onMinimize={() => togglePanel("studio")} sprachtrainingActive={sprachtrainingActive} />
                ) : studioView === "lernkarten" ? (
                  <LernkartenStudio
                    karten={lernkarten}
                    loading={lernkartenLoading}
                    flippedCards={flippedCards}
                    onGenerate={generateLernkarten}
                    onFlip={toggleFlipCard}
                    onBack={() => setStudioView("overview")}
                  />
                ) : (
                  <QuizStudio
                    questions={quiz}
                    loading={quizLoading}
                    answers={quizAnswers}
                    onGenerate={generateQuiz}
                    onAnswer={(qi, ai) => setQuizAnswers((prev) => ({ ...prev, [qi]: ai }))}
                    onBack={() => setStudioView("overview")}
                  />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
