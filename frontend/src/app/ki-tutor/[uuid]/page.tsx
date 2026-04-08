"use client";

import "mind-elixir/style.css";
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import HelpTooltip from "@/components/HelpTooltip";
import Spinner from "@/components/Spinner";
import {
  Eye,
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
  MagnifyingGlassMinus,
  ArrowsOut,
  ArrowsIn,
  ArrowsOutLineVertical,
  ArrowsInLineVertical,
  CornersOut,
  CornersIn,
  ListBullets,
  Lightbulb,
  BookOpenText,
  ChartBar,
  Table,
  TreeStructure,
  GearSix,
  CaretDown,
  CaretUp,
  Copy,
  NotePencil,
  Trash,
  Translate,
  Book,
  TextAa,
  Exam,
  ArrowCounterClockwise,
  Target,
  TrendUp,
  WarningCircle,
  Info,
  DownloadSimple,
  Play,
  SpeakerHigh,
  VideoCamera,
  FileVideo,
  FileAudio,
  Files,
  ClockCounterClockwise,
  DotsThreeVertical,
  type IconWeight,
} from "@phosphor-icons/react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import type { AuthStatus } from "@/types";
import { PDFViewer, type PDFViewerRef } from "@embedpdf/react-pdf-viewer";
import { registerIcons } from "@embedpdf/snippet";

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

// ─── Types ────────────────────────────────────────────────────────────────────

interface ModuleDetail {
  uuid: string;
  title: string;
  description?: string | null;
  status: string;
  is_active: boolean;
  sources: Source[];
}

const _MEDIA_EXTENSIONS = new Set([".mp3", ".mp4", ".wav", ".flac", ".m4a", ".webm"]);
function _isMediaFile(filename: string): boolean {
  const ext = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return _MEDIA_EXTENSIONS.has(ext);
}

function _formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

/** Convert **bold** and *italic* markdown to HTML (XSS-safe). */
function _md(text: string): string {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
}

function _chunkLabel(filename: string, num: number, startTime?: number | null): string {
  if (_isMediaFile(filename) && startTime != null) return _formatTime(startTime);
  if (_isMediaFile(filename)) return `Teil ${num}`;
  return `S. ${num}`;
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
  source_text?: string;
  start_time?: number;
  end_time?: number;
}

interface SourceQmap {
  qnum: number;
  uuid: string;
  filename: string;
  is_media?: boolean;
}

interface ChatMessage {
  id?: string;
  role: "user" | "assistant";
  content: string;
  source_pages?: SourceRef[];
  source_qmap?: SourceQmap[];
  sourceCount?: number;
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
  highlightText?: string;
  nonce?: number;
  startTime?: number;
}

interface DatentabelleRowSource {
  source_label: string;
  page: number | string;
  highlight?: string;
}

interface DatentabelleData {
  title: string;
  columns: string[];
  rows: { cells: string[]; sources: number[] | DatentabelleRowSource[] }[];
}

interface DatentabelleSource {
  number: number;
  filename: string;
}

type StudioView = "overview" | "karteikarten" | "quiz" | "datentabelle" | "mindmap" | "notizen";
type PanelKey = "quellen" | "chat" | "studio";

interface GlossaryEntry {
  id: number;
  term_de: string;
  term_en: string;
  definition: string;
  definition_en?: string;
  example_sentence?: string;
  example_sentence_en?: string;
  page_number?: number;
  filename?: string;
}

interface ClozeExercise {
  glossary_entry_id: number;
  sentence: string;
  answer: string;
  options: string[];
  page_number?: number;
}

interface VocabTestQuestion {
  glossary_entry_id: number;
  question: string;
  options: string[];
  correct_index: number;
  explanation?: string;
}

type SprachtrainingView = "overview" | "glossar" | "karteikarten" | "lueckentext" | "vokabeltest"
  | "lk-sets" | "lk-learn" | "lk-complete"
  | "cl-sets" | "cl-learn" | "cl-complete"
  | "vt-sets" | "vt-learn" | "vt-complete"
  | "create-set";

interface ExerciseItem {
  id: number;
  set_id: number;
  position: number;
  front: string;
  back: string;
  back_en?: string;
  options?: string[];
  correct_idx?: number;
  source_label?: string;
  page_number?: number;
  start_time?: number;
  explanation?: string;
}

interface ExerciseSet {
  id: number;
  module_id: number;
  user_id: number;
  tool: string;
  title: string;
  mode: string;
  source_uuid?: string;
  card_count: number;
  status?: string;
  created_at: string;
  total_attempts?: number;
  progress_pct?: number;
  last_run_correct?: number;
  items?: ExerciseItem[];
}

interface StreakInfo {
  current_streak: number;
  max_streak: number;
  last_active_date: string | null;
}

interface ExerciseOverview {
  total_sets: number;
  total_cards: number;
  total_attempts: number;
  total_correct: number;
  accuracy: number;
}

interface HeatmapDay {
  day: string;
  answers: number;
  correct: number;
  wrong: number;
  sets_practiced: number;
}

interface StudentStats {
  streak: StreakInfo;
  overview: ExerciseOverview;
  lerntools: ExerciseOverview;
  sprachtraining: ExerciseOverview;
  heatmap: HeatmapDay[];
  lerntools_heatmap: HeatmapDay[];
  sprachtraining_heatmap: HeatmapDay[];
  chat: { total: number; today: number };
  first_activity: string | null;
  active_days: number;
  today: string;
}

const MinimizeContext = createContext<(() => void) | null>(null);

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
      <Spinner size="xs" className="" />
    );
  if (status === "ready") return null;
  return (
    <span title="Indizierung fehlgeschlagen" className="flex-shrink-0 inline-flex">
      <XIcon size={12} weight="bold" style={{ color: "#B91C1C" }} />
    </span>
  );
}

// ─── File Icon ─────────────────────────────────────────────────────────────────

function FileIcon({ filename }: { filename: string }) {
  const isPdf = filename.toLowerCase().endsWith(".pdf");
  const isMedia = _isMediaFile(filename);
  const isVideo = [".mp4", ".webm"].some(e => filename.toLowerCase().endsWith(e));
  const isAudio = isMedia && !isVideo;
  const bg = isVideo ? "#E0E7FF" : isAudio ? "#FEF3C7" : isPdf ? "#FEE2E2" : "#DBEAFE";
  const color = isVideo ? "#4338CA" : isAudio ? "#B45309" : isPdf ? "#B91C1C" : "#1D4ED8";
  const Icon = isVideo ? FileVideo : isAudio ? FileAudio : FilePdf;
  return (
    <div
      className="flex-shrink-0 w-8 h-8 rounded flex items-center justify-center"
      style={{ backgroundColor: bg }}
    >
      <Icon size={16} weight="bold" color={color} />
    </div>
  );
}

// ─── PDF Viewer ────────────────────────────────────────────────────────────────

const PDF_ICON_MAP: Record<string, React.ComponentType<{ size?: number; weight?: IconWeight }>> = {
  ArrowsCounterClockwise,
  Scissors,
  MagnifyingGlassPlus,
  BookOpenText,
  ListBullets,
  Lightbulb,
};

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


function MediaPlayer({
  source, onClose, moduleUuid, onMinimize,
}: {
  source: ViewerState;
  onClose: () => void;
  moduleUuid: string;
  onMinimize?: () => void;
}) {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const mediaUrl = `/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/file`;

  // Seek to timestamp when source changes
  useEffect(() => {
    if (source.startTime !== undefined && mediaRef.current) {
      mediaRef.current.currentTime = source.startTime;
      mediaRef.current.play().catch(() => {});
    }
  }, [source.startTime, source.nonce]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
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
      {/* Player */}
      <div className="flex-1 flex items-center justify-center p-4 overflow-hidden">
        {isVideo ? (
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={mediaUrl}
            controls
            className="w-full max-h-full rounded-lg"
            style={{ backgroundColor: "#000" }}
          />
        ) : (
          <div className="w-full max-w-md flex flex-col items-center gap-4">
            <div
              className="w-24 h-24 rounded-full flex items-center justify-center"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.1)" }}
            >
              <SpeakerHigh size={40} weight="bold" style={{ color: "var(--kb)" }} />
            </div>
            <span className="text-sm font-medium truncate max-w-full">{source.filename}</span>
            <audio
              ref={mediaRef as React.RefObject<HTMLAudioElement>}
              src={mediaUrl}
              controls
              className="w-full"
            />
          </div>
        )}
      </div>
    </div>
  );
}


function PdfViewer({
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
          `/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/summaries`,
          { credentials: "include" },
        );
        if (res.ok && !cancelled) {
          const data = await res.json();
          setSummariesStatus(data.status);
          if (data.status === "ready") {
            const pages: Record<number, string> = {};
            for (const [k, v] of Object.entries(data.pages)) pages[Number(k)] = v as string;
            setPageSummaries(pages);
            setSummariesLoaded(true);
          } else if (data.status === "generating") {
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
  const prevHighlightRef = useRef<{ pageIndex: number; id: string } | null>(null);

  function doHighlightSearch(reg: unknown, page: number, text: string) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = reg as any;
    const scroll = r.getPlugin?.("scroll")?.provides?.();
    scroll?.scrollToPage?.({ pageNumber: page, behavior: "instant" });

    const anno = r.getPlugin?.("annotation")?.provides?.();
    // Remove previous highlight annotation
    if (prevHighlightRef.current && anno) {
      try { anno.deleteAnnotation(prevHighlightRef.current.pageIndex, prevHighlightRef.current.id); } catch { /* ignore */ }
      prevHighlightRef.current = null;
    }

    if (!text?.trim() || !anno) { console.log("[HL] abort: no text or no anno plugin", { text: text?.slice(0, 30), anno: !!anno }); return; }

    const engine = r.getEngine?.();
    const docMgr = r.getPlugin?.("document-manager")?.provides?.();
    const selection = r.getPlugin?.("selection")?.provides?.();
    console.log("[HL] plugins:", { engine: !!engine, docMgr: !!docMgr, selection: !!selection });
    if (!engine || !docMgr) return;

    const doc = docMgr.getActiveDocument?.();
    console.log("[HL] doc:", { doc: !!doc, pages: doc?.pages?.length });
    if (!doc) return;

    const pageIndex = page - 1;
    const pageObj = doc.pages?.[pageIndex];
    console.log("[HL] pageObj:", { pageIndex, pageObj: !!pageObj });
    if (!pageObj) return;

    // Get geometry (from selection cache or engine)
    const cachedGeo = selection?.getState?.()?.geometry?.[pageIndex];
    const geoPromise: Promise<unknown> = cachedGeo
      ? Promise.resolve(cachedGeo)
      : (engine.getPageGeometry?.(doc, pageObj)?.toPromise?.() ?? Promise.resolve(null));

    geoPromise.then((geo: unknown) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const g = geo as any;
      console.log("[HL] geometry:", { hasRuns: !!g?.runs?.length, runCount: g?.runs?.length });
      if (!g?.runs?.length) return;

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const lastRun = g.runs[g.runs.length - 1] as any;
      const totalChars = lastRun.charStart + lastRun.glyphs.length;
      if (totalChars === 0) return;

      const sliceTask = engine.getTextSlices?.(doc, [{ pageIndex, charIndex: 0, charCount: totalChars }]);
      const slicePromise: Promise<unknown> = sliceTask?.toPromise?.() ?? Promise.resolve(null);

      return slicePromise.then((slices: unknown) => {
        const arr = slices as string[] | null;
        if (!arr?.[0]) return;
        const pageText = arr[0];

        // Normalize text: keep only letters, digits, spaces — strip everything else
        const stripToCore = (s: string): { text: string; map: number[] } => {
          const out: string[] = [];
          const map: number[] = [];
          for (let i = 0; i < s.length; i++) {
            // Dehyphenation: '-' + '\n' between letters → skip both
            if (s[i] === "-" && s[i + 1] === "\n" &&
                i > 0 && /\p{L}/u.test(s[i - 1]) && i + 2 < s.length && /\p{L}/u.test(s[i + 2])) {
              i++; continue;
            }
            const ch = s[i];
            if (ch === "\n" || ch === "\r") {
              if (out.length > 0 && out[out.length - 1] !== " ") { out.push(" "); map.push(i); }
              continue;
            }
            // Keep letters, digits, spaces only
            if (/[\p{L}\p{N} ]/u.test(ch)) {
              if (ch === " " && out.length > 0 && out[out.length - 1] === " ") continue;
              out.push(ch); map.push(i);
            }
            // Everything else (quotes, punctuation, symbols) → skip
          }
          return { text: out.join(""), map };
        };

        const { text: normalized, map: mapping } = stripToCore(pageText);
        const { text: searchText } = stripToCore(text);

        const matchPos = normalized.toLowerCase().indexOf(searchText.toLowerCase());
        if (matchPos === -1) return;

        const origStart = mapping[matchPos];
        // Find end position by searching for the last few words separately in the page text
        // This avoids character-count drift from stripped symbols
        const searchWords = searchText.split(/\s+/);
        const lastWords = searchWords.slice(-3).join(" ").toLowerCase();
        // Only search within ~110% of expected range to avoid matching elsewhere
        const maxEnd = Math.min(matchPos + Math.ceil(searchText.length * 1.1), normalized.length);
        const searchSlice = normalized.toLowerCase().slice(matchPos, maxEnd);
        const tailInSlice = searchSlice.lastIndexOf(lastWords);
        const tailPos = tailInSlice >= 0 ? matchPos + tailInSlice : -1;
        let origEnd: number;
        if (tailPos >= 0) {
          origEnd = mapping[Math.min(tailPos + lastWords.length - 1, mapping.length - 1)];
        } else {
          origEnd = mapping[Math.min(matchPos + searchText.length - 1, mapping.length - 1)];
        }
        // Extend to include trailing punctuation
        while (origEnd + 1 < pageText.length && /[.,;:!?)}\]\-]/.test(pageText[origEnd + 1])) origEnd++;

        // Use RUN rects directly — find all runs that overlap with [origStart, origEnd]
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const runs = g.runs as any[];
        const segmentRects: { origin: { x: number; y: number }; size: { width: number; height: number } }[] = [];

        for (const run of runs) {
          const runEnd = run.charStart + run.glyphs.length - 1;
          // Check if this run overlaps with our character range
          if (runEnd < origStart || run.charStart > origEnd) continue;
          // Use the run's bounding rect directly
          const r = run.rect;
          if (r && r.width > 0 && r.height > 0) {
            // If run partially overlaps, clip to the overlapping glyphs
            const clipStart = Math.max(0, origStart - run.charStart);
            const clipEnd = Math.min(run.glyphs.length - 1, origEnd - run.charStart);
            const firstGlyph = run.glyphs[clipStart];
            const lastGlyph = run.glyphs[clipEnd];
            const x1 = firstGlyph.x;
            const x2 = lastGlyph.x + lastGlyph.width;
            segmentRects.push({
              origin: { x: x1, y: r.y },
              size: { width: x2 - x1, height: r.height },
            });
          }
        }

        // Merge segments on the same visual line
        const merged: typeof segmentRects = [];
        for (const sr of segmentRects) {
          const prev = merged[merged.length - 1];
          if (prev && Math.abs(sr.origin.y - prev.origin.y) < prev.size.height * 0.6) {
            const minX = Math.min(prev.origin.x, sr.origin.x);
            const maxX = Math.max(prev.origin.x + prev.size.width, sr.origin.x + sr.size.width);
            const minY = Math.min(prev.origin.y, sr.origin.y);
            const maxY = Math.max(prev.origin.y + prev.size.height, sr.origin.y + sr.size.height);
            merged[merged.length - 1] = { origin: { x: minX, y: minY }, size: { width: maxX - minX, height: maxY - minY } };
          } else {
            merged.push({ ...sr });
          }
        }
        const finalSegments = merged.length > 0 ? merged : segmentRects;
        console.log("[HL] segments:", finalSegments.length);
        if (finalSegments.length === 0) return;

        const bMinX = Math.min(...finalSegments.map(sr => sr.origin.x));
        const bMinY = Math.min(...finalSegments.map(sr => sr.origin.y));
        const bMaxX = Math.max(...finalSegments.map(sr => sr.origin.x + sr.size.width));
        const bMaxY = Math.max(...finalSegments.map(sr => sr.origin.y + sr.size.height));

        const boundingRect = { origin: { x: bMinX - 2, y: bMinY - 2 }, size: { width: bMaxX - bMinX + 4, height: bMaxY - bMinY + 4 } };
        const highlightId = `kis-hl-${Date.now()}`;
        // Use timeout to ensure page is fully rendered before adding annotation
        setTimeout(() => {
          anno.createAnnotation(pageIndex, {
            id: highlightId,
            type: 9, // HIGHLIGHT
            pageIndex,
            rect: boundingRect,
            segmentRects: finalSegments,
            opacity: 0.35,
            strokeColor: "#FFFF00",
          });
          prevHighlightRef.current = { pageIndex, id: highlightId };
          console.log("[HL] created annotation", highlightId, "segments:", segmentRects.length);
        }, 300);
        console.log("[HL] created annotation", highlightId);
      });
    }).catch((err) => { console.error("[HL] error:", err); });
  }

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
      scroll?.scrollToPage?.({ pageNumber: source.page, behavior: "instant" });
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
    <div className="flex flex-col h-full relative" ref={containerRef}>
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
            src: `/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/file`,
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
              <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>Wird generiert…</span>
            ) : pageSummaries[page] ? (
              <div dangerouslySetInnerHTML={{ __html: pageSummaries[page].replace(/\n/g, "<br/>") }} />
            ) : summariesStatus === "failed" ? (
              <div style={{ textAlign: "center", padding: "16px 12px" }}>
                <span style={{ color: "#6b7280", display: "block", marginBottom: 10, fontSize: 12 }}>Generierung fehlgeschlagen.</span>
                <button
                  onClick={async () => {
                    setSummariesStatus("generating");
                    setSummariesLoaded(false);
                    try {
                      await fetch(`/api/ki-tutor/modules/${moduleUuid}/sources/${source.uuid}/summaries/generate`, { method: "POST", credentials: "include" });
                    } catch { /* ignore */ }
                  }}
                  style={{ padding: "6px 16px", fontSize: 12, borderRadius: 6, border: "1px solid var(--color-fg-accent, #60a5fa)", background: "var(--color-bg-accent, #1e3a5f)", color: "#fff", cursor: "pointer", fontWeight: 500 }}
                >
                  Erneut versuchen
                </button>
              </div>
            ) : (
              <span style={{ color: "var(--color-fg-muted, #9ca3af)" }}>Keine Zusammenfassung für diese Seite.</span>
            )}
          </div>
        </div>,
        sidebarTarget,
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
  const panelRef = useRef<HTMLDivElement>(null);
  const [deleteSourceId, setDeleteSourceId] = useState<string | null>(null);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const el = panelRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 220);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

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
    <div ref={panelRef} className="flex flex-col h-full">
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
          className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
          title="Panel minimieren"
        >
          <SidebarSimple size={13} />
        </button>
      </div>

      {/* Upload button + drag-and-drop (lecturer) */}
      {isLecturer && (
        <div
          className="px-4 py-3 flex-shrink-0 transition-colors duration-150"
          style={{ borderBottom: "1px solid var(--border)" }}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onDragEnter={(e) => { e.preventDefault(); e.stopPropagation(); e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.06)"; }}
          onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); if (!e.currentTarget.contains(e.relatedTarget as Node)) e.currentTarget.style.backgroundColor = ""; }}
          onDrop={(e) => {
            e.preventDefault(); e.stopPropagation(); e.currentTarget.style.backgroundColor = "";
            const f = e.dataTransfer.files?.[0];
            if (f) onUpload(f);
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.docx,.pptx,.md,.mp3,.mp4,.wav,.flac,.m4a,.webm"
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
            style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", border: "1.5px dashed rgba(var(--kb-rgb),0.3)" }}
          >
            <Plus size={15} weight="bold" />
            Quelle hinzufügen
          </button>
          {uploadProgress !== null && (
            <div className="mt-2">
              <div className="h-1 rounded-full overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
                <div
                  className="h-full rounded-full transition-all duration-200"
                  style={{ width: `${uploadProgress}%`, backgroundColor: "var(--kb)" }}
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
            className="w-3.5 h-3.5 flex-shrink-0 accent-primary"
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
              Lade eine Quelle hoch.
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
                className="flex-shrink-0 w-3.5 h-3.5 accent-primary"
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

              <div className="flex items-center gap-2 flex-shrink-0">
                <SourceStatus status={src.status} />
                {!compact && (
                  <>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); onOpenViewer(src); }}
                      className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
                      style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
                      title="Im Viewer öffnen"
                    >
                      <Eye size={13} />
                    </button>
                    {isLecturer && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); setDeleteSourceId(src.uuid); }}
                        className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
                        style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
                        title="Quelle löschen"
                      >
                        <Trash size={13} weight="regular" />
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Delete confirmation modal */}
      {deleteSourceId && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold text-gray-900 mb-2">Quelle löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">{sources.find((s) => s.uuid === deleteSourceId)?.filename || "Quelle"}</span>
            </p>
            <p className="text-sm text-red-600 mb-6">
              Die Quelle wird vollständig entfernt und kann nicht wiederhergestellt werden.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setDeleteSourceId(null)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Abbrechen
              </button>
              <button
                onClick={() => { onDeleteSource(deleteSourceId); setDeleteSourceId(null); }}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg"
              >
                Löschen
              </button>
            </div>
          </div>
        </div>
      )}
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
  externalTextareaRef,
  onSaveNote,
  onMinimize,
  onSendPrompt,
}: {
  messages: ChatMessage[];
  activeSourceIds: string[];
  sources: Source[];
  loading: boolean;
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onPillClick: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  moduleReady: boolean;
  onClear: () => void;
  externalTextareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  onSaveNote?: (content: string) => void;
  onMinimize?: () => void;
  onSendPrompt?: (text: string) => void;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);
  const userScrolledUp = useRef(false);
  const [chatMenuOpen, setChatMenuOpen] = useState(false);
  const [expandedMsgs, setExpandedMsgs] = useState<Set<number>>(new Set());
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [savedNoteIdx, setSavedNoteIdx] = useState<number | null>(null);
  const chatMenuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  // Sync internal textarea ref → external ref so parent can focus it
  const textareaCallbackRef = useCallback((el: HTMLTextAreaElement | null) => {
    (textareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
    if (externalTextareaRef) (externalTextareaRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = el;
  }, [externalTextareaRef]);
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [input]);
  useEffect(() => {
    if (!chatMenuOpen) return;
    function handle(e: MouseEvent) {
      if (!chatMenuRef.current?.contains(e.target as Node)) setChatMenuOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [chatMenuOpen]);

  // Detect user scrolling up to opt out of auto-scroll
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      userScrolledUp.current = !nearBottom;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Re-engage auto-scroll when a new user message is sent
  useEffect(() => {
    if (loading) userScrolledUp.current = false;
  }, [loading]);

  useEffect(() => {
    if (isFirstRender.current) {
      bottomRef.current?.scrollIntoView({ behavior: "instant" });
      isFirstRender.current = false;
      return;
    }
    if (userScrolledUp.current) return;
    bottomRef.current?.scrollIntoView({ behavior: loading ? "instant" : "smooth" });
  }, [messages, loading]);

  const getFilename = (srcUuid: string) =>
    sources.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0 relative" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Chat</span>
        <div className="flex items-center gap-1.5">
        <div className="relative" ref={chatMenuRef}>
          <button
            type="button"
            onClick={() => setChatMenuOpen((v) => !v)}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Optionen"
          >
            <DotsThreeVertical size={16} weight="bold" />
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
                style={{ color: "#B91C1C" }}
              >
                Chatprotokoll löschen
              </button>
            </div>
          )}
        </div>
        {onMinimize && (
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Panel minimieren"
          >
            <SidebarSimple size={13} />
          </button>
        )}
        </div>
      </div>

      {/* Messages */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
      <div className="mx-auto w-full px-6 py-6 flex flex-col gap-5" style={{ maxWidth: 720 }}>
        {messages.length === 0 && !loading && (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 py-16">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)" }}
            >
              <Chat size={22} style={{ color: "var(--kb)" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
              Dein KI-Tutor
            </p>
            <p className="text-xs text-center max-w-xs" style={{ color: "var(--muted)" }}>
              Wähle Quellen links aus – stell Fragen, lass dir Inhalte erklären oder gib Anweisungen.
            </p>
            <div className="flex flex-col gap-2 mt-2 w-full max-w-sm">
              {[
                "Fasse die wichtigsten Punkte zusammen.",
                "Erkläre mir das Thema in einfachen Worten.",
                "Welche Prüfungsfragen könnten dazu gestellt werden?",
              ].map((prompt) => (
                <button
                  key={prompt}
                  disabled={activeSourceIds.length === 0}
                  onClick={() => onSendPrompt?.(prompt)}
                  className="text-left text-xs px-4 py-2.5 rounded-xl border transition-all"
                  style={{
                    borderColor: activeSourceIds.length === 0 ? "var(--border)" : "rgba(var(--kb-rgb),0.25)",
                    color: activeSourceIds.length === 0 ? "var(--muted)" : "var(--text)",
                    backgroundColor: activeSourceIds.length === 0 ? "transparent" : "rgba(var(--kb-rgb),0.04)",
                    cursor: activeSourceIds.length === 0 ? "default" : "pointer",
                    opacity: activeSourceIds.length === 0 ? 0.5 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (activeSourceIds.length > 0) {
                      e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.10)";
                      e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.4)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (activeSourceIds.length > 0) {
                      e.currentTarget.style.backgroundColor = "rgba(var(--kb-rgb),0.04)";
                      e.currentTarget.style.borderColor = "rgba(var(--kb-rgb),0.25)";
                    }
                  }}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => {
          const msgSourcePages = msg.source_pages ?? [];

          // Parse [QN, S. X] and legacy [S. X] tags → inline pill buttons
          const msgQmap = msg.source_qmap ?? [];
          function parseCitations(text: string): React.ReactNode[] {
            // Matches [Q1, S. 2], [S. 2], [Q1, 05:32], [Q1, 1:05:32]
            const pattern = /\[(?:Q(\d+),\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))\]/g;
            const nodes: React.ReactNode[] = [];
            let last = 0;
            let m: RegExpExecArray | null;
            while ((m = pattern.exec(text)) !== null) {
              if (m.index > last) nodes.push(text.slice(last, m.index));
              const qNum = m[1] ? parseInt(m[1]) : null;
              const pageNum = m[2] ? parseInt(m[2]) : 0;
              const timestamp = m[3] || null;

              // Resolve source via qmap (preferred) or fallback to source_pages
              const qEntry = qNum ? msgQmap.find(q => q.qnum === qNum) : null;
              const isMedia = qEntry?.is_media || !!timestamp;
              const sourceUuid = qEntry?.uuid ?? msgSourcePages.find(s => s.page_number === pageNum)?.source_uuid ?? msgSourcePages[0]?.source_uuid ?? activeSourceIds[0] ?? "";
              const filename = qEntry?.filename ?? getFilename(sourceUuid);
              const sp = msgSourcePages.find(s => s.source_uuid === sourceUuid && (timestamp ? s.start_time !== undefined : s.page_number === pageNum));

              if (isMedia && timestamp) {
                // Parse timestamp to seconds
                const parts = timestamp.split(":").map(Number);
                const seconds = parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
                nodes.push(
                  <button
                    key={m.index}
                    type="button"
                    onClick={() => onPillClick(sourceUuid, 0, filename, undefined, seconds)}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5"
                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                    title={`${filename}, ${timestamp}`}
                  >
                    <Play size={8} weight="bold" />
                    {timestamp}
                  </button>
                );
              } else {
                nodes.push(
                  <button
                    key={m.index}
                    type="button"
                    onClick={() => onPillClick(sourceUuid, pageNum, filename, sp?.source_text)}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5"
                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
                    title={`${filename}, ${_chunkLabel(filename, pageNum)}`}
                  >
                    <FilePdf size={8} weight="bold" />
                    {_chunkLabel(filename, pageNum)}
                  </button>
                );
              }
              last = pattern.lastIndex;
            }
            if (last < text.length) nodes.push(text.slice(last));
            return nodes;
          }

          function withCitations(children: React.ReactNode): React.ReactNode {
            return React.Children.map(children, (child) =>
              typeof child === "string" ? parseCitations(child) : child
            );
          }

          return (
          <div
            key={msg.id ?? i}
            className={`flex flex-col gap-1.5 group ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="flex items-center gap-2 mb-0.5">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: "var(--kb)" }}
                >
                  KI
                </div>
                <span className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>
                  KI Tutor
                </span>
              </div>
            )}
            <div
              className="max-w-[96%] px-4 py-3 rounded-2xl text-sm leading-relaxed break-words"
              style={
                msg.role === "user"
                  ? { backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap", overflowWrap: "break-word" }
                  : { backgroundColor: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderTopLeftRadius: 6, overflowWrap: "break-word" }
              }
            >
              {msg.role === "assistant" && !msg.content ? (
                <span className="inline-flex items-center gap-2">
                  <span className="inline-flex gap-1">
                    {[0, 1, 2].map((n) => (
                      <span
                        key={n}
                        className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                        style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                      />
                    ))}
                  </span>
                </span>
              ) : msg.role === "assistant" ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    p: ({ children }) => <p className="mb-2 last:mb-0">{withCitations(children)}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="leading-relaxed">{withCitations(children)}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    h1: ({ children }) => <p className="font-semibold mb-1">{withCitations(children)}</p>,
                    h2: ({ children }) => <p className="font-semibold mb-1">{withCitations(children)}</p>,
                    h3: ({ children }) => <p className="font-medium mb-1">{withCitations(children)}</p>,
                    table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                    thead: ({ children }) => <thead className="border-b border-current/20">{children}</thead>,
                    th: ({ children }) => <th className="text-left px-2 py-1 font-semibold">{children}</th>,
                    td: ({ children }) => <td className="px-2 py-1 border-t border-current/10">{withCitations(children)}</td>,
                  }}
                >
                  {(() => {
                    const seen = new Set<string>();
                    return msg.content.replace(/\s*\[(?:Q(\d+),\s*)?S\.\s*(\d+)\]/g, (m, q, p) => {
                      const k = `${q ?? ""}:${p}`;
                      if (seen.has(k)) return "";
                      seen.add(k);
                      return m;
                    });
                  })()}
                </ReactMarkdown>
              ) : (
                <>
                  <div
                    style={{
                      maxHeight: expandedMsgs.has(i) ? "none" : "8em",
                      overflow: "hidden",
                    }}
                  >
                    {msg.content}
                  </div>
                  {msg.content.split("\n").length > 5 || msg.content.length > 300 ? (
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedMsgs((prev) => {
                          const next = new Set(prev);
                          next.has(i) ? next.delete(i) : next.add(i);
                          return next;
                        })
                      }
                      className="flex items-center gap-1 mt-1.5 text-[11px] opacity-70 hover:opacity-100 transition-opacity"
                      style={{ color: "white" }}
                    >
                      {expandedMsgs.has(i) ? (
                        <>
                          <CaretUp size={12} /> Einklappen
                        </>
                      ) : (
                        <>
                          <CaretDown size={12} /> Mehr anzeigen
                        </>
                      )}
                    </button>
                  ) : null}
                </>
              )}
            </div>
            <div className={`flex items-center gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
              {msg.sourceCount != null && msg.sourceCount > 0 && (
                <span className="text-[10px]" style={{ color: "var(--muted)" }}>
                  {msg.sourceCount} {msg.sourceCount === 1 ? "Quelle" : "Quellen"}
                </span>
              )}
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(msg.content.replace(/\[S\.\s*\d+\]/g, "").trim());
                  setCopiedIdx(i);
                  setTimeout(() => setCopiedIdx(null), 1500);
                }}
                className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                style={{ color: "var(--muted)" }}
                title="Kopieren"
              >
                {copiedIdx === i ? <Check size={13} weight="bold" /> : <Copy size={13} />}
              </button>
              {msg.role === "assistant" && onSaveNote && !loading && (
                <button
                  type="button"
                  onClick={() => {
                    onSaveNote(msg.content);
                    setSavedNoteIdx(i);
                    setTimeout(() => setSavedNoteIdx(null), 1500);
                  }}
                  className="sm:opacity-0 sm:group-hover:opacity-100 transition-opacity p-1 rounded-full hover:bg-black/5"
                  style={{ color: savedNoteIdx === i ? "#16a34a" : "var(--muted)" }}
                  title="Als Notiz speichern"
                >
                  {savedNoteIdx === i ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
                </button>
              )}
            </div>
          </div>
          );
        })}

        {/* Loading indicator removed – streaming messages show inline dots */}
        <div ref={bottomRef} />
      </div>
      </div>

      {/* Input area */}
      <div
        className="flex-shrink-0 px-6 pt-4 pb-0"
        style={{ borderTop: "1px solid var(--border)" }}
      >
      <div className="mx-auto w-full" style={{ maxWidth: 720 }}>
        <div
          className="flex items-center gap-2 rounded-2xl px-4 py-3"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
        >
          <textarea
            ref={textareaCallbackRef}
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); }
            }}
            placeholder="Text eingeben…"
            rows={1}
            disabled={loading}
            className="flex-1 text-sm resize-none focus:outline-none disabled:opacity-50 bg-transparent"
            style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
          />
          <button
            type="button"
            onClick={onSend}
            disabled={loading || !input.trim() || activeSourceIds.length === 0}
            className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-opacity hover:opacity-85"
            style={{ backgroundColor: "var(--kb)" }}
            title="Senden"
          >
            <PaperPlaneRight size={16} weight="bold" />
          </button>
        </div>
        <div className="flex items-center justify-between mt-2 px-1">
          <span className="text-[11px]" style={{ color: "var(--muted)" }}>
            {activeSourceIds.length} {activeSourceIds.length === 1 ? "Quelle" : "Quellen"} aktiv
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
    <div style={{ perspective: 1200, cursor: "pointer", userSelect: "none" }} onClick={onFlip}>
      <div
        style={{
          position: "relative", width: "100%", height: 260,
          transformStyle: "preserve-3d",
          transition: "transform 0.5s cubic-bezier(0.4,0,0.2,1)",
          transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        {/* Front */}
        <div
          style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            borderRadius: 20, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: "32px 28px", gap: 12,
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "0 4px 20px rgba(0,0,0,0.07)",
          }}
        >
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "var(--muted)" }}>
            Begriff
          </span>
          <p className="text-base text-center leading-relaxed font-medium" style={{ color: "var(--text)" }}>{front}</p>
          <span className="text-[10px] mt-4" style={{ color: "var(--muted)" }}>Tippen zum Umdrehen</span>
        </div>
        {/* Back */}
        <div
          style={{
            position: "absolute", inset: 0, backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
            borderRadius: 20, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            padding: "32px 28px", gap: 12,
            backgroundColor: "var(--kb)",
            boxShadow: "0 4px 20px rgba(var(--kb-rgb),0.18)",
          }}
        >
          <span className="text-[10px] font-semibold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.5)" }}>
            Erklärung
          </span>
          <p className="text-base text-center leading-relaxed font-medium" style={{ color: "white" }}>{back}</p>
        </div>
      </div>
    </div>
  );
}

// ─── Studio Subviews ──────────────────────────────────────────────────────────

// Lerntools: var(--kb) blue tones
const LERNTOOLS_BADGE: Record<string, { bg: string; color: string }> = {
  Karteikarten:   { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  Quiz:           { bg: "rgba(254,249,195,0.7)", color: "#A16207" },
  Datentabelle:   { bg: "rgba(255,237,213,0.7)", color: "#C2410C" },
  Mindmap:        { bg: "rgba(236,254,255,0.7)", color: "#0E7490" },
  Infografik:     { bg: "rgba(237,233,254,0.7)", color: "#534AB7" },
  "Präsentation": { bg: "rgba(255,228,230,0.7)", color: "#BE123C" },
};
// Sprachtraining: distinct tool colors (each unique)
const SPRACHTRAINING_BADGE: Record<string, { bg: string; color: string }> = {
  Karteikarten:   { bg: "rgba(207,250,254,0.7)", color: "#0E7490" },
  Lernkarten:     { bg: "rgba(245,235,220,0.7)", color: "#78350F" },
  Glossar:        { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  "Lückentext":   { bg: "rgba(255,228,230,0.7)", color: "#BE123C" },
  "Begriffe-Quiz": { bg: "rgba(237,233,254,0.7)", color: "#534AB7" },
};
const SHARED_BADGE: Record<string, { bg: string; color: string }> = {
  Notizen:        { bg: "rgba(241,245,249,0.7)", color: "#475569" },
  Statistik:      { bg: "rgba(241,245,249,0.7)", color: "#475569" },
};

function SubviewHeader({ title, onBack, breadcrumbs, rightContent, category }: { title: string; onBack: () => void; breadcrumbs?: { label: string; onClick: () => void }[]; rightContent?: React.ReactNode; category?: "lerntools" | "sprachtraining" }) {
  const minimize = useContext(MinimizeContext);
  const badge = (category === "sprachtraining" ? SPRACHTRAINING_BADGE[title] : LERNTOOLS_BADGE[title]) ?? SHARED_BADGE[title];
  const mutedColor = "var(--muted)";
  const btnBg = "var(--surface-dim)";
  return (
    <div
      className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
      style={{ borderBottom: "1px solid var(--border)" }}
    >
      <button
        type="button"
        onClick={onBack}
        className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
        style={{ backgroundColor: btnBg, color: mutedColor }}
      >
        <CaretLeft size={13} />
      </button>
      {breadcrumbs && breadcrumbs.length > 0 ? (
        <div className="flex items-center gap-1 text-sm min-w-0 flex-1">
          {breadcrumbs.map((b, i) => (
            <React.Fragment key={i}>
              <button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: category === "sprachtraining" && b.label === "Fachsprachentraining" ? "#B07CE8" : mutedColor }}>{b.label}</button>
              <CaretRight size={10} weight="bold" style={{ color: category === "sprachtraining" && b.label === "Fachsprachentraining" ? "#B07CE8" : mutedColor, opacity: 0.5 }} className="shrink-0" />
            </React.Fragment>
          ))}
          {badge ? (
            <span className="font-semibold truncate px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span>
          ) : (
            <span className="font-semibold truncate" style={{ color: "var(--text)" }}>{title}</span>
          )}
        </div>
      ) : (
        badge ? (
          <span className="text-sm font-semibold flex-1 inline-flex"><span className="px-1.5 py-0.5 rounded" style={{ backgroundColor: badge.bg, color: badge.color }}>{title}</span></span>
        ) : (
          <span className="text-sm font-semibold flex-1" style={{ color: "var(--text)" }}>{title}</span>
        )
      )}
      {rightContent}
      {minimize && (
        <button type="button" onClick={minimize}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity ml-auto"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
          title="Panel minimieren">
          <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
        </button>
      )}
    </div>
  );
}

// ─── Exercise Sets Overview (shared for all 3 tools) ────────────────────────

function ExerciseSetsOverview({
  title, sets, onBack, onSelect, onCreate, onDelete, sourceCount, stats, breadcrumbs, category,
}: {
  title: string; sets: ExerciseSet[];
  onBack: () => void; onSelect: (s: ExerciseSet) => void;
  onCreate: () => void; onDelete: (id: number) => void;
  sourceCount: number; stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
  category?: "lerntools" | "sprachtraining";
}) {

  const noSources = sourceCount === 0;
  const atLimit = sets.length >= 20;
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} onBack={onBack} breadcrumbs={breadcrumbs} category={category} />
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
                : `${sourceCount} Quellen vorhanden — es werden maximal 5 berücksichtigt`}
        </div>

        {sets.length === 0 ? (
          <div className="flex flex-col items-center gap-3 pt-[15%]">
            <Cards size={48} weight="duotone" style={{ color: "var(--border)" }} />
            <p className="text-sm text-center" style={{ color: "var(--muted)" }}>Wähle Quellen aus und drücke auf Erstellen.</p>
            <button type="button" onClick={onCreate}
              disabled={noSources || atLimit}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all hover:opacity-80 disabled:opacity-40"
              style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
              <Plus size={14} weight="bold" /> Erstellen ({sets.length}/20)
            </button>
          </div>
        ) : (
          <>
            <div className="flex justify-center">
              <button type="button" onClick={onCreate}
                disabled={noSources || atLimit}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                <Plus size={14} weight="bold" /> Erstellen ({sets.length}/20)
              </button>
            </div>
            <div className="flex items-center justify-between px-1">
              <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{sets.length} Übungen</span>
              <span className="text-xs" style={{ color: "var(--muted)" }}>{sets.reduce((s, e) => s + e.card_count, 0)} Karten</span>
            </div>
            <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
              {sets.map((s) => {
                const generating = s.status === "generating";
                const failed = s.status === "failed";
                const lastCorrect = s.last_run_correct ?? 0;
                const hasRun = (s.total_attempts ?? 0) > 0;
                return (
                  <div key={s.id} onClick={() => !generating && !failed && onSelect(s)}
                    className={`bg-white rounded-xl p-3.5 flex flex-col gap-2 relative overflow-hidden group ${generating ? "opacity-70" : "cursor-pointer"}`}
                    style={{ boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)", minHeight: 90 }}>
                    {/* Title + Score */}
                    <div className="flex items-start gap-2.5 flex-1 min-w-0">
                      <span className="text-sm font-semibold leading-snug flex-1 line-clamp-3 mt-0.5 kis-tooltip" style={{ color: "var(--text)" }}
                        data-tip={generating ? undefined : (s.title === "Wird generiert…" ? undefined : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, ""))}>
                        {generating ? "Wird generiert…" : (s.title === "Wird generiert…" ? (TOOL_LABELS[s.tool] || s.tool) : s.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, ""))}
                      </span>
                      {generating ? (
                        <Spinner size="sm" />
                      ) : failed ? (
                        <span className="shrink-0 text-xs font-bold" style={{ color: "#EF4444" }}>!</span>
                      ) : (() => {
                          const pct = hasRun ? Math.round((lastCorrect / s.card_count) * 100) : 0;
                          const r = 14; const c = 2 * Math.PI * r; const offset = c - (pct / 100) * c;
                          return (
                            <svg width="38" height="38" viewBox="0 0 38 38" className="shrink-0">
                              <circle cx="19" cy="19" r={r} fill="none" stroke="var(--border)" strokeWidth="3" />
                              <circle cx="19" cy="19" r={r} fill="none" stroke="var(--kb)" strokeWidth="3"
                                strokeDasharray={c} strokeDashoffset={offset} strokeLinecap="round"
                                transform="rotate(-90 19 19)" />
                              <text x="19" y="19" textAnchor="middle" dominantBaseline="central"
                                fontSize="9" fontWeight="700" fill="var(--kb)">{pct}%</text>
                            </svg>
                          );
                        })()}
                    </div>
                    {/* Bottom row: meta left, delete right */}
                    <div className="flex items-center justify-between mt-auto pt-1">
                      <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>
                        {generating ? (s.mode === "glossar" ? "Glossar" : s.mode === "quiz" ? "Quiz" : s.mode === "lueckentext" ? "Lückentext" : s.mode === "vokabeltest" ? "Vokabeltest" : "Lernkarten") : failed ? "Fehlgeschlagen" : `${s.card_count} Karten`}
                        {!generating && s.mode === "glossar" && " · Glossar"}
                        {!generating && ` · ${new Date(s.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", timeZone: "Europe/Berlin" })}`}
                      </span>
                      <div className="flex items-center gap-1">
                        {!generating && <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                          className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                          <Trash size={12} />
                        </button>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Lernkarten Learn View ──────────────────────────────────────────────────

function LernkartenLearnView({
  exerciseSet, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs, showTranslation,
}: {
  exerciseSet: ExerciseSet;
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun?: boolean) => void;
  onAskChat?: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
  showTranslation?: boolean;
}) {
  const minimize = useContext(MinimizeContext);
  const [shuffledItems, setShuffledItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      const arr = [...raw];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; }
      setShuffledItems(arr);
      shuffledRef.current = true;
    }
  }, [exerciseSet.items]);
  const items = shuffledItems;
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [results, setResults] = useState<{ item_id: number; correct: boolean }[]>([]);
  const [streak, setStreak] = useState(0);
  const [animating, setAnimating] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const total = items.length;
  const card = items[index];
  const isVocab = exerciseSet.tool === "lernkarten";

  useEffect(() => { setFlipped(false); }, [index]);

  function answer(correct: boolean) {
    if (!card || animating) return;
    const isFirst = results.length === 0;
    setResults(prev => [...prev, { item_id: card.id, correct }]);
    if (correct) setStreak((s) => s + 1);
    else setStreak(0);
    onAnswer(card.id, correct, isFirst);

    if (index >= total - 1) {
      setShowResults(true);
      return;
    }
    setAnimating(true);
    setTimeout(() => {
      setIndex((i) => i + 1);
      setFlipped(false);
      setAnimating(false);
    }, 280);
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner />
      <p className="text-xs" style={{ color: "var(--muted)" }}>Wird geladen…</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (<div className="flex items-center gap-1 text-[12px] min-w-0 flex-1">{breadcrumbs.map((b, i) => (<React.Fragment key={i}><button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: "var(--muted)" }}>{b.label}</button><CaretRight size={9} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" /></React.Fragment>))}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span></div>) : (<span className="text-[12px] font-semibold flex-1 truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span>)}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Panel minimieren">
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>
      {/* Progress bar as top border */}
      <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
        <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
      </div>
      {/* Results */}
      {showResults ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
            style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
            <Check size={30} weight="bold" color="white" />
          </div>
          <h3 className="text-lg font-semibold" style={{ color: "var(--text)" }}>Geschafft!</h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "#1a8a5c" }}>{results.filter(r => r.correct).length} / {total}</strong> gewusst — <strong style={{ color: "#1a8a5c" }}>{Math.round((results.filter(r => r.correct).length / total) * 100)}%</strong>
          </p>
          <div className="flex gap-3 mt-4">
            <button type="button" onClick={() => { setShowResults(false); setIndex(0); setFlipped(false); setResults([]); shuffledRef.current = false; }}
              className="px-5 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
              style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}>
              Erneut versuchen
            </button>
            <button type="button" onClick={onBack}
              className="px-5 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
              style={{ backgroundColor: "var(--accent)" }}>
              Fertig
            </button>
          </div>
        </div>
      ) : card ? (
      <>
      {/* Card */}
      <div className="flex-1 flex flex-col items-center px-3 sm:px-4 pt-4 pb-3 gap-4">
        <div className="w-full mt-6" style={{ perspective: 1200, maxWidth: 560, cursor: "pointer", userSelect: "none" }} onClick={() => setFlipped((f) => !f)}>
          <div style={{
            position: "relative", width: "100%", minHeight: 300, transformStyle: "preserve-3d",
            transition: "transform 0.5s cubic-bezier(0.4,0,0.2,1)",
            transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
          }}>
            {/* Front */}
            <div style={{
              position: "absolute", inset: 0, backfaceVisibility: "hidden", borderRadius: 16,
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              padding: "36px 20px", gap: 8, backgroundColor: "var(--surface)",
              border: "2px solid var(--kb)",
              boxShadow: "0 4px 20px rgba(0,0,0,0.07)",
            }}>
              <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: "var(--muted)" }}>{isVocab ? "Fachbegriff" : "Frage"}</span>
              <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "var(--text)" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
              <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
                <span />
                {onAskChat && (
                  <button type="button" onClick={(e) => { e.stopPropagation(); onAskChat(`Gib mir einen kurzen Tipp zur folgenden Frage, OHNE die Antwort zu verraten.: „${card.front}"`); }}
                    className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-opacity hover:opacity-80"
                    style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                    <Lightbulb size={13} weight="bold" /> Tipp
                  </button>
                )}
              </div>
            </div>
            {/* Back */}
            <div style={{
              position: "absolute", inset: 0, backfaceVisibility: "hidden", transform: "rotateY(180deg)",
              borderRadius: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
              padding: "36px 20px 56px", gap: 8,
              backgroundColor: "var(--kb)",
              boxShadow: "0 4px 20px rgba(var(--kb-rgb),0.2)",
            }}>
              <span className="text-[9px] font-bold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.35)" }}>{isVocab ? "Definition" : "Antwort"}</span>
              <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "white" }} dangerouslySetInnerHTML={{ __html: _md(card.back) }} />
              {showTranslation && isVocab && card.back_en && (
                <p className="text-xs text-center italic" style={{ color: "rgba(255,255,255,0.6)" }}>{card.back_en}</p>
              )}
              {/* Source chip + Chat button */}
              <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
                {card.source_label && (
                  <button type="button"
                    onClick={(e) => { e.stopPropagation(); if (onSourceClick) onSourceClick(card.source_label!, card.page_number ?? 1, card.start_time); }}
                    className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-all text-white/55 bg-white/10 hover:text-white hover:bg-white/20">
                    <FilePdf size={12} weight="bold" /> {card.source_label}{card.page_number && card.source_label ? `, ${_chunkLabel(card.source_label, card.page_number, card.start_time)}` : card.page_number ? `, S. ${card.page_number}` : ""}
                  </button>
                )}
                {onAskChat && (
                  <button type="button" onClick={(e) => { e.stopPropagation(); onAskChat(isVocab
                      ? `Erkläre mir den Begriff „${card.front}" genauer. Was bedeutet er, in welchem Kontext wird er verwendet und welche Zusammenhänge sind wichtig?`
                      : `Erkläre mir folgendes Thema genauer: „${card.front}". Was sind wichtige Details, Beispiele und Zusammenhänge?`); }}
                    className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-all text-white/55 bg-white/10 hover:text-white hover:bg-white/20">
                    <Chat size={13} weight="bold" /> Mehr erfahren
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
        {/* Actions */}
        <div className="flex items-center justify-center gap-6 min-h-[48px]">
          {flipped ? (
            <>
              <button type="button" onClick={() => answer(false)} title="Nochmal"
                className="w-11 h-11 rounded-full flex items-center justify-center transition-all hover:scale-110"
                style={{ border: "2px solid #d4453a", color: "#d4453a", backgroundColor: "var(--surface)", boxShadow: "0 1px 3px rgba(0,40,60,0.06)" }}>
                <XIcon size={18} weight="bold" />
              </button>
              <button type="button" onClick={() => answer(true)} title="Gewusst!"
                className="w-11 h-11 rounded-full flex items-center justify-center transition-all hover:scale-110"
                style={{ border: "2px solid #1a8a5c", color: "#1a8a5c", backgroundColor: "var(--surface)", boxShadow: "0 1px 3px rgba(0,40,60,0.06)" }}>
                <Check size={18} weight="bold" />
              </button>
            </>
          ) : (
            <button type="button" onClick={() => setFlipped(true)}
              className="px-6 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
              style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
              Antwort zeigen
            </button>
          )}
        </div>
      </div>
      </>
      ) : null}
    </div>
  );
}

// ─── Exercise Completion Screen ─────────────────────────────────────────────

function ExerciseCompletion({
  title, results, total, onRetryWrong, onBack, breadcrumbs,
}: {
  title: string; results: { item_id: number; correct: boolean }[];
  total: number; onRetryWrong: () => void; onBack: () => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const correct = results.filter((r) => r.correct).length;
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} onBack={onBack} breadcrumbs={breadcrumbs} />
      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-2">
        {/* Animated check */}
        <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
          style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
          <Check size={30} weight="bold" color="white" />
        </div>
        <h3 className="text-lg font-semibold" style={{ color: "var(--text)" }}>Geschafft!</h3>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          <strong style={{ color: "#1a8a5c" }}>{correct} / {total}</strong> gewusst — <strong style={{ color: "#1a8a5c" }}>{pct}%</strong>
        </p>
        <div className="flex gap-2 mt-4">
          {correct < total && (
            <button type="button" onClick={onRetryWrong}
              className="px-4 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
              style={{ color: "var(--accent)", backgroundColor: "var(--surface)", border: "1.5px solid var(--border)" }}>
              Falsche wiederholen
            </button>
          )}
          <button type="button" onClick={onBack}
            className="px-4 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
            style={{ backgroundColor: "var(--accent)" }}>
            Zur Übersicht
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Multiple Choice Exercise View (Lückentext + Vokabeltest) ───────────────

function MCExerciseView({
  exerciseSet, tool, onBack, onAnswer, onAskChat, onSourceClick, breadcrumbs,
}: {
  exerciseSet: ExerciseSet;
  tool: "lueckentext" | "vokabeltest" | "quiz";
  onBack: () => void;
  onAnswer: (itemId: number, correct: boolean, newRun?: boolean) => void;
  onAskChat: (text: string) => void;
  onSourceClick?: (filename: string, page: number, startTime?: number) => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const minimize = useContext(MinimizeContext);
  const [shuffledItems, setShuffledItems] = useState<ExerciseItem[]>([]);
  const shuffledRef = useRef(false);
  useEffect(() => {
    const raw = exerciseSet.items || [];
    if (raw.length > 0 && !shuffledRef.current) {
      const arr = [...raw];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; }
      if (tool === "quiz") {
        const shuffled = arr.map((item) => {
          if (!item.options || item.correct_idx === undefined) return item;
          const indices = item.options.map((_, i) => i);
          for (let i = indices.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [indices[i], indices[j]] = [indices[j], indices[i]]; }
          return { ...item, options: indices.map((i) => item.options![i]), correct_idx: indices.indexOf(item.correct_idx) };
        });
        setShuffledItems(shuffled);
      } else {
        setShuffledItems(arr);
      }
      shuffledRef.current = true;
    }
  }, [exerciseSet.items, tool]);
  const items = shuffledItems;
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [results, setResults] = useState<{ item_id: number; correct: boolean }[]>([]);
  const [streak, setStreak] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [hintLoading, setHintLoading] = useState(false);

  const total = items.length;
  const card = items[index];
  const answered = selected !== null;
  const isCorrect = answered && selected === card?.correct_idx;

  function select(optIdx: number) {
    if (answered || !card) return;
    setSelected(optIdx);
    const correct = optIdx === card.correct_idx;
    const isFirst = results.length === 0;
    setResults(prev => [...prev, { item_id: card.id, correct }]);
    if (correct) setStreak((s) => s + 1);
    else setStreak(0);
    onAnswer(card.id, correct, isFirst);
  }

  function advance() {
    if (index >= total - 1) {
      if (tool === "quiz") {
        setShowResults(true);
      } else {
        onBack();
      }
    } else {
      setIndex((i) => i + 1);
      setSelected(null);
      setHint(null);
    }
  }

  async function requestHint() {
    if (!card || hintLoading) return;
    setHintLoading(true);
    try {
      onAskChat(`Gib mir einen kurzen Tipp zur folgenden Frage, OHNE die Antwort zu verraten.: „${card.front}"`);
    } catch { /* ignore */ }
    setHintLoading(false);
  }

  if (!card && !showResults) return (
    <div className="flex flex-col h-full items-center justify-center gap-3">
      <Spinner />
      <p className="text-xs" style={{ color: "var(--muted)" }}>Wird geladen…</p>
    </div>
  );
  const progressPct = showResults ? 100 : ((index + 1) / total) * 100;
  const options = card?.options || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)", backgroundColor: "var(--surface)" }}>
        <button type="button" onClick={onBack}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
          <CaretLeft size={13} />
        </button>
        {breadcrumbs && breadcrumbs.length > 0 ? (<div className="flex items-center gap-1 text-[12px] min-w-0 flex-1">{breadcrumbs.map((b, i) => (<React.Fragment key={i}><button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: "var(--muted)" }}>{b.label}</button><CaretRight size={9} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" /></React.Fragment>))}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span></div>) : (<span className="text-[12px] font-semibold flex-1 truncate" style={{ color: "var(--text)" }}>{exerciseSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}</span>)}
        {minimize && (
          <button type="button" onClick={minimize}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
            title="Panel minimieren">
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        )}
      </div>
      {/* Progress — rendered inside question card */}
      {/* Quiz Results */}
      {showResults && tool === "quiz" ? (
        <div className="flex-1 flex flex-col items-center justify-center px-6 gap-3">
          <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
            style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
            <Check size={30} weight="bold" color="white" />
          </div>
          <h3 className="text-lg font-semibold" style={{ color: "var(--text)" }}>Quiz abgeschlossen!</h3>
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            <strong style={{ color: "#1a8a5c" }}>{results.filter(r => r.correct).length} / {total}</strong> richtig — <strong style={{ color: "#1a8a5c" }}>{Math.round((results.filter(r => r.correct).length / total) * 100)}%</strong>
          </p>
          <div className="flex gap-3 mt-4">
            <button type="button" onClick={() => { setShowResults(false); setIndex(0); setSelected(null); setResults([]); shuffledRef.current = false; }}
              className="px-5 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
              style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}>
              Erneut versuchen
            </button>
            <button type="button" onClick={onBack}
              className="px-5 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
              style={{ backgroundColor: "var(--accent)" }}>
              Fertig
            </button>
          </div>
        </div>
      ) : card ? (
      <>
      {/* Progress bar */}
      <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
        <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${progressPct}%`, backgroundColor: "var(--kb)" }} />
      </div>
      {/* Question Card */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto mt-6 w-full" style={{ maxWidth: 560 }}>
          <div className="rounded-2xl flex flex-col gap-4 overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
            <div className="px-6 pt-5 pb-6 flex flex-col gap-4">
            {/* Counter */}
            <span className="text-[11px] font-semibold" style={{ color: "var(--muted)" }}>Frage {index + 1} / {total}</span>
            {/* Question text */}
            {tool === "lueckentext" ? (
              <p className="text-sm leading-relaxed" style={{ color: "var(--text)" }}
                dangerouslySetInnerHTML={{
                  __html: card.front.replace(
                    /___+/g,
                    answered
                      ? `<span style="font-weight:700;color:${isCorrect ? '#1a8a5c' : '#d4453a'};border-bottom:2px solid ${isCorrect ? '#1a8a5c' : '#d4453a'};padding:0 4px">${card.back}</span>`
                      : '<span style="display:inline-block;min-width:80px;border-bottom:2px dashed var(--kb);color:var(--kb);font-weight:700;padding:0 4px">___________</span>'
                  ),
                }}
              />
            ) : (
              <p className="text-sm font-semibold leading-snug" style={{ color: "var(--text)" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
            )}
            {/* Options */}
            <div className="flex flex-col gap-2 mt-1">
              {options.map((opt, oi) => {
                const isThis = selected === oi;
                const isRight = oi === card.correct_idx;
                let borderColor = "var(--border)";
                let bg = "var(--bg)";
                let dotBg = "var(--border)";
                let dotColor = "var(--muted)";
                if (answered && isRight) { borderColor = "#1a8a5c"; bg = "rgba(26,138,92,0.08)"; dotBg = "#1a8a5c"; dotColor = "#fff"; }
                else if (answered && isThis && !isRight) { borderColor = "#d4453a"; bg = "rgba(212,69,58,0.07)"; dotBg = "#d4453a"; dotColor = "#fff"; }
                return (
                  <button key={oi} type="button" onClick={() => select(oi)}
                    disabled={answered}
                    className={`w-full text-left flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${!answered ? "hover:shadow-sm active:scale-[0.98] cursor-pointer" : ""}`}
                    style={{ border: `1.5px solid ${borderColor}`, backgroundColor: bg, color: "var(--text)", opacity: answered && !isThis && !isRight ? 0.45 : 1 }}
                    onMouseEnter={(e) => { if (!answered) e.currentTarget.style.borderColor = "var(--kb)"; }}
                    onMouseLeave={(e) => { if (!answered) e.currentTarget.style.borderColor = borderColor; }}>
                    <span className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                      style={{ backgroundColor: dotBg, color: dotColor }}>
                      {String.fromCharCode(65 + oi)}
                    </span>
                    <span dangerouslySetInnerHTML={{ __html: _md(opt) }} />
                  </button>
                );
              })}
            </div>
            {/* Feedback */}
            {answered && (
              <div className="text-sm font-semibold px-4 py-2.5 rounded-xl"
                style={isCorrect
                  ? { color: "#1a8a5c", backgroundColor: "rgba(26,138,92,0.08)" }
                  : { color: "#d4453a", backgroundColor: "rgba(212,69,58,0.07)" }}>
                {isCorrect ? "✓ Richtig!" : <span dangerouslySetInnerHTML={{ __html: `✗ Richtig wäre: ${_md(card.back)}` }} />}
              </div>
            )}
            {/* Source chip + Hint */}
            <div className="flex items-center justify-between mt-1">
              <div>
                {card.source_label && (
                  <button type="button"
                    onClick={() => { if (onSourceClick) onSourceClick(card.source_label!, card.page_number ?? 1, card.start_time); }}
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 rounded-full border-none cursor-pointer transition-opacity hover:opacity-80"
                    style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                    <FilePdf size={12} weight="bold" /> {card.source_label}{card.page_number && card.source_label ? `, ${_chunkLabel(card.source_label, card.page_number, card.start_time)}` : card.page_number ? `, S. ${card.page_number}` : ""}
                  </button>
                )}
              </div>
              {tool === "quiz" && !answered && (
                <button type="button" onClick={requestHint}
                  disabled={hintLoading}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all hover:opacity-80 disabled:opacity-50"
                  style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                  <Lightbulb size={13} weight="bold" />
                  {hintLoading ? "Wird geladen…" : "Tipp"}
                </button>
              )}
            </div>
            {/* Action row: Chat + Weiter */}
            {answered && (
              <div className="flex items-center justify-between mt-2">
                <button type="button" onClick={() => onAskChat(tool === "vokabeltest" || tool === "lueckentext"
                    ? `Erkläre mir den Begriff „${tool === "lueckentext" ? card.back : card.front}" genauer. Was bedeutet er, in welchem Kontext wird er verwendet und welche Zusammenhänge sind wichtig?`
                    : `Erkläre mir folgendes Thema genauer: „${card.front}". Was sind wichtige Details, Beispiele und Zusammenhänge?`)}
                  className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-all hover:opacity-80"
                  style={{ color: "var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }}>
                  <Chat size={13} weight="bold" /> Mehr erfahren
                </button>
                <button type="button" onClick={advance}
                  className="flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-semibold text-white transition-all hover:opacity-90"
                  style={{ backgroundColor: "var(--kb)" }}>
                  {index >= total - 1 ? "Abschließen" : "Weiter"} <CaretRight size={14} weight="bold" />
                </button>
              </div>
            )}
          </div>
          </div>
        </div>
      </div>
      </>
      ) : null}
    </div>
  );
}

// ─── Create Set Modal ───────────────────────────────────────────────────────

function CreateSetModal({
  tool, glossaryCount, selectedSource, creating,
  onClose, onCreate,
}: {
  tool: string; glossaryCount: number; selectedSource?: { uuid: string; filename: string } | null;
  creating: boolean;
  onClose: () => void;
  onCreate: (mode: string, count: number) => void;
}) {
  const isQuiz = tool === "quiz";
  const [mode, setMode] = useState<"glossar" | "quelle">(isQuiz || glossaryCount === 0 ? "quelle" : "glossar");
  const [count, setCount] = useState(isQuiz ? 5 : 10);
  const toolLabels: Record<string, string> = { karteikarten: "Karteikarten", lernkarten: "Lernkarten", lueckentext: "Lückentext", vokabeltest: "Begriffe-Quiz", quiz: "Quiz" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-[340px]" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text)" }}>Neue {toolLabels[tool] || "Übung"} erstellen</h3>

        {/* Mode */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>Quelle</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && (
            <button type="button" onClick={() => glossaryCount > 0 && setMode("glossar")}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
              style={{
                ...(mode === "glossar"
                  ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)", color: "var(--text)" }
                  : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)" }),
                ...(glossaryCount === 0 ? { opacity: 0.4, pointerEvents: "none" as const } : {}),
              }}>
              <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
                style={{ borderColor: mode === "glossar" ? "var(--accent)" : "var(--border)" }}>
                {mode === "glossar" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--accent)" }} />}
              </div>
              Aus Glossar <span className="text-[10px]" style={{ color: "var(--muted)" }}>({glossaryCount} Begriffe)</span>
            </button>
          )}
          <button type="button" onClick={() => selectedSource && setMode("quelle")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
            style={{
              ...(mode === "quelle"
                ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)" }),
              color: "var(--text)",
              opacity: selectedSource ? 1 : 0.4,
              pointerEvents: selectedSource ? "auto" : "none",
            }}>
            <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
              style={{ borderColor: mode === "quelle" ? "var(--accent)" : "var(--border)" }}>
              {mode === "quelle" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--accent)" }} />}
            </div>
            Aus ausgewählter Quelle {selectedSource && <span className="text-[10px] inline-block max-w-[120px] truncate align-bottom" title={selectedSource.filename} style={{ color: "var(--muted)" }}>({selectedSource.filename})</span>}
          </button>
          {!selectedSource && (
            <p className="text-[10px] ml-5" style={{ color: "#c4820e" }}>
              Wähle links eine Quelle aus, um aus ihr zu generieren.
            </p>
          )}
        </div>

        {/* Count */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>Anzahl</div>
        <div className="flex gap-1.5 mb-4">
          {[5, 10, 15].map((n) => (
            <button key={n} type="button" onClick={() => setCount(n)}
              className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all text-center"
              style={count === n
                ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)", color: "var(--accent)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)" }}>
              {n}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
            style={{ color: "var(--accent)", backgroundColor: "var(--surface)", border: "1.5px solid var(--border)" }}>
            Abbrechen
          </button>
          <button type="button" onClick={() => onCreate(mode, count)} disabled={creating}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: "var(--accent)" }}>
            {creating ? <Spinner size="xs" color="current" /> : <Plus size={13} weight="bold" />}
            {creating ? "Generieren…" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

function QuizStudio({
  questions, loading, answers, onGenerate, onAnswer, onBack, sourceCount, breadcrumbs,
}: {
  questions: QuizQuestion[]; loading: boolean; answers: Record<number, number>;
  onGenerate: () => void; onAnswer: (qi: number, ai: number) => void; onBack: () => void;
  sourceCount: number;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [view, setView] = useState<"list" | "viewer">("list");
  const correct = Object.entries(answers).filter(([qi, ai]) => questions[Number(qi)]?.correct === ai).length;
  const total = Object.keys(answers).length;
  const noSources = sourceCount === 0;

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title="Quiz" onBack={onBack} breadcrumbs={breadcrumbs} />
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
                  : `${sourceCount} Quellen vorhanden — es werden maximal 5 berücksichtigt`}
          </div>

          <div className="flex justify-center">
            <button type="button" onClick={() => { onGenerate(); setView("viewer"); }}
              disabled={noSources || loading}
              className="flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold text-white transition-all hover:opacity-90 disabled:opacity-40"
              style={{ backgroundColor: "var(--kb)", maxWidth: 280, width: "100%" }}>
              {loading
                ? <><Spinner size="xs" color="current" /> Wird generiert…</>
                : <><Plus size={13} weight="bold" /> Neues Quiz erstellen</>}
            </button>
          </div>
        </div>
      </div>

      {/* ── Viewer ── */}
      <div style={{ display: view === "viewer" ? "flex" : "none" }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setView("list")}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (<div className="flex items-center gap-1 text-sm min-w-0 flex-1">{breadcrumbs.map((b, i) => (<React.Fragment key={i}><button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: "var(--muted)" }}>{b.label}</button><CaretRight size={10} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" /></React.Fragment>))}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>Quiz</span></div>) : (<span className="text-base font-bold flex-1" style={{ color: "var(--text)" }}>Quiz</span>)}
          {total > 0 && questions.length > 0 && (
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}>
              {correct} / {questions.length} richtig
            </span>
          )}
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex-1 flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <Spinner />
                <p className="text-xs" style={{ color: "var(--muted)" }}>Quiz wird generiert…</p>
              </div>
            </div>
          )}
          {!loading && questions.length > 0 && (
            <div className="mx-auto w-full p-4 flex flex-col gap-4" style={{ maxWidth: 560 }}>
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
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Placeholder Studio (coming soon) ────────────────────────────────────────

function PlaceholderStudio({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} onBack={onBack} />
      <div className="flex-1 flex items-center justify-center">
        <p className="text-xs" style={{ color: "var(--muted)" }}>Coming soon</p>
      </div>
    </div>
  );
}

// ─── Infografik: Icon mapping ────────────────────────────────────────────────

import * as PhosphorIcons from "@phosphor-icons/react";

const ICON_MAP: Record<string, any> = {
  GraduationCap: PhosphorIcons.GraduationCap, Student: PhosphorIcons.Student,
  Brain: PhosphorIcons.Brain, Lightbulb: PhosphorIcons.Lightbulb,
  RocketLaunch: PhosphorIcons.RocketLaunch, Target: PhosphorIcons.Target,
  TrendUp: PhosphorIcons.TrendUp, TrendDown: PhosphorIcons.TrendDown,
  ChartBar: PhosphorIcons.ChartBar, ChartLine: PhosphorIcons.ChartLine,
  Globe: PhosphorIcons.Globe, GlobeHemisphereWest: PhosphorIcons.GlobeHemisphereWest,
  Translate: PhosphorIcons.Translate, Book: PhosphorIcons.Book, BookOpen: PhosphorIcons.BookOpen,
  Users: PhosphorIcons.Users, UserCirclePlus: PhosphorIcons.UserCirclePlus,
  Handshake: PhosphorIcons.Handshake, Buildings: PhosphorIcons.Buildings,
  Bank: PhosphorIcons.Bank, Factory: PhosphorIcons.Factory, Briefcase: PhosphorIcons.Briefcase,
  Certificate: PhosphorIcons.Certificate, Medal: PhosphorIcons.Medal,
  Trophy: PhosphorIcons.Trophy, Star: PhosphorIcons.Star, Heart: PhosphorIcons.Heart,
  Shield: PhosphorIcons.Shield, Lock: PhosphorIcons.Lock, Key: PhosphorIcons.Key,
  Path: PhosphorIcons.Path, Signpost: PhosphorIcons.Signpost, MapPin: PhosphorIcons.MapPin,
  Compass: PhosphorIcons.Compass, Flag: PhosphorIcons.Flag,
  Gear: PhosphorIcons.Gear, Wrench: PhosphorIcons.Wrench, Code: PhosphorIcons.Code,
  Desktop: PhosphorIcons.Desktop, Robot: PhosphorIcons.Robot,
  MagicWand: PhosphorIcons.MagicWand, Sparkle: PhosphorIcons.Sparkle,
  ChatCircle: PhosphorIcons.ChatCircle, Megaphone: PhosphorIcons.Megaphone,
  Eye: PhosphorIcons.Eye, Binoculars: PhosphorIcons.Binoculars,
  MagnifyingGlass: PhosphorIcons.MagnifyingGlass,
  Clock: PhosphorIcons.Clock, Calendar: PhosphorIcons.Calendar,
  Timer: PhosphorIcons.Timer, Lightning: PhosphorIcons.Lightning, Fire: PhosphorIcons.Fire,
  Leaf: PhosphorIcons.Leaf, ArrowRight: PhosphorIcons.ArrowRight, ArrowUp: PhosphorIcons.ArrowUp,
  ArrowsClockwise: PhosphorIcons.ArrowsClockwise, Checks: PhosphorIcons.Checks,
  Warning: PhosphorIcons.Warning, Info: PhosphorIcons.Info, Question: PhosphorIcons.Question,
  Coins: PhosphorIcons.Coins, CurrencyDollar: PhosphorIcons.CurrencyDollar,
  Percent: PhosphorIcons.Percent, Calculator: PhosphorIcons.Calculator,
  Network: PhosphorIcons.Network, TreeStructure: PhosphorIcons.TreeStructure,
  FlowArrow: PhosphorIcons.FlowArrow, GitBranch: PhosphorIcons.GitBranch,
};

// THL Corporate Design — immer diese Farben
const COLOR_SCHEMES: Record<string, { primary: string; accent: string; light: string; gradient: string }> = {
  blue: { primary: "#004261", accent: "#0E7490", light: "#E0F2FE", gradient: "linear-gradient(135deg, #004261, #0E7490)" },
  teal: { primary: "#004261", accent: "#0E7490", light: "#E0F2FE", gradient: "linear-gradient(135deg, #004261, #0E7490)" },
  orange: { primary: "#004261", accent: "#0E7490", light: "#E0F2FE", gradient: "linear-gradient(135deg, #004261, #0E7490)" },
  purple: { primary: "#004261", accent: "#0E7490", light: "#E0F2FE", gradient: "linear-gradient(135deg, #004261, #0E7490)" },
};

function PhIcon({ name, size = 24, color, weight = "duotone" as const }: { name: string; size?: number; color?: string; weight?: any }) {
  const Comp = ICON_MAP[name] || PhosphorIcons.CircleDashed;
  return <Comp size={size} color={color} weight={weight} />;
}

// ─── Infografik: Layout Renderer ─────────────────────────────────────────────



// ─── Infografik Studio ───────────────────────────────────────────────────────


// ─── Datentabelle Studio ─────────────────────────────────────────────────────

function DatentabelleStudio({
  table, sources, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, sourceCount,
  allSources, onPillClick, stats, breadcrumbs,
}: {
  table: DatentabelleData | null;
  sources: DatentabelleSource[];
  loading: boolean;
  onGenerate: () => void;
  onBack: () => void;
  savedList: { id: number; title: string; created_at: string | null }[];
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
  sourceCount: number;
  allSources?: Source[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [view, setView] = useState<"viewer" | "list">("list");
  const noSources = sourceCount === 0;
  const atLimit = savedList.length >= 20;
  const activeTitle = table?.title || "Datentabelle";

  return (
    <div className="flex flex-col h-full">
      {/* ── List view ── */}
      <div style={{ display: view === "list" ? "flex" : "none" }} className="flex-col h-full">
        <SubviewHeader title="Datentabelle" onBack={onBack} breadcrumbs={breadcrumbs} />
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
                  : `${sourceCount} Quellen vorhanden — es werden maximal 5 berücksichtigt`}
          </div>

          {savedList.length === 0 && !loading ? (
            <div className="flex flex-col items-center gap-3 pt-[15%]">
              <Table size={48} weight="duotone" style={{ color: "var(--border)" }} />
              <p className="text-sm text-center" style={{ color: "var(--muted)" }}>Wähle Quellen aus und drücke auf Erstellen.</p>
              <button type="button" onClick={() => onGenerate()}
                disabled={noSources || loading || atLimit}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                <Plus size={12} weight="bold" /> Erstellen ({savedList.length}/20)
              </button>
            </div>
          ) : (
            <>
              <div className="flex justify-center">
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                  style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                  <Plus size={12} weight="bold" /> Erstellen ({savedList.length}/20)
                </button>
              </div>
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>{savedList.length} {savedList.length === 1 ? "Datentabelle" : "Datentabellen"}</span>
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
                      <Table size={16} weight="duotone" style={{ color: "var(--kb)", flexShrink: 0 }} />
                      <span className="text-[12px] font-semibold leading-snug flex-1 line-clamp-3 kis-tooltip" style={{ color: "var(--text)" }} data-tip={item.title}>
                        {item.title}
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

      {/* ── Viewer ── */}
      <div style={{ display: view === "viewer" ? "flex" : "none" }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => setView("list")}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (<div className="flex items-center gap-1 text-sm min-w-0 flex-1">{breadcrumbs.map((b, i) => (<React.Fragment key={i}><button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: "var(--muted)" }}>{b.label}</button><CaretRight size={10} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" /></React.Fragment>))}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>{activeTitle}</span></div>) : (<span className="text-base font-bold flex-1 truncate" style={{ color: "var(--text)" }}>{activeTitle}</span>)}
        </div>
        <div className="flex-1 overflow-y-auto">
          {!table && loading && (
            <div className="flex-1 flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <Spinner />
                <p className="text-xs" style={{ color: "var(--muted)" }}>Datentabelle wird generiert…</p>
              </div>
            </div>
          )}
          {table && (
            <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ maxWidth: 900, userSelect: "text" }}>
              <p className="text-[11px]" style={{ color: "var(--muted)" }}>
                Basierend auf {sources.length} Quelle{sources.length !== 1 ? "n" : ""}
              </p>

              <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid var(--border)" }}>
                <table className="w-full border-collapse text-xs" style={{ minWidth: 500 }}>
                  <thead>
                    <tr>
                      {table.columns.map((col, i) => (
                        <th key={i}
                          className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap"
                          style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", borderBottom: "1px solid var(--border)" }}>
                          {col}
                        </th>
                      ))}
                      <th className="px-3 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap"
                        style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)", borderBottom: "1px solid var(--border)" }}>
                        Quelle
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {table.rows.map((row, ri) => (
                      <tr key={ri} style={{ backgroundColor: ri % 2 === 0 ? "var(--bg)" : "var(--surface)" }}>
                        {row.cells.map((cell, ci) => (
                          <td key={ci} className="px-3 py-2 align-top leading-snug"
                            style={{ borderBottom: "1px solid var(--border)", color: "var(--text)" }}>
                            {cell}
                          </td>
                        ))}
                        <td className="px-3 py-2 align-top"
                          style={{ borderBottom: "1px solid var(--border)" }}>
                          <div className="flex flex-wrap gap-1">
                            {row.sources.map((s, si) => {
                              if (typeof s === "object" && s !== null && "source_label" in s) {
                                const rs = s as DatentabelleRowSource;
                                const src = allSources?.find((a) => a.filename === rs.source_label);
                                const isMedia = _isMediaFile(rs.source_label);
                                const SourceIcon = isMedia ? SpeakerHigh : FilePdf;
                                let pageNum = 0;
                                let startTime: number | undefined;
                                const label = isMedia ? String(rs.page) : `S. ${rs.page}`;
                                if (isMedia && typeof rs.page === "string") {
                                  const parts = rs.page.split(":").map(Number);
                                  if (parts.length === 3) startTime = parts[0] * 3600 + parts[1] * 60 + parts[2];
                                  else if (parts.length === 2) startTime = parts[0] * 60 + parts[1];
                                } else {
                                  pageNum = typeof rs.page === "number" ? rs.page : parseInt(String(rs.page), 10) || 0;
                                }
                                return (
                                  <button key={si} type="button"
                                    onClick={() => src && onPillClick?.(src.uuid, pageNum, src.filename, rs.highlight, startTime)}
                                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity whitespace-nowrap"
                                    style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}>
                                    <SourceIcon size={10} weight="bold" />
                                    [{si + 1}] {label}
                                  </button>
                                );
                              }
                              const num = s as number;
                              const legend = sources.find((src) => src.number === num);
                              const fname = legend?.filename || "";
                              const src = legend ? allSources?.find((a) => a.filename === fname) : undefined;
                              const isMedia = fname ? _isMediaFile(fname) : false;
                              const LegacyIcon = isMedia ? SpeakerHigh : FilePdf;
                              return (
                                <button key={si} type="button"
                                  onClick={() => src && onPillClick?.(src.uuid, 0, src.filename)}
                                  className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity whitespace-nowrap"
                                  style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}>
                                  <LegacyIcon size={10} weight="bold" />
                                  [{num}]
                                </button>
                              );
                            })}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {sources.length > 0 && (
                <div className="flex flex-col gap-1 pt-2">
                  {sources.map((s) => (
                    <p key={s.number} className="text-[11px] leading-snug" style={{ color: "var(--muted)" }}>
                      [{s.number}] {s.filename}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Mindmap Studio ──────────────────────────────────────────────────────────

interface MindmapNodeData {
  topic: string;
  children?: MindmapNodeData[];
  source_label?: string;
  page_number?: number | string;
  keyword?: string;
}

function MindmapStudio({
  mindmap, loading, onGenerate, onBack,
  savedList, onSelect, onDelete, sourceCount,
  sources, onPillClick, stats, breadcrumbs,
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
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const meInstanceRef = useRef<any>(null);
  const [view, setView] = useState<"viewer" | "list">("list");
  const [allExpanded, setAllExpanded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
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
            // Phosphor bold icons — same as chat pills (FilePdf / Play)
            const icon = isMedia
              ? `<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 256 256" fill="currentColor" style="vertical-align:-1px;flex-shrink:0"><path d="M234.49,111.07,90.41,22.94A20,20,0,0,0,60,39.87V216.13a20,20,0,0,0,30.41,16.93l144.08-88.13a19.82,19.82,0,0,0,0-33.86ZM84,208.85V47.15L216.16,128Z"/></svg>`
              : `<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8" viewBox="0 0 256 256" fill="currentColor" style="vertical-align:-1px;flex-shrink:0"><path d="M200,164v8h12a12,12,0,0,1,0,24H200v12a12,12,0,0,1-24,0V152a12,12,0,0,1,12-12h32a12,12,0,0,1,0,24ZM92,172a32,32,0,0,1-32,32H56v4a12,12,0,0,1-24,0V152a12,12,0,0,1,12-12H60A32,32,0,0,1,92,172Zm-24,0a8,8,0,0,0-8-8H56v16h4A8,8,0,0,0,68,172Zm100,8a40,40,0,0,1-40,40H112a12,12,0,0,1-12-12V152a12,12,0,0,1,12-12h16A40,40,0,0,1,168,180Zm-24,0a16,16,0,0,0-16-16h-4v32h4A16,16,0,0,0,144,180ZM36,108V40A20,20,0,0,1,56,20h96a12,12,0,0,1,8.49,3.52l56,56A12,12,0,0,1,220,88v20a12,12,0,0,1-24,0v-4H148a12,12,0,0,1-12-12V44H60v64a12,12,0,0,1-24,0ZM160,57V80h23Z"/></svg>`;
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
              color: noSources ? "#B91C1C" : sourceCount > 1 ? "#c4820e" : "var(--kb)",
            }}>
            <Files size={13} weight="bold" />
            {noSources
              ? "Keine Quelle ausgewählt"
              : sourceCount === 1
                ? "1 Quelle ausgewählt"
                : `${sourceCount} Quellen vorhanden — es wird maximal 1 berücksichtigt`}
          </div>

          {savedList.length === 0 && !loading ? (
            <div className="flex flex-col items-center gap-3 pt-[15%]">
              <TreeStructure size={48} weight="duotone" style={{ color: "var(--border)" }} />
              <p className="text-sm text-center" style={{ color: "var(--muted)" }}>Wähle Quellen aus und drücke auf Erstellen.</p>
              <button type="button" onClick={() => onGenerate()}
                disabled={noSources || loading || atLimit}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                <Plus size={12} weight="bold" /> Erstellen ({savedList.length}/20)
              </button>
            </div>
          ) : (
            <>
              <div className="flex justify-center">
                <button type="button" onClick={() => onGenerate()}
                  disabled={noSources || loading || atLimit}
                  className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
                  style={{ color: "var(--kb)", backgroundColor: "#fff", border: "1.5px solid var(--kb)" }}>
                  <Plus size={12} weight="bold" /> Erstellen ({savedList.length}/20)
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
      <div style={{
        display: view === "viewer" ? "flex" : "none",
        ...(fullscreen ? { position: "fixed" as const, inset: 0, zIndex: 9999, backgroundColor: "var(--bg)" } : {}),
      }} className="flex-col h-full">
        <div className="flex items-center gap-2 px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <button type="button" onClick={() => { if (fullscreen) setFullscreen(false); else setView("list"); }}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
            <CaretLeft size={13} />
          </button>
          {breadcrumbs ? (<div className="flex items-center gap-1 text-sm min-w-0 flex-1">{breadcrumbs.map((b, i) => (<React.Fragment key={i}><button type="button" onClick={b.onClick} className="font-medium hover:underline shrink-0" style={{ color: "var(--muted)" }}>{b.label}</button><CaretRight size={10} weight="bold" style={{ color: "var(--muted)", opacity: 0.5 }} className="shrink-0" /></React.Fragment>))}<span className="font-semibold truncate" style={{ color: "var(--text)" }}>{activeTopicName}</span></div>) : (<span className="text-base font-bold flex-1 truncate" style={{ color: "var(--text)" }}>{activeTopicName}</span>)}
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
            <button type="button" onClick={() => setFullscreen(!fullscreen)} title={fullscreen ? "Vollbild beenden" : "Vollbild"}
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
                <Spinner />
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

// ─── Notizen Studio ──────────────────────────────────────────────────────────

interface Note { id: number; content: string; created_at: string | null }

function NotizenStudio({
  notes, onAdd, onDelete, onBack, sources, activeSourceIds, onPillClick, stats, breadcrumbs,
}: {
  notes: Note[]; onAdd: (content: string) => void; onDelete: (id: number) => void; onBack?: () => void;
  sources?: Source[]; activeSourceIds?: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [draft, setDraft] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [draft]);

  const getFilename = (srcUuid: string) =>
    sources?.find((s) => s.uuid === srcUuid)?.filename ?? srcUuid;

  function parseNoteCitations(text: string): React.ReactNode[] {
    const pattern = /\[(?:Q(\d+),\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))\]/g;
    const nodes: React.ReactNode[] = [];
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = pattern.exec(text)) !== null) {
      if (m.index > last) nodes.push(text.slice(last, m.index));
      const pageNum = m[2] ? parseInt(m[2]) : 0;
      const timestamp = m[3] || null;
      const isMedia = !!timestamp;

      // Best-effort source resolution: first media or first PDF source
      const sourceUuid = isMedia
        ? (sources?.find(s => _isMediaFile(s.filename))?.uuid ?? activeSourceIds?.[0] ?? "")
        : (sources?.find(s => !_isMediaFile(s.filename))?.uuid ?? activeSourceIds?.[0] ?? "");
      const filename = getFilename(sourceUuid);

      if (isMedia && timestamp) {
        const parts = timestamp.split(":").map(Number);
        const seconds = parts.length === 3 ? parts[0] * 3600 + parts[1] * 60 + parts[2] : parts[0] * 60 + parts[1];
        nodes.push(
          <button
            key={m.index}
            type="button"
            onClick={() => onPillClick?.(sourceUuid, 0, filename, undefined, seconds)}
            className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5"
            style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
            title={`${filename}, ${timestamp}`}
          >
            <Play size={8} weight="bold" />
            {timestamp}
          </button>
        );
      } else {
        nodes.push(
          <button
            key={m.index}
            type="button"
            onClick={() => onPillClick?.(sourceUuid, pageNum, filename)}
            className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium hover:opacity-80 transition-opacity align-middle mx-0.5"
            style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
            title={`${filename}, ${_chunkLabel(filename, pageNum)}`}
          >
            <FilePdf size={8} weight="bold" />
            {_chunkLabel(filename, pageNum)}
          </button>
        );
      }
      last = pattern.lastIndex;
    }
    if (last < text.length) nodes.push(text.slice(last));
    return nodes;
  }

  function withNoteCitations(children: React.ReactNode): React.ReactNode {
    return React.Children.map(children, (child) =>
      typeof child === "string" ? parseNoteCitations(child) : child
    );
  }

  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title="Notizen" onBack={onBack} breadcrumbs={breadcrumbs} />}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-3" style={{ maxWidth: 560 }}>
          {/* New note input */}
          <div
            className="flex gap-2 items-center rounded-xl p-2"
            style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
          >
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => { if (e.target.value.length <= 2000) setDraft(e.target.value); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && draft.trim()) { e.preventDefault(); onAdd(draft.trim()); setDraft(""); }
              }}
              placeholder="Neue Notiz…"
              maxLength={2000}
              rows={1}
              className="flex-1 text-sm resize-none focus:outline-none bg-transparent"
              style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
            />
            {draft.length > 1800 && (
              <span className="text-[10px] flex-shrink-0" style={{ color: draft.length >= 2000 ? "#ef4444" : "var(--muted)" }}>
                {draft.length}/2000
              </span>
            )}
            <button
              type="button"
              onClick={() => { if (draft.trim()) { onAdd(draft.trim()); setDraft(""); } }}
              disabled={!draft.trim()}
              className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-white disabled:opacity-40 transition-opacity hover:opacity-85"
              style={{ backgroundColor: "var(--kb)" }}
              title="Notiz speichern"
            >
              <Plus size={14} weight="bold" />
            </button>
          </div>

          {/* Notes grid */}
          {notes.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <NotePencil size={32} weight="light" />
              <span className="text-xs text-center">Noch keine Notizen. Erstelle eine oben oder speichere eine KI-Antwort als Notiz.</span>
            </div>
          )}
          <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {notes.map((note) => {
              const isExpanded = expandedId === note.id;
              return (
              <div
                key={note.id}
                className="group relative rounded-xl p-3 cursor-pointer hover:opacity-80 transition-opacity flex flex-col"
                style={{
                  backgroundColor: "var(--background)",
                  boxShadow: "0 2px 10px rgba(0,40,60,0.05), 0 0 0 1px rgba(0,40,60,0.03)",
                  minHeight: 90,
                  ...(isExpanded ? { gridColumn: "1 / -1" } : {}),
                }}
                onClick={() => setExpandedId(isExpanded ? null : note.id)}
              >
                <div
                  className={`text-sm pr-6 ki-note-content overflow-hidden flex-1 ${isExpanded ? "" : "max-h-[4.5em]"}`}
                  style={{ color: "var(--text)", ...(isExpanded ? {} : { WebkitMaskImage: "linear-gradient(to bottom, black 60%, transparent 100%)" }) }}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{withNoteCitations(children)}</p>,
                      ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
                      li: ({ children }) => <li className="leading-relaxed">{withNoteCitations(children)}</li>,
                      strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                      h1: ({ children }) => <p className="font-semibold mb-1">{withNoteCitations(children)}</p>,
                      h2: ({ children }) => <p className="font-semibold mb-1">{withNoteCitations(children)}</p>,
                      h3: ({ children }) => <p className="font-medium mb-1">{withNoteCitations(children)}</p>,
                      table: ({ children }) => <div className="overflow-x-auto my-2"><table className="w-full text-xs border-collapse">{children}</table></div>,
                      th: ({ children }) => <th className="text-left px-2 py-1 font-medium border-b" style={{ borderColor: "var(--border)" }}>{children}</th>,
                      td: ({ children }) => <td className="px-2 py-1 border-b" style={{ borderColor: "var(--border)" }}>{children}</td>,
                      hr: () => <hr className="my-3" style={{ borderColor: "var(--border)" }} />,
                    }}
                  >
                    {note.content}
                  </ReactMarkdown>
                </div>
                <div className="flex items-center justify-between mt-auto pt-1">
                  <span className="text-[10px] font-medium" style={{ color: "var(--muted)" }}>
                    {note.created_at ? new Date(note.created_at).toLocaleDateString("de-DE", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" }) : ""}
                  </span>
                  <button type="button" onClick={(e) => { e.stopPropagation(); onDelete(note.id); }}
                    className="w-6 h-6 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                    style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                    <Trash size={12} />
                  </button>
                </div>
              </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sprachtraining: Glossar ──────────────────────────────────────────────────

function GlossarMenu({ onDeleteAll }: { onDeleteAll?: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button type="button" onClick={() => setOpen(!open)}
        className="w-5 h-5 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
        style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
        <DotsThreeVertical size={12} weight="bold" />
      </button>
      {open && (
        <div className="absolute right-0 top-6 z-50 rounded-lg py-1"
          style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", minWidth: 160, boxShadow: "0 4px 16px rgba(0,0,0,0.12)" }}>
          <button type="button"
            onClick={() => { setOpen(false); onDeleteAll?.(); }}
            className="w-full text-left px-3 py-1.5 text-[11px] hover:opacity-70 transition-opacity"
            style={{ color: "#B91C1C" }}>
            Alle Begriffe löschen
          </button>
        </div>
      )}
    </div>
  );
}

function GlossarView({
  entries, loading, extracting, onGenerate, onBack, onOpenSource, onDelete, onDeleteAll, sourceCount = 0, stats, breadcrumbs, showTranslation,
}: {
  entries: GlossaryEntry[]; loading: boolean; extracting?: boolean;
  onGenerate: () => void; onBack?: () => void;
  onOpenSource?: (page: number, highlightText?: string) => void;
  onDelete?: (id: number) => void;
  onDeleteAll?: () => void;
  sourceCount?: number;
  stats?: StudentStats | null;
  breadcrumbs?: { label: string; onClick: () => void }[];
  showTranslation?: boolean;
}) {
  const noSources = sourceCount === 0;
  return (
    <div className="flex flex-col h-full">
      {onBack && <SubviewHeader title="Glossar" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-3" style={{ maxWidth: 560 }}>
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
                  : `${sourceCount} Quellen vorhanden — es werden maximal 5 berücksichtigt`}
          </div>
          {extracting && (
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-xl text-xs font-medium"
              style={{ backgroundColor: "rgba(var(--accent-rgb),0.06)", color: "var(--accent)" }}>
              <Spinner size="xs" color="current" />
              Begriffe werden aus Markierung extrahiert…
            </div>
          )}
          <div className="relative flex items-center justify-center gap-1.5 px-1">
            <button
              type="button"
              onClick={onGenerate}
              disabled={loading || noSources}
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80 disabled:opacity-40"
              style={{ color: "var(--accent)", backgroundColor: "#fff", border: "1.5px solid var(--accent)" }}
            >
              {loading ? <Spinner size="xs" color="current" /> : <Plus size={12} weight="bold" />}
              {loading ? "Begriffe werden extrahiert…" : "Begriffe extrahieren"}
            </button>
            <HelpTooltip text="Extrahiert 10–20 Fachbegriffe aus den ausgewählten Quellen. Maximal 150 Einträge." />
            {entries.length > 0 && (
              <div className="absolute right-0 flex items-center gap-1.5">
                <span className="text-xs font-medium" style={{ color: "var(--muted)" }}>{entries.length}/150</span>
                <GlossarMenu onDeleteAll={onDeleteAll} />
              </div>
            )}
          </div>


          {entries.length === 0 && !loading && (
            <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
              <Book size={32} weight="light" />
              <span className="text-xs text-center">Noch kein Glossar generiert. Klicke oben auf „Begriffe extrahieren", um Fachbegriffe aus deinen Quellen zu extrahieren.</span>
            </div>
          )}

          {entries.map((entry) => (
            <div
              key={entry.id}
              className="rounded-xl p-4 flex flex-col gap-2 relative group select-text"
              style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", userSelect: "text" }}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-sm font-bold" style={{ color: "var(--text)" }}>{entry.term_de}</span>
                  {showTranslation && <span className="text-sm font-medium ml-2" style={{ color: "var(--accent)" }}>{entry.term_en}</span>}
                </div>
                {entry.page_number && (
                  <button type="button" onClick={() => onOpenSource?.(entry.page_number!, entry.term_de)}
                    className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0 hover:opacity-80 transition-opacity"
                    style={{ backgroundColor: "rgba(var(--accent-rgb),0.12)", color: "var(--accent)" }}>
                    <FilePdf size={8} weight="bold" /> {entry.filename ? _chunkLabel(entry.filename, entry.page_number!) : `S. ${entry.page_number}`}
                  </button>
                )}
              </div>
              {showTranslation && (entry.example_sentence) && (
                <div>
                  <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>Kontext</span>
                  <p className="text-sm italic leading-relaxed mt-0.5" style={{ color: "var(--muted)" }}>
                    „{entry.example_sentence}"
                  </p>
                </div>
              )}
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>Erklärung (B1)</span>
                <p className="text-sm leading-relaxed mt-0.5" style={{ color: "var(--text)", opacity: 0.8 }}>
                  {entry.definition}
                </p>
              </div>
              <div className="flex justify-end mt-1">
                <button type="button" onClick={() => onDelete?.(entry.id)}
                  className="w-5 h-5 rounded-full flex items-center justify-center hover:opacity-70 transition-opacity"
                  style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}>
                  <Trash size={10} />
                </button>
              </div>
            </div>
          ))}

        </div>
      </div>
    </div>
  );
}

// ─── Sprachtraining: Karteikarten ────────────────────────────────────────────

function VocabFlashcards({
  entries, onBack, breadcrumbs,
}: {
  entries: GlossaryEntry[];
  onBack: () => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [results, setResults] = useState<{ glossary_entry_id: number; correct: boolean }[]>([]);
  const [finished, setFinished] = useState(false);

  useEffect(() => { setFlipped(false); }, [index]);

  const card = entries[index];
  const total = entries.length;
  const correctCount = results.filter((r) => r.correct).length;

  function handleAnswer(correct: boolean) {
    const newResults = [...results, { glossary_entry_id: card.id, correct }];
    setResults(newResults);
    if (index + 1 < total) {
      setIndex(index + 1);
    } else {
      setFinished(true);
    }
  }

  const wrongEntries = finished
    ? results.filter((r) => !r.correct).map((r) => entries.find((e) => e.id === r.glossary_entry_id)).filter(Boolean) as GlossaryEntry[]
    : [];

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title="Karteikarten" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--text)" }}>Ergebnis</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--accent)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {Math.round((correctCount / total) * 100)}% gewusst
              </p>
            </div>

            {/* Progress bar */}
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }}
              />
            </div>

            {wrongEntries.length > 0 && (
              <div className="w-full rounded-xl p-4" style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}>
                <p className="text-xs font-semibold mb-2" style={{ color: "#B91C1C" }}>
                  <WarningCircle size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-2px" }} />
                  Nochmal lernen:
                </p>
                <div className="flex flex-col gap-1.5">
                  {wrongEntries.map((e) => (
                    <div key={e.id} className="flex items-center gap-2 text-xs" style={{ color: "var(--text)" }}>
                      <span className="font-semibold">{e.term_de}</span>
                      <span style={{ color: "var(--muted)" }}>—</span>
                      <span style={{ color: "var(--muted)" }}>{e.term_en}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-2 w-full">
              {wrongEntries.length > 0 && (
                <button
                  type="button"
                  onClick={() => { setIndex(0); setResults([]); setFinished(false); }}
                  className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                  style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#B91C1C", border: "1px solid rgba(239,68,68,0.2)" }}
                >
                  <ArrowCounterClockwise size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
                  Alle nochmal
                </button>
              )}
              <button
                type="button"
                onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
              >
                Zurück
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Karteikarten" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
      <div className="flex-1 overflow-y-auto p-4">
        <div className="mx-auto mt-6 w-full flex flex-col gap-4" style={{ maxWidth: 560 }}>
          {/* Card */}
          {card && (
            <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: flipped ? "rgba(var(--accent-rgb),0.04)" : "var(--surface)", boxShadow: "0 4px 20px rgba(0,40,60,0.08)" }}>
              {/* Progress bar as top border */}
              <div className="w-full" style={{ height: 3, backgroundColor: "var(--border)" }}>
                <div className="h-full transition-all duration-500 rounded-r-full" style={{ width: `${((index + 1) / total) * 100}%`, backgroundColor: "var(--kb)" }} />
              </div>
            <button
              type="button"
              onClick={() => setFlipped(!flipped)}
              className="w-full p-6 text-center transition-all cursor-pointer"
              style={{
                minHeight: 180,
                backgroundColor: "transparent",
                border: "none",
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 8,
              }}
            >
              {!flipped ? (
                <>
                  <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>{card.term_de}</span>
                  <span className="text-[10px]" style={{ color: "var(--muted)" }}>Tippen zum Umdrehen</span>
                </>
              ) : (
                <>
                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--accent)" }}>
                    {card.term_en}
                  </span>
                  <span className="text-sm leading-relaxed font-semibold" style={{ color: "var(--text)" }}
                    dangerouslySetInnerHTML={{ __html: _md(card.definition) }} />
                  {card.page_number && (
                    <span className="text-xs mt-1" style={{ color: "var(--muted)" }}>{card.filename ? _chunkLabel(card.filename, card.page_number!) : `S. ${card.page_number}`}</span>
                  )}
                </>
              )}
            </button>
            </div>
          )}

          {/* Answer buttons */}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleAnswer(false)}
              className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
              style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#B91C1C", border: "1px solid rgba(239,68,68,0.2)" }}
            >
              <XIcon size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
              Nochmal
            </button>
            <button
              type="button"
              onClick={() => handleAnswer(true)}
              className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
              style={{ backgroundColor: "rgba(34,197,94,0.1)", color: "#166534", border: "1px solid rgba(34,197,94,0.2)" }}
            >
              <Check size={13} weight="bold" className="inline mr-1" style={{ verticalAlign: "-1px" }} />
              Gewusst
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sprachtraining: Lückentext ──────────────────────────────────────────────

function LueckentextView({
  exercises, loading, onGenerate, onBack, breadcrumbs,
}: {
  exercises: ClozeExercise[]; loading: boolean;
  onGenerate: () => void; onBack: () => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [current, setCurrent] = useState(0);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [finished, setFinished] = useState(false);

  const total = exercises.length;
  const ex = exercises[current];

  function handleSelect(optIdx: number) {
    if (answers[current] !== undefined) return;
    setAnswers({ ...answers, [current]: optIdx });
  }

  function handleAdvance() {
    if (current + 1 < total) {
      setCurrent(current + 1);
    } else {
      setFinished(true);
      const finalAnswers = { ...answers };
    }
  }

  const correctCount = Object.entries(answers).filter(
    ([i, optIdx]) => exercises[Number(i)]?.options[optIdx] === exercises[Number(i)]?.answer
  ).length;

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title="Lückentext" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--text)" }}>Ergebnis</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--accent)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {Math.round((correctCount / total) * 100)}% richtig
              </p>
            </div>
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div className="h-full rounded-full" style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }} />
            </div>
            <div className="flex gap-2 w-full">
              <button
                type="button"
                onClick={() => { setCurrent(0); setAnswers({}); setFinished(false); onGenerate(); }}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--accent)" }}
              >
                Neue Übung
              </button>
              <button type="button" onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
              >
                Zurück
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Lückentext" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ maxWidth: 560 }}>
          <button
            type="button"
            onClick={() => { onGenerate(); setCurrent(0); setAnswers({}); setFinished(false); }}
            disabled={loading}
            className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity hover:opacity-90"
            style={{ backgroundColor: "var(--accent)" }}
          >
            <span className="flex items-center justify-center gap-2">
              <TextAa size={16} weight="bold" />
              {loading ? "Generiere…" : "Lückentext starten"}
            </span>
          </button>

          {ex && !loading && (
            <>
              <div className="text-center text-xs font-semibold" style={{ color: "var(--muted)" }}>
                Frage {current + 1} / {total}
              </div>

              <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-sm leading-relaxed font-semibold mb-4" style={{ color: "var(--text)" }}>
                  {ex.sentence}
                </p>
                <div className="flex flex-col gap-2">
                  {ex.options.map((opt, oi) => {
                    const answered = answers[current] !== undefined;
                    const isCorrect = opt === ex.answer;
                    const isSelected = answers[current] === oi;
                    let bg = "var(--bg)";
                    let border = "var(--border)";
                    let color = "var(--text)";
                    if (answered) {
                      if (isCorrect) { bg = "#DCFCE7"; border = "#86EFAC"; color = "#166534"; }
                      else if (isSelected) { bg = "#FEE2E2"; border = "#FCA5A5"; color = "#991B1B"; }
                    }
                    return (
                      <button
                        key={oi}
                        type="button"
                        onClick={() => handleSelect(oi)}
                        disabled={answered}
                        className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold disabled:cursor-default transition-colors"
                        style={{ backgroundColor: bg, border: `1px solid ${border}`, color }}
                      >
                        {["A", "B", "C", "D"][oi]}. {opt}
                      </button>
                    );
                  })}
                </div>
                {answers[current] !== undefined && (
                  <p className="flex items-center gap-1 text-xs mt-3 font-semibold"
                    style={{ color: ex.options[answers[current]] === ex.answer ? "#166534" : "#991B1B" }}
                  >
                    {ex.options[answers[current]] === ex.answer
                      ? <><Check size={12} weight="bold" /> Richtig!</>
                      : <><XIcon size={12} weight="bold" /> Die richtige Antwort ist: {ex.answer}</>}
                  </p>
                )}
                {answers[current] !== undefined && (
                  <button type="button" onClick={handleAdvance}
                    className="mt-2 self-end flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
                    style={{ backgroundColor: "var(--accent)" }}>
                    {current + 1 >= total ? "Abschließen" : "Weiter"} <CaretRight size={12} weight="bold" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Sprachtraining: Vokabeltest ─────────────────────────────────────────────

function VokabeltestView({
  questions, loading, onGenerate, onBack, breadcrumbs,
}: {
  questions: VocabTestQuestion[]; loading: boolean;
  onGenerate: () => void; onBack: () => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [current, setCurrent] = useState(0);
  const [finished, setFinished] = useState(false);

  const total = questions.length;
  const q = questions[current];

  function handleSelect(optIdx: number) {
    if (answers[current] !== undefined) return;
    setAnswers({ ...answers, [current]: optIdx });
  }

  function handleAdvance() {
    if (current + 1 < total) {
      setCurrent(current + 1);
    } else {
      setFinished(true);
      const finalAnswers = { ...answers };
    }
  }

  const correctCount = Object.entries(answers).filter(
    ([i, optIdx]) => questions[Number(i)]?.correct_index === optIdx
  ).length;

  if (finished) {
    return (
      <div className="flex flex-col h-full">
        <SubviewHeader title="Begriffe-Quiz" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full px-4 pt-8 pb-6 flex flex-col items-center gap-5" style={{ maxWidth: 560 }}>
            <div className="text-center">
              <p className="text-lg font-bold" style={{ color: "var(--text)" }}>Ergebnis</p>
              <p className="text-3xl font-bold mt-2" style={{ color: "var(--accent)" }}>
                {correctCount} / {total}
              </p>
              <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
                {Math.round((correctCount / total) * 100)}% richtig
              </p>
            </div>
            <div className="w-full rounded-full h-2.5 overflow-hidden" style={{ backgroundColor: "var(--border)" }}>
              <div className="h-full rounded-full" style={{ width: `${(correctCount / total) * 100}%`, backgroundColor: "#22c55e" }} />
            </div>
            <div className="flex gap-2 w-full">
              <button type="button"
                onClick={() => { setCurrent(0); setAnswers({}); setFinished(false); onGenerate(); }}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--accent)" }}
              >
                Neuer Test
              </button>
              <button type="button" onClick={onBack}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold transition-opacity hover:opacity-90"
                style={{ backgroundColor: "var(--border)", color: "var(--text)" }}
              >
                Zurück
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title="Begriffe-Quiz" onBack={onBack} breadcrumbs={breadcrumbs} category="sprachtraining" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full px-4 pt-4 pb-6 flex flex-col gap-4" style={{ maxWidth: 560 }}>
          <button
            type="button"
            onClick={() => { onGenerate(); setCurrent(0); setAnswers({}); setFinished(false); }}
            disabled={loading}
            className="w-full py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-50 transition-opacity hover:opacity-90"
            style={{ backgroundColor: "var(--accent)" }}
          >
            <span className="flex items-center justify-center gap-2">
              <Exam size={16} weight="bold" />
              {loading ? "Generiere…" : "Begriffe-Quiz starten"}
            </span>
          </button>

          {q && !loading && (
            <>
              <div className="text-center text-xs font-semibold" style={{ color: "var(--muted)" }}>
                Frage {current + 1} / {total}
              </div>

              <div className="rounded-xl p-4" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}>
                <p className="text-sm font-semibold mb-4 leading-snug" style={{ color: "var(--text)" }}>
                  {q.question}
                </p>
                <div className="flex flex-col gap-2">
                  {q.options.map((opt, oi) => {
                    const answered = answers[current] !== undefined;
                    const isCorrect = oi === q.correct_index;
                    const isSelected = answers[current] === oi;
                    let bg = "var(--bg)";
                    let border = "var(--border)";
                    let color = "var(--text)";
                    if (answered) {
                      if (isCorrect) { bg = "#DCFCE7"; border = "#86EFAC"; color = "#166534"; }
                      else if (isSelected && !isCorrect) { bg = "#FEE2E2"; border = "#FCA5A5"; color = "#991B1B"; }
                    }
                    return (
                      <button
                        key={oi}
                        type="button"
                        onClick={() => handleSelect(oi)}
                        disabled={answered}
                        className="w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold disabled:cursor-default transition-colors"
                        style={{ backgroundColor: bg, border: `1px solid ${border}`, color }}
                      >
                        {["A", "B", "C", "D"][oi]}. {opt}
                      </button>
                    );
                  })}
                </div>
                {answers[current] !== undefined && (
                  <button type="button" onClick={handleAdvance}
                    className="mt-2 self-end flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
                    style={{ backgroundColor: "var(--accent)" }}>
                    {current + 1 >= total ? "Abschließen" : "Weiter"} <CaretRight size={12} weight="bold" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}


// ─── Sprachtraining: Overview ────────────────────────────────────────────────

function SprachtrainingOverview({
  activeSourceCount, glossaryCount, onNavigate,
}: {
  activeSourceCount: number;
  glossaryCount: number;
  onNavigate: (view: SprachtrainingView) => void;
}) {
  const noSources = activeSourceCount === 0;

  const tiles = [
    { key: "lk-sets" as const, Icon: BookOpenText, label: "Lernkarten", desc: "Übungen", iconBg: "rgba(245,235,220,0.7)", iconColor: "#78350F" },
    { key: "cl-sets" as const, Icon: TextAa, label: "Lückentext", desc: "Übungen", iconBg: "rgba(254,226,226,0.7)", iconColor: "#B91C1C" },
    { key: "vt-sets" as const, Icon: Exam, label: "Begriffe-Quiz", desc: "Übungen", iconBg: "rgba(237,233,254,0.7)", iconColor: "#534AB7" },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {/* Glossar counter */}
        {glossaryCount > 0 && (
          <span className="text-xs font-medium px-1" style={{ color: "var(--muted)" }}>
            {glossaryCount}/150 Glossar
          </span>
        )}

        {/* Tool tiles */}
        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}>
          {tiles.map((tile) => {
            const disabled = noSources;
            return (
              <button
                key={tile.key}
                type="button"
                onClick={() => !disabled && onNavigate(tile.key)}
                disabled={disabled}
                className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-2xl text-center transition-all hover:brightness-95 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  minHeight: 85,
                  backgroundColor: tile.iconBg,
                  border: `1.5px solid ${tile.iconColor}22`,
                }}
              >
                <tile.Icon size={20} color={tile.iconColor} weight="bold" />
                <span className="text-xs font-semibold leading-tight" style={{ color: tile.iconColor }}>
                  {tile.label}
                </span>
                <span className="text-xs" style={{ color: tile.iconColor, opacity: 0.7 }}>
                  {tile.desc}
                </span>
              </button>
            );
          })}
        </div>


      </div>
    </div>
  );
}

// ─── Stats Bar (reusable across studio sub-views) ───────────────────────────

function MasteryBar({ stats }: { stats: StudentStats | null }) {
  if (!stats) return null;
  const o = stats.lerntools;
  return (
    <div className="px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>
          {o.total_sets} {o.total_sets === 1 ? "Übung" : "Übungen"} · {o.total_cards} Karten
        </span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{o.total_attempts} Antworten</span>
      </div>
    </div>
  );
}

// ─── Lerntools Grid (icon-only when narrow) ──────────────────────────────────

function LerntoolsGrid({ tiles, onSelect }: {
  tiles: { key: string; Icon: React.ComponentType<any>; label: string; iconBg: string; iconColor: string }[];
  onSelect: (key: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 160);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} className="px-3 pb-3 flex-shrink-0">
      <div className="grid gap-2" style={{ gridTemplateColumns: compact ? "repeat(auto-fill, minmax(50px, 1fr))" : "repeat(auto-fill, minmax(120px, 1fr))" }}>
        {tiles.map((tile) => (
          <button
            key={tile.key}
            type="button"
            onClick={() => onSelect(tile.key)}
            className="flex flex-col items-center justify-center gap-2 p-3 rounded-2xl text-center transition-colors hover:brightness-95"
            style={{
              minHeight: compact ? 50 : 90,
              backgroundColor: tile.iconBg,
              border: `1.5px solid ${tile.iconColor}33`,
            }}
            title={tile.label}
          >
            <tile.Icon size={compact ? 18 : 20} color={tile.iconColor} weight="bold" />
            {!compact && (
              <span className="text-xs font-semibold leading-tight" style={{ color: tile.iconColor }}>
                {tile.label}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Tool Label / Color Maps ──────────────────────────────────────────────

const TOOL_LABELS: Record<string, string> = {
  lernkarten: "Lernkarten",
  karteikarten: "Karteikarten",
  lueckentext: "Lückentext",
  vokabeltest: "Begriffe-Quiz",
  quiz: "Quiz",
};

const TOOL_COLORS: Record<string, { bg: string; color: string }> = {
  lernkarten:    { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  karteikarten:  { bg: "rgba(220,252,231,0.7)", color: "#166534" },
  quiz:          { bg: "rgba(254,249,195,0.7)", color: "#A16207" },
  lueckentext:   { bg: "rgba(254,226,226,0.7)", color: "#B91C1C" },
  vokabeltest:   { bg: "rgba(237,233,254,0.7)", color: "#534AB7" },
};

// ─── Recent Activities ────────────────────────────────────────────────────

interface RecentActivity {
  set_id: number;
  tool: string;
  mode: string;
  title: string;
  last_answer: string | null;
  answers: number;
  correct: number;
}

const ACTIVITY_TOOL_ICONS: Record<string, React.ComponentType<any>> = {
  karteikarten: Cards,
  lernkarten: BookOpenText,
  quiz: Question,
  lueckentext: TextAa,
  vokabeltest: Exam,
  datentabelle: Table,
  mindmap: TreeStructure,
};

const ACTIVITY_TOOL_COLORS: Record<string, string> = {
  karteikarten: "#166534",
  lernkarten: "#0E7490",
  quiz: "#A16207",
  lueckentext: "#B91C1C",
  vokabeltest: "#534AB7",
  datentabelle: "#C2410C",
  mindmap: "#0369A1",
};

function RecentActivities({ moduleUuid, onNavigateToSet, refreshKey }: { moduleUuid: string; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; refreshKey?: number }) {
  const [activities, setActivities] = useState<RecentActivity[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`/api/ki-tutor/modules/${moduleUuid}/recent-activities`, { credentials: "include" })
      .then(r => r.ok ? r.json() : [])
      .then(data => setActivities(data))
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [moduleUuid, refreshKey]);

  if (!loaded) return null;

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return "gerade eben";
    if (diffMin < 60) return `vor ${diffMin} Min.`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `vor ${diffH} Std.`;
    const diffD = Math.floor(diffH / 24);
    if (diffD === 1) return "gestern";
    if (diffD < 7) return `vor ${diffD} Tagen`;
    return d.toLocaleDateString("de-DE", { day: "numeric", month: "short" });
  };

  if (activities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 pt-16 pb-8 px-4" style={{ color: "var(--muted)" }}>
        <ClockCounterClockwise size={32} weight="light" />
        <span className="text-xs text-center">Noch keine Aktivitäten.</span>
      </div>
    );
  }

  return (
    <div className="px-3 pb-3">
      <span className="text-[10px] font-semibold uppercase tracking-wider my-2 block" style={{ color: "var(--muted)" }}>
        Letzte Aktivitäten
      </span>
      <div className="flex flex-col gap-1">
        {activities.map((a) => {
          const iconColor = ACTIVITY_TOOL_COLORS[a.tool] ?? "var(--muted)";
          const Icon = ACTIVITY_TOOL_ICONS[a.tool] ?? Cards;
          const displayTitle = a.title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
          return (
            <button
              key={a.set_id}
              type="button"
              onClick={() => onNavigateToSet?.(a.set_id, a.tool, a.mode)}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-xl text-left transition-opacity hover:opacity-70"
              style={{ backgroundColor: "var(--hover)" }}
            >
              <div className="w-7 h-7 flex items-center justify-center flex-shrink-0">
                <Icon size={16} color={iconColor} weight="bold" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium truncate" style={{ color: "var(--text)" }}>
                  {displayTitle}
                </div>
                <div className="text-[10px]" style={{ color: "var(--muted)" }}>
                  {TOOL_LABELS[a.tool] ?? a.tool} · {a.last_answer ? formatTime(a.last_answer) : ""}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Student Stats View ────────────────────────────────────────────────────

type StatsPeriod = "30" | "180";

interface DayDetail {
  day: string;
  sets: { set_id: number; tool: string; mode: string; title: string; answers: number; correct: number; wrong: number; first_answer: string | null; last_answer: string | null }[];
  total_answers: number;
  total_correct: number;
  total_wrong: number;
  chat_count: number;
}

function StudentStatsView({ stats, loading, moduleUuid, onNavigateToSet }: { stats: StudentStats | null; loading: boolean; moduleUuid: string; onNavigateToSet?: (setId: number, tool: string, mode: string) => void }) {
  const [period, setPeriod] = useState<StatsPeriod>("30");
  const [category, setCategory] = useState<"lerntools" | "sprachtraining">("lerntools");

  // ── Lerntools: eigener State ──
  const [selDayLt, setSelDayLt] = useState<HeatmapDay | null>(null);
  const [detailLt, setDetailLt] = useState<DayDetail | null>(null);
  const [loadLt, setLoadLt] = useState(false);

  useEffect(() => {
    if (!stats) return;
    const hasAnyActivity = stats.lerntools_heatmap.some(d => d.answers > 0);
    const entry = hasAnyActivity ? (stats.lerntools_heatmap.find(d => d.day === stats.today) ?? null) : null;
    setSelDayLt(entry);
    setDetailLt(null);
    if (entry && entry.answers > 0) {
      setLoadLt(true);
      fetch(`/api/ki-tutor/modules/${moduleUuid}/stats/day?date=${entry.day}&category=lerntools`, { credentials: "include" })
        .then(r => r.ok ? r.json() : null)
        .then(d => setDetailLt(d))
        .finally(() => setLoadLt(false));
    }
  }, [stats, moduleUuid]);

  // ── Sprachtraining: eigener State ──
  const [selDaySt, setSelDaySt] = useState<HeatmapDay | null>(null);
  const [detailSt, setDetailSt] = useState<DayDetail | null>(null);
  const [loadSt, setLoadSt] = useState(false);

  useEffect(() => {
    if (!stats) return;
    const hasAnyActivity = stats.sprachtraining_heatmap.some(d => d.answers > 0);
    const entry = hasAnyActivity ? (stats.sprachtraining_heatmap.find(d => d.day === stats.today) ?? null) : null;
    setSelDaySt(entry);
    setDetailSt(null);
    if (entry && entry.answers > 0) {
      setLoadSt(true);
      fetch(`/api/ki-tutor/modules/${moduleUuid}/stats/day?date=${entry.day}&category=sprachtraining`, { credentials: "include" })
        .then(r => r.ok ? r.json() : null)
        .then(d => setDetailSt(d))
        .finally(() => setLoadSt(false));
    }
  }, [stats, moduleUuid]);

  // ── Aktive Kategorie ──
  const selectedDay = category === "lerntools" ? selDayLt : selDaySt;
  const dayDetail = category === "lerntools" ? detailLt : detailSt;
  const dayDetailLoading = category === "lerntools" ? loadLt : loadSt;


  if (loading) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-sm" style={{ color: "var(--muted)" }}>Statistik wird geladen…</p>
    </div>
  );
  if (!stats) return (
    <div className="flex-1 flex items-center justify-center p-4">
      <p className="text-sm" style={{ color: "var(--muted)" }}>Noch keine Daten vorhanden. Starte Übungen, um deine Statistik zu sehen.</p>
    </div>
  );

  const { lerntools, sprachtraining, lerntools_heatmap, sprachtraining_heatmap, chat, active_days, today } = stats;
  const currentOverview = category === "lerntools" ? lerntools : sprachtraining;
  const categoryHeatmap = category === "lerntools" ? lerntools_heatmap : sprachtraining_heatmap;

  // Filter heatmap by period
  const periodDays = parseInt(period);
  const filteredHeatmap = categoryHeatmap.slice(-periodDays);
  const periodAnswers = filteredHeatmap.reduce((s, d) => s + d.answers, 0);
  const periodCorrect = filteredHeatmap.reduce((s, d) => s + d.correct, 0);
  const periodWrong = filteredHeatmap.reduce((s, d) => s + d.wrong, 0);
  const periodActiveDays = filteredHeatmap.filter(d => d.answers > 0).length;
  const periodAccuracy = periodAnswers > 0 ? Math.round(periodCorrect / periodAnswers * 100) : 0;

  // Heatmap rendering: weeks as columns, days as rows (Mon-Sun)
  const heatmapWeeks: HeatmapDay[][] = [];
  let currentWeek: HeatmapDay[] = [];
  for (const d of filteredHeatmap) {
    const dow = new Date(d.day + "T12:00:00+02:00").getDay(); // 0=Sun
    const mondayIdx = dow === 0 ? 6 : dow - 1; // 0=Mon
    if (mondayIdx === 0 && currentWeek.length > 0) {
      heatmapWeeks.push(currentWeek);
      currentWeek = [];
    }
    currentWeek.push(d);
  }
  if (currentWeek.length > 0) heatmapWeeks.push(currentWeek);

  const maxAns = Math.max(...filteredHeatmap.map(d => d.answers), 1);

  // Lerntools: brand blue, Sprachtraining: green
  const accent = category === "lerntools" ? "var(--kb)" : "#9333EA";
  const heatRgb = category === "lerntools" ? "0,66,97" : "147,51,234";

  function heatColor(answers: number): string {
    if (answers === 0) return `rgba(${heatRgb},0.07)`;
    const intensity = Math.min(answers / maxAns, 1);
    if (intensity < 0.25) return `rgba(${heatRgb},0.20)`;
    if (intensity < 0.5) return `rgba(${heatRgb},0.40)`;
    if (intensity < 0.75) return `rgba(${heatRgb},0.60)`;
    return `rgba(${heatRgb},0.85)`;
  }

  function formatDay(dayStr: string) {
    const d = new Date(dayStr + "T12:00:00+02:00");
    return d.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", timeZone: "Europe/Berlin" });
  }

  function formatTime(iso: string | null) {
    if (!iso) return "";
    const d = new Date(iso);
    return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
  }

  async function selectDay(d: HeatmapDay) {
    const setDay = category === "lerntools" ? setSelDayLt : setSelDaySt;
    const setDetail = category === "lerntools" ? setDetailLt : setDetailSt;
    const setLoad = category === "lerntools" ? setLoadLt : setLoadSt;
    if (selectedDay?.day === d.day) { setDay(null); setDetail(null); return; }
    setDay(d);
    setDetail(null);
    if (d.answers > 0) {
      setLoad(true);
      try {
        const res = await fetch(`/api/ki-tutor/modules/${moduleUuid}/stats/day?date=${d.day}&category=${category}`, { credentials: "include" });
        if (res.ok) setDetail(await res.json());
      } catch { /* ignore */ }
      setLoad(false);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
      {/* ── Category filter ── */}
      <StudioTabs
        tabs={[
          { key: "lerntools", label: "Lerntools" },
          { key: "sprachtraining", label: "Fachsprachentraining" },
        ]}
        active={category}
        onSelect={(k) => setCategory(k as "lerntools" | "sprachtraining")}
        accentColor={category === "sprachtraining" ? "#9333EA" : undefined}
      />

      {/* ── Period selector + period summary ── */}
      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-semibold" style={{ color: "var(--text)" }}>Aktivität</h3>
          <div className="flex gap-1">
            {([["30", "30 Tage"], ["180", "6 Monate"]] as [StatsPeriod, string][]).map(([val, label]) => (
              <button
                key={val}
                type="button"
                onClick={() => setPeriod(val)}
                className="px-2 py-0.5 rounded text-xs font-medium transition-colors"
                style={{
                  backgroundColor: period === val ? accent : "transparent",
                  color: period === val ? "#fff" : "var(--muted)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {periodAnswers === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-8" style={{ color: "var(--muted)" }}>
            <ChartBar size={32} weight="light" />
            <span className="text-xs text-center">Noch keine Aktivitäten in diesem Zeitraum.</span>
          </div>
        ) : (
        <>
        {/* Period summary line */}
        <div className="flex gap-3 mb-2 text-xs" style={{ color: "var(--muted)" }}>
          <span>{periodActiveDays} aktive Tage</span>
          <span>{periodAnswers} Antworten</span>
          {periodAnswers > 0 && <span>{periodAccuracy}% richtig</span>}
        </div>

        {/* ── Heatmap ── */}
        {(() => {
          const cellSize = 32;
          const gap = 4;
          const showDayNums = true;
          // Build month labels with correct column spans
          const monthLabels: { label: string; colSpan: number }[] = [];
          let prevMonth = -1;
          for (const week of heatmapWeeks) {
            const d = new Date(week[0].day + "T12:00:00+02:00");
            const m = d.getMonth();
            if (m !== prevMonth) {
              monthLabels.push({ label: d.toLocaleDateString("de-DE", { month: "short", timeZone: "Europe/Berlin" }), colSpan: 1 });
              prevMonth = m;
            } else {
              monthLabels[monthLabels.length - 1].colSpan++;
            }
          }
          return (
            <div className="overflow-x-auto p-1">
              <div className="flex mx-auto" style={{ width: "fit-content" }}>
              {/* Row labels — fixed */}
              <div className="flex flex-col flex-shrink-0 mr-2" style={{ paddingTop: cellSize + gap + 2 }}>
                  {["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"].map(d => (
                    <div key={d} className="flex items-center justify-end text-[10px] font-medium" style={{ height: cellSize, marginBottom: gap, color: "var(--muted)" }}>{d}</div>
                  ))}
                </div>
                {/* Grid with month headers */}
                <div>
                  {/* Month labels */}
                  <div className="flex" style={{ marginBottom: gap, width: "fit-content" }}>
                    {monthLabels.map((m, i) => (
                      <div key={i} className="text-[10px] font-medium" style={{
                        width: m.colSpan * (cellSize + gap) - gap,
                        marginRight: gap,
                        color: "var(--muted)",
                        height: cellSize,
                        display: "flex",
                        alignItems: "center",
                      }}>{m.label}</div>
                    ))}
                  </div>
                  {/* Cells */}
                  <div className="flex" style={{ gap, width: "fit-content" }}>
                    {heatmapWeeks.map((week, wi) => (
                      <div key={wi} className="flex flex-col" style={{ gap }}>
                        {week.map(d => {
                          const isSelected = selectedDay?.day === d.day;
                          const dateObj = new Date(d.day + "T12:00:00+02:00");
                          const dayNum = dateObj.getDate();
                          const isToday = d.day === today;
                          return (
                            <button
                              key={d.day}
                              type="button"
                              onClick={() => selectDay(d)}
                              className="rounded-[4px] transition-all flex items-center justify-center"
                              style={{
                                width: cellSize,
                                height: cellSize,
                                backgroundColor: heatColor(d.answers),
                                outline: isSelected ? `2px solid ${accent}` : "none",
                                outlineOffset: 1,
                                borderBottom: isToday && !isSelected ? `2.5px solid ${category === "sprachtraining" ? "#C084FC" : "var(--muted)"}` : "none",
                              }}
                              title={`${formatDay(d.day)}: ${d.answers} Antworten`}
                            >
                              {showDayNums && <span className="text-[10px] font-medium" style={{ color: d.answers > 0 ? `rgba(255,255,255,${Math.min(0.5 + (d.answers / maxAns) * 0.5, 1)})` : "var(--muted)" }}>{dayNum}</span>}
                            </button>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* Legend */}
        <div className="flex items-center justify-center gap-2 mt-2">
          <span className="text-[10px]" style={{ color: "var(--muted)" }}>Weniger</span>
          {[0, 0.25, 0.5, 0.75, 1].map((v, i) => (
            <div key={i} className="rounded-[3px]" style={{ width: 14, height: 14, backgroundColor: v === 0 ? `rgba(${heatRgb},0.07)` : `rgba(${heatRgb},${0.15 + v * 0.70})` }} />
          ))}
          <span className="text-[10px]" style={{ color: "var(--muted)" }}>Mehr</span>
        </div>
        </>
        )}
      </div>

      {/* ── Selected day detail ── */}
      {selectedDay && (
        <div className="rounded-xl p-3">
          <div className="mb-2">
            <div className="text-xs font-semibold" style={{ color: "var(--text)" }}>
              {formatDay(selectedDay.day)} {selectedDay.day === today && "(Heute)"}
            </div>
          </div>
          {selectedDay.answers === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-4" style={{ color: "var(--muted)" }}>
              <ClockCounterClockwise size={24} weight="light" />
              <span className="text-xs text-center">Keine Aktivität an diesem Tag.</span>
            </div>
          ) : dayDetailLoading ? (
            <p className="text-xs" style={{ color: "var(--muted)" }}>Wird geladen…</p>
          ) : dayDetail ? (
            <div className="space-y-2">
              {/* Per-set breakdown */}
              {dayDetail.sets.map(s => {
                const pct = s.answers > 0 ? Math.round(s.correct / s.answers * 100) : 0;
                // Clean title: remove file extensions for display
                const displayTitle = s.title.replace(/\.(pdf|mp4|mp3|webm|wav|m4a|ogg)$/i, "");
                return (
                  <div key={s.set_id} className="rounded-lg px-2.5 py-2 cursor-pointer transition-colors hover:brightness-95" style={{ backgroundColor: "var(--surface)" }} onClick={() => onNavigateToSet?.(s.set_id, s.tool, s.mode)}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium truncate" style={{ color: "var(--text)", maxWidth: "70%" }}>
                        {displayTitle}
                      </span>
                      <span className="text-xs font-semibold" style={{ color: pct >= 70 ? accent : "var(--muted)" }}>
                        {pct}%
                      </span>
                    </div>
                    {/* Mini progress bar */}
                    <div className="flex rounded-full overflow-hidden" style={{ height: 4, backgroundColor: "var(--border)" }}>
                      <div style={{ width: `${pct}%`, backgroundColor: accent }} />
                      {s.wrong > 0 && <div style={{ width: `${100 - pct}%`, backgroundColor: "var(--border)" }} />}
                    </div>
                    <div className="flex items-center justify-between mt-1 text-[9px]" style={{ color: "var(--muted)" }}>
                      <span className="px-1 py-0.5 rounded" style={{
                        backgroundColor: (TOOL_COLORS[s.tool] || { bg: "var(--surface)" }).bg,
                        color: (TOOL_COLORS[s.tool] || { color: "var(--muted)" }).color,
                      }}>
                        {TOOL_LABELS[s.tool] || s.tool}
                      </span>
                      <span>{s.correct}/{s.correct + s.wrong} richtig</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      )}


    </div>
  );
}

// ─── Studio Tabs (container-width responsive) ───────────────────────────────

function StudioTabs({ tabs, active, onSelect, accentColor }: {
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
  accentColor?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<"row" | "grid" | "stack">("row");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      if (w >= tabs.length * 90) setLayout("row");
      else if (w >= 160) setLayout("grid");
      else setLayout("stack");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [tabs.length]);

  const cols = layout === "row" ? tabs.map(t => t.key === "sprachtraining" ? "1.4fr" : "1fr").join(" ") : layout === "grid" ? "repeat(2, 1fr)" : "1fr";

  return (
    <div ref={ref} className="flex-shrink-0 px-3 pt-6 pb-2 w-full mx-auto" style={{ maxWidth: 500 }}>
      <div
        className="grid gap-1 p-1 rounded-xl"
        style={{ backgroundColor: "rgba(var(--accent-rgb), 0.08)", gridTemplateColumns: cols }}
      >
        {tabs.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onSelect(tab.key)}
              className={`py-1.5 px-3 text-xs font-medium rounded-lg transition-all overflow-hidden text-ellipsis whitespace-nowrap ${!isActive ? "hover:bg-black/[0.03] hover:text-[var(--text)]" : ""}`}
              style={{
                color: isActive ? (accentColor || "var(--accent)") : "var(--muted)",
                backgroundColor: isActive ? "var(--bg)" : undefined,
                border: "none",
                boxShadow: isActive ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Studio Overview ──────────────────────────────────────────────────────────

function StudioOverview({ onSelect, onMinimize, sprachtrainingActive, sprachtrainingContent, glossarContent, notizenContent, moduleUuid, statsVersion, onNavigateToSet, onSprachNavigate, activeSourceCount, sprachView }: { onSelect: (v: StudioView) => void; onMinimize: () => void; sprachtrainingActive: boolean; sprachtrainingContent?: React.ReactNode; glossarContent?: React.ReactNode; notizenContent?: React.ReactNode; moduleUuid: string; statsVersion: number; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; onSprachNavigate?: (view: SprachtrainingView) => void; activeSourceCount?: number; sprachView?: string }) {
  const [studioTab, _setStudioTab] = useState<"tools" | "sprachtraining" | "glossar" | "notizen" | "statistik">(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("kis-studio-tab");
      if (saved && ["tools", "glossar", "notizen", "statistik"].includes(saved)) return saved as any;
    }
    return "tools";
  });
  const setStudioTab = (tab: typeof studioTab) => { _setStudioTab(tab); sessionStorage.setItem("kis-studio-tab", tab); };

  const [studentStats, setStudentStats] = useState<StudentStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const refreshStats = useCallback(() => {
    setStatsLoading(true);
    fetch(`/api/ki-tutor/modules/${moduleUuid}/stats`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setStudentStats(data); })
      .catch(() => {})
      .finally(() => setStatsLoading(false));
  }, [moduleUuid]);

  useEffect(() => {
    if (studioTab === "statistik") refreshStats();
  }, [studioTab, moduleUuid, refreshStats, statsVersion]);

  const lerntoolsTiles = [
    { key: "karteikarten" as const, Icon: Cards, label: "Karteikarten", iconBg: "rgba(220,252,231,0.7)", iconColor: "#166534" },
    { key: "quiz" as const, Icon: Question, label: "Quiz", iconBg: "rgba(254,249,195,0.7)", iconColor: "#A16207" },
    { key: "datentabelle" as const, Icon: Table, label: "Datentabelle", iconBg: "rgba(255,237,213,0.7)", iconColor: "#C2410C" },
    { key: "mindmap" as const, Icon: TreeStructure, label: "Mindmap", iconBg: "rgba(236,254,255,0.7)", iconColor: "#0E7490" },
  ];

  const sprachTiles = [
    { key: "lk-sets" as const, Icon: BookOpenText, label: "Lernkarten", iconBg: "rgba(245,235,220,0.7)", iconColor: "#78350F" },
    { key: "cl-sets" as const, Icon: TextAa, label: "Lückentext", iconBg: "rgba(254,226,226,0.7)", iconColor: "#B91C1C" },
    { key: "vt-sets" as const, Icon: Exam, label: "Begriffe-Quiz", iconBg: "rgba(237,233,254,0.7)", iconColor: "#534AB7" },
  ];

  const noSources = (activeSourceCount ?? 0) === 0;

  // When sprachView goes back to "overview", return to tools tab
  useEffect(() => {
    if (studioTab === "sprachtraining" && (!sprachView || sprachView === "overview")) {
      setStudioTab("tools");
    }
  }, [sprachView, studioTab]); // eslint-disable-line react-hooks/exhaustive-deps

  const effectiveTab = studioTab;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      {effectiveTab === "statistik" ? (
        <SubviewHeader title="Statistik" onBack={() => setStudioTab("tools")} breadcrumbs={[{ label: "Studio", onClick: () => setStudioTab("tools") }]} />
      ) : (
        <>
          <div
            className="flex items-center justify-between px-4 py-3 flex-shrink-0"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Studio</span>
            <button
              type="button"
              onClick={onMinimize}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              title="Panel minimieren"
            >
              <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
            </button>
          </div>

          {/* Tabs */}
          <StudioTabs
            tabs={[
              { key: "tools" as const, label: "Tools" },
              { key: "glossar" as const, label: "Glossar" },
              { key: "notizen" as const, label: "Notizen" },
              { key: "statistik" as const, label: "Statistik" },
            ]}
            active={effectiveTab === "sprachtraining" ? "tools" : effectiveTab}
            onSelect={(k) => setStudioTab(k as typeof studioTab)}
          />
        </>
      )}

      {/* Tools: Lerntools + Sprachtraining + Activities */}
      {studioTab === "tools" && (
        <div className="flex-1 overflow-y-auto flex flex-col">
          <div className="px-3 pt-3 pb-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>Lerntools</span>
          </div>
          <LerntoolsGrid tiles={lerntoolsTiles} onSelect={(key) => onSelect(key as StudioView)} />

          {sprachtrainingActive && (
            <>
              <div className="px-3 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "#9333EA" }}>Fachsprachentraining</span>
              </div>
              <LerntoolsGrid tiles={sprachTiles} onSelect={(key) => {
                if (!noSources && onSprachNavigate) {
                  onSprachNavigate(key as SprachtrainingView);
                  setStudioTab("sprachtraining");
                }
              }} />
            </>
          )}

          <RecentActivities moduleUuid={moduleUuid} onNavigateToSet={onNavigateToSet} refreshKey={statsVersion} />
        </div>
      )}

      {/* Sprachtraining Inhalt */}
      {studioTab === "sprachtraining" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {sprachtrainingContent}
        </div>
      )}

      {/* Glossar Inhalt */}
      {studioTab === "glossar" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {glossarContent}
        </div>
      )}

      {/* Notizen Inhalt */}
      {studioTab === "notizen" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          {notizenContent}
        </div>
      )}

      {/* Ergebnisse Inhalt */}
      {studioTab === "statistik" && (
        <StudentStatsView stats={studentStats} loading={statsLoading} moduleUuid={moduleUuid} onNavigateToSet={onNavigateToSet} />
      )}
    </div>
  );
}



// ─── Mini Panel Strip ─��────────────────────────────────────────────────────────

function MiniStrip({ label, onClick, side }: { label: string; onClick: () => void; side: "left" | "right" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center pt-4 h-full w-full gap-2 hover:opacity-70 transition-opacity"
      style={{ color: "var(--muted)" }}
      title={label}
    >
      <span
        className="w-7 h-7 flex items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
      >
        <SidebarSimple
          size={13}
          style={{ transform: side === "right" ? "scaleX(-1)" : "none", flexShrink: 0 }}
        />
      </span>
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
  const searchParams = useSearchParams();
  const uuid = params.uuid as string;
  const enrollmentId = searchParams.get("eid") ? Number(searchParams.get("eid")) : null;
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

  const MIN_PANEL = 50;
  const MOBILE_BREAKPOINT = 768;

  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [prevSelectedSourceIds, setPrevSelectedSourceIds] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  // Persist selected sources to sessionStorage
  useEffect(() => {
    if (selectedSourceIds.length > 0) {
      sessionStorage.setItem(`kis-selected-sources-${uuid}`, JSON.stringify(selectedSourceIds));
    }
  }, [selectedSourceIds, uuid]);

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatTextareaRef = useRef<HTMLTextAreaElement>(null);

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
  const [studioEnabled, setStudioEnabled] = useState(true);
  const [sprachtrainingActive, setSprachtrainingActive] = useState(false);

  const [popupActions, setPopupActions] = useState<{ key: string; label: string; icon: string; prompt: string; min_words: number }[]>([]);

  const [studioView, setStudioView] = useState<StudioView>("overview");
  const [lernkarten, setLernkarten] = useState<LernKarte[]>([]);
  const [lernkartenLoading, setLernkartenLoading] = useState(false);
  const [mindmapData, setMindmapData] = useState<MindmapNodeData | null>(null);
  const [mindmapLoading, setMindmapLoading] = useState(false);
  const [mindmapList, setMindmapList] = useState<{ id: number; created_at: string | null; topic: string }[]>([]);
  const [datentabelle, setDatentabelle] = useState<DatentabelleData | null>(null);
  const [datentabelleSources, setDatentabelleSources] = useState<DatentabelleSource[]>([]);
  const [datentabelleLoading, setDatentabelleLoading] = useState(false);
  const [datentabelleList, setDatentabelleList] = useState<{ id: number; title: string; created_at: string | null }[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);

  // ─── Sprachtraining State ─────────────────────────────────────────────────
  const [sprachView, setSprachView] = useState<SprachtrainingView>("overview");
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [glossaryLoading, setGlossaryLoading] = useState(false);
  const [clozeExercises, setClozeExercises] = useState<ClozeExercise[]>([]);
  const [clozeLoading, setClozeLoading] = useState(false);
  const [vocabQuestions, setVocabQuestions] = useState<VocabTestQuestion[]>([]);
  const [vocabLoading, setVocabLoading] = useState(false);
  const [sprachSourceUuid, setSprachSourceUuid] = useState("");

  // ─── Exercise Sets State ─────────────────────────────────────────────────
  const [exerciseSets, setExerciseSets] = useState<ExerciseSet[]>([]);
  const [activeSet, setActiveSet] = useState<ExerciseSet | null>(null);
  const [setCreating, setSetCreating] = useState(false);
  const [createSetTool, setCreateSetTool] = useState<string>("lernkarten");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [streakInfo, setStreakInfo] = useState<StreakInfo>({ current_streak: 0, max_streak: 0, last_active_date: null });
  const [statsVersion, setStatsVersion] = useState(0);
  const [pageStats, setPageStats] = useState<StudentStats | null>(null);
  const [glossaryCount, setGlossaryCount] = useState(0);

  // ─── Init ──────────────────────────────────────────────────────────────────

  const loadMessages = useCallback(async () => {
    try {
      const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : "";
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/messages${eidParam}`, { credentials: "include" });
      if (res.ok) setMessages(await res.json());
    } catch { /* ignore */ }
  }, [uuid, enrollmentId]);

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
        // Restore selected sources from sessionStorage, fallback to all ready
        const storageKey = `kis-selected-sources-${uuid}`;
        const saved = sessionStorage.getItem(storageKey);
        if (saved) {
          try {
            const savedIds: string[] = JSON.parse(saved);
            const validIds = savedIds.filter((id) => srcs.some((s) => s.uuid === id && s.status === "ready"));
            setSelectedSourceIds(validIds.length > 0 ? validIds : srcs.filter((s) => s.status === "ready").map((s) => s.uuid));
          } catch { setSelectedSourceIds(srcs.filter((s) => s.status === "ready").map((s) => s.uuid)); }
        } else {
          setSelectedSourceIds(srcs.filter((s) => s.status === "ready").map((s) => s.uuid));
        }

        await loadMessages();

        const settingsRes = await fetch(`/api/ki-tutor/modules/${uuid}/settings`, { credentials: "include" });
        if (!cancelled && settingsRes.ok) {
          const s = await settingsRes.json();
          setChatLang(s.chat_lang ?? "de");
          setStudioEnabled(s.studio_enabled ?? true);
          setSprachtrainingActive(s.sprachtraining_active ?? false);
        }

        const actionsRes = await fetch("/api/ki-tutor/popup-actions", { credentials: "include" });
        if (!cancelled && actionsRes.ok) {
          const d = await actionsRes.json();
          setPopupActions(d.actions ?? []);
        }

        const notesRes = await fetch(`/api/ki-tutor/modules/${uuid}/notes`, { credentials: "include" });
        if (!cancelled && notesRes.ok) setNotes(await notesRes.json());

        if (!cancelled) setInitialized(true);
      } catch {
        if (!cancelled) router.push("/ki-tutor");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [uuid, router, loadMessages]);

  // Fetch stats at page level so sub-views can show mastery bar
  const refreshPageStats = useCallback(() => {
    fetch(`/api/ki-tutor/modules/${uuid}/stats`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setPageStats(data); })
      .catch(() => {});
  }, [uuid]);

  useEffect(() => {
    if (initialized) refreshPageStats();
  }, [initialized, refreshPageStats, statsVersion]);

  // Reset mobile tab if studio is disabled
  useEffect(() => {
    if (!studioEnabled && activeTab === "studio") setActiveTab("chat");
  }, [studioEnabled, activeTab]);

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
      body: JSON.stringify({ chat_lang: chatLang, studio_enabled: studioEnabled, sprachtraining_active: sprachtrainingActive }),
    }).catch(() => { /* ignore */ });
  }, [chatLang, studioEnabled, sprachtrainingActive, initialized, uuid]);

  useEffect(() => {
    const pendingIds = sources.filter((s) => s.status === "indexing" || s.status === "pending").map((s) => s.uuid);
    if (pendingIds.length === 0) return;
    const id = setInterval(async () => {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}`, { credentials: "include" });
      if (!res.ok) return;
      const mod: ModuleDetail = await res.json();
      const srcs: Source[] = mod.sources ?? [];
      setSources(srcs);
      setModuleDetail(mod);
      // Only auto-select sources that just transitioned from pending/indexing → ready
      setSelectedSourceIds((prev) => {
        const justBecameReady = srcs.filter((s) => s.status === "ready" && pendingIds.includes(s.uuid) && !prev.includes(s.uuid)).map((s) => s.uuid);
        return justBecameReady.length > 0 ? [...prev, ...justBecameReady] : prev;
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

  function handleOpenViewer(source: Source, page = 1, highlightText?: string) {
    setPrevSelectedSourceIds(selectedSourceIds);
    setSelectedSourceIds([source.uuid]);
    setViewerSource({ uuid: source.uuid, filename: source.filename, page, highlightText, nonce: Date.now() });
    setPanels((prev) => ({ ...prev, quellen: true }));
  }

  function handleCloseViewer() {
    setSelectedSourceIds(prevSelectedSourceIds);
    setViewerSource(null);
  }

  async function handleDeleteSource(srcUuid: string) {
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

  async function sendChatMessage(content: string, directText = false, sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string }) {
    // Strip leftover citation markers from pasted AI text
    content = content.replace(/\s*\[(?:Q\d+,\s*)?S\.\s*\d+\]/g, "");
    const effectiveSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;
    if (!content.trim()) return;
    if (!directText && effectiveSourceIds.length === 0) return;
    const msgSourceCount = directText ? 1 : effectiveSourceIds.length;
    setMessages((prev) => [...prev, { role: "user", content: content.trim(), sourceCount: msgSourceCount }]);
    setChatInput("");
    setChatLoading(true);
    // Add placeholder assistant message for streaming
    setMessages((prev) => [...prev, { role: "assistant", content: "", sourceCount: msgSourceCount }]);

    const updateLast = (patch: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) updated[updated.length - 1] = { ...last, ...patch };
        return updated;
      });

    try {
      const res = await fetch(`/api/ki-tutor-stream/${uuid}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: content.trim(),
          active_source_ids: directText ? [] : effectiveSourceIds,
          direct_text: directText,
          ...(enrollmentId && { enrollment_id: enrollmentId }),
          ...(sourceInfo && {
            source_uuid: sourceInfo.uuid,
            source_filename: sourceInfo.filename,
            source_page: sourceInfo.page,
            source_text: sourceInfo.selectedText,
          }),
        }),
      });
      if (res.ok && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        // Batch token updates at screen refresh rate for smooth rendering
        let pendingTokens = "";
        let rafId: number | null = null;
        const flushTokens = () => {
          if (!pendingTokens) return;
          const chunk = pendingTokens;
          pendingTokens = "";
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            if (last) updated[updated.length - 1] = { ...last, content: last.content + chunk };
            return updated;
          });
        };

        const processLine = (line: string) => {
          if (!line.startsWith("data: ")) return;
          try {
            const evt = JSON.parse(line.slice(6));
            if (evt.token) {
              pendingTokens += evt.token;
              if (rafId == null) {
                rafId = requestAnimationFrame(() => { flushTokens(); rafId = null; });
              }
            } else if (evt.done) {
              // Flush remaining tokens before applying metadata
              if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
              flushTokens();
              updateLast({ source_pages: evt.source_pages, source_qmap: evt.source_qmap });
            } else if (evt.error) {
              updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
            }
          } catch { /* skip malformed lines */ }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) processLine(line);
        }
        // Process remaining buffer (e.g. the done event)
        if (buffer.trim()) processLine(buffer);
        // Final flush of any remaining tokens
        if (rafId != null) { cancelAnimationFrame(rafId); rafId = null; }
        flushTokens();
      } else if (res.status === 409) {
        updateLast({ content: "Das Modul wird noch indiziert. Bitte warte einen Moment und versuche es erneut." });
      } else {
        updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
      }
    } catch {
      updateLast({ content: "Es ist ein Fehler aufgetreten. Bitte versuche es erneut." });
    } finally {
      setChatLoading(false);
    }
  }

  function handleAskWithSelection(prompt: string, sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string }) {
    if (isMobile) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    sendChatMessage(prompt, true, sourceInfo);
  }

  // ─── Glossary Extract State ──────────────────────────────────────────────
  const [glossaryExtracting, setGlossaryExtracting] = useState(false);

  async function handleAddToGlossary(text: string, sourceUuid: string, page: number) {
    // Navigate to Glossar view and show extracting state
    setSprachView("glossar");
    setSprachtrainingActive(true);
    setGlossaryExtracting(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/glossary/extract`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_uuid: sourceUuid, page_number: page }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.added > 0) {
          loadGlossary();
          loadGlossaryCount();
        }
      }
    } catch { /* ignore */ } finally {
      setGlossaryExtracting(false);
    }
  }

  function handleCustomQuestion(selectedText: string) {
    if (isMobile) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    setChatInput(`"${selectedText}"\n\n`);
    // Focus textarea after React renders the new input
    setTimeout(() => chatTextareaRef.current?.focus(), 50);
  }

  function handlePillClick(sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) {
    const src = sources.find((s) => s.uuid === sourceUuid);
    const isMedia = _isMediaFile(filename);
    if (isMedia) {
      setViewerSource({ uuid: sourceUuid, filename, page: 0, startTime, nonce: Date.now() });
      setPanels((prev) => ({ ...prev, quellen: true }));
    } else if (src) {
      handleOpenViewer(src, page, sourceText);
    } else {
      setPrevSelectedSourceIds(selectedSourceIds);
      setSelectedSourceIds([sourceUuid]);
      setViewerSource({ uuid: sourceUuid, filename, page, highlightText: sourceText, nonce: Date.now() });
      setPanels((prev) => ({ ...prev, quellen: true }));
    }
  }

  // ─── Studio ────────────────────────────────────────────────────────────────

  async function generateLernkarten() {
    setLernkartenLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/lernkarten/generate`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          active_source_ids: selectedSourceIds,
          count: 10,
        }),
      });
      if (res.ok) {
        // Now creates an exercise set — switch to sprachtraining view
        loadExerciseSets("lernkarten");
        setSprachtrainingActive(true);
        setSprachView("lk-sets");
      }
    } catch { /* ignore */ } finally {
      setLernkartenLoading(false);
    }
  }

  const mindmapPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopMindmapPolling() {
    if (mindmapPollRef.current) { clearInterval(mindmapPollRef.current); mindmapPollRef.current = null; }
  }

  async function refreshMindmapList() {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/mindmaps`, { credentials: "include" });
      if (res.ok) setMindmapList(await res.json());
    } catch { /* ignore */ }
  }

  function startMindmapPolling(mindmapId: number) {
    stopMindmapPolling();
    setMindmapLoading(true);
    mindmapPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ki-tutor/modules/${uuid}/mindmap/${mindmapId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.mindmap) {
          setMindmapData(data.mindmap);

          setMindmapLoading(false);
          stopMindmapPolling();
          refreshMindmapList();
        } else if (data.status === "failed") {
          console.error("Mindmap failed:", data.error);
          setMindmapLoading(false);
          stopMindmapPolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }

  // Load existing mindmap on mount + resume polling if pending/running
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ki-tutor/modules/${uuid}/mindmap`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.mindmap) {
          setMindmapData(data.mindmap);
        } else if (data.id && (data.status === "pending" || data.status === "running")) {
          startMindmapPolling(data.id);
        }
      } catch { /* ignore */ }
    })();
    refreshMindmapList();
    return () => stopMindmapPolling();
  }, [uuid]); // eslint-disable-line react-hooks/exhaustive-deps

  async function generateMindmap() {
    if (selectedSourceIds.length === 0) return;
    setMindmapLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/mindmap/generate`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds.slice(0, 5) }),
      });
      if (res.ok) {
        const data = await res.json();
        startMindmapPolling(data.mindmap_id);
      } else {
        const err = await res.text();
        console.error("Mindmap generate error:", res.status, err);
        setMindmapLoading(false);
      }
    } catch {
      setMindmapLoading(false);
    }
  }

  async function selectMindmap(id: number) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/mindmap/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.mindmap) {
        setMindmapData(data.mindmap);
      }
    } catch { /* ignore */ }
  }

  async function deleteMindmap(id: number) {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/mindmap/${id}`, { method: "DELETE", credentials: "include" });
      setMindmapList((prev) => prev.filter((m) => m.id !== id));
    } catch { /* ignore */ }
  }

  // ─── Datentabelle Functions ──────────────────────────────────────────────

  const datentabellePollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopDatentabellePolling() {
    if (datentabellePollRef.current) { clearInterval(datentabellePollRef.current); datentabellePollRef.current = null; }
  }

  async function refreshDatentabelleList() {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/datentabellen`, { credentials: "include" });
      if (res.ok) setDatentabelleList(await res.json());
    } catch { /* ignore */ }
  }

  function startDatentabellePolling(dtId: number) {
    stopDatentabellePolling();
    setDatentabelleLoading(true);
    datentabellePollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ki-tutor/modules/${uuid}/datentabelle/${dtId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.table_data) {
          setDatentabelle(data.table_data);
          setDatentabelleSources(data.table_data.sources || []);
          setDatentabelleLoading(false);
          stopDatentabellePolling();
          refreshDatentabelleList();
        } else if (data.status === "failed") {
          console.error("Datentabelle failed:", data.error);
          setDatentabelleLoading(false);
          stopDatentabellePolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ki-tutor/modules/${uuid}/datentabelle`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === "success" && data.table_data) {
            setDatentabelle(data.table_data);
            setDatentabelleSources(data.table_data.sources || []);
          } else if (data && (data.status === "pending" || data.status === "running")) {
            startDatentabellePolling(data.id);
          }
        }
      } catch { /* ignore */ }
    })();
    refreshDatentabelleList();
    return () => stopDatentabellePolling();
  }, [uuid]); // eslint-disable-line react-hooks/exhaustive-deps

  async function generateDatentabelle() {
    if (selectedSourceIds.length === 0) return;
    setDatentabelleLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/datentabelle/generate`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds.slice(0, 5) }),
      });
      if (res.ok) {
        const data = await res.json();
        startDatentabellePolling(data.datentabelle_id);
      } else {
        console.error("Datentabelle generate error:", res.status);
        setDatentabelleLoading(false);
      }
    } catch {
      setDatentabelleLoading(false);
    }
  }

  async function selectDatentabelle(id: number) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/datentabelle/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.table_data) {
        setDatentabelle(data.table_data);
        setDatentabelleSources(data.table_data.sources || []);
      }
    } catch { /* ignore */ }
  }

  async function deleteDatentabelle(id: number) {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/datentabelle/${id}`, { method: "DELETE", credentials: "include" });
      setDatentabelleList((prev) => prev.filter((d) => d.id !== id));
    } catch { /* ignore */ }
  }

  // ─── Sprachtraining Functions ────────────────────────────────────────────

  // Active sources for sprachtraining (max 3, from left panel checkboxes)
  const sprachActiveIds = selectedSourceIds.slice(0, 3);

  async function deleteGlossaryEntry(entryId: number) {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/glossary/${entryId}`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary((prev) => prev.filter((e) => e.id !== entryId));
      loadGlossaryCount();
    } catch { /* ignore */ }
  }

  async function deleteAllGlossaryEntries() {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/glossary`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary([]);
      loadGlossaryCount();
    } catch { /* ignore */ }
  }

  const glossaryPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopGlossaryPolling() {
    if (glossaryPollRef.current) { clearInterval(glossaryPollRef.current); glossaryPollRef.current = null; }
  }

  async function loadGlossary() {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/glossary`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGlossary(data.entries || []);
        return data.entries?.length > 0;
      }
    } catch { /* ignore */ }
    return false;
  }

  async function generateGlossary() {
    if (sprachActiveIds.length === 0) return;
    setGlossaryLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/glossary/generate`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: sprachActiveIds }),
      });
      if (res.ok) {
        // Poll for glossary entries until they appear
        stopGlossaryPolling();
        const startCount = glossary.length;
        glossaryPollRef.current = setInterval(async () => {
          const hasNew = await loadGlossary();
          if (hasNew) {
            // Check if entries changed (new ones generated)
            const res2 = await fetch(`/api/ki-tutor/modules/${uuid}/glossary`, { credentials: "include" });
            if (res2.ok) {
              const data2 = await res2.json();
              if ((data2.entries || []).length !== startCount) {
                setGlossary(data2.entries || []);
                setGlossaryLoading(false);
                stopGlossaryPolling();
                loadGlossaryCount();
              }
            }
          }
        }, 3000);
        // Safety: stop polling after 2 minutes
        setTimeout(() => { stopGlossaryPolling(); setGlossaryLoading(false); }, 120000);
      } else {
        setGlossaryLoading(false);
      }
    } catch {
      setGlossaryLoading(false);
    }
  }

  async function generateCloze() {
    if (sprachActiveIds.length === 0) return;
    setClozeLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/exercises/cloze`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: sprachActiveIds }),
      });
      if (res.ok) {
        // Now creates an exercise set — reload sets via polling
        loadExerciseSets("lueckentext");
        setSprachView("cl-sets");
      }
    } catch { /* ignore */ } finally {
      setClozeLoading(false);
    }
  }

  async function generateVocabTest() {
    if (sprachActiveIds.length === 0) return;
    setVocabLoading(true);
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/exercises/vocab-test`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: sprachActiveIds }),
      });
      if (res.ok) {
        // Now creates an exercise set — reload sets via polling
        loadExerciseSets("vokabeltest");
        setSprachView("vt-sets");
      }
    } catch { /* ignore */ } finally {
      setVocabLoading(false);
    }
  }


  // Load exercise sets when switching to studio views
  useEffect(() => {
    if (studioView === "quiz") loadExerciseSets("quiz");
  }, [studioView]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleStudioSelect(view: StudioView) {
    if (view === "karteikarten" || view === "quiz") loadExerciseSets(view);
    setStudioView(view);
  }

  function handleNavigateToSet(setId: number, tool: string, mode: string) {
    if (tool === "mindmap") {
      selectMindmap(setId);
      setStudioView("mindmap");
      return;
    }
    if (tool === "datentabelle") {
      selectDatentabelle(setId);
      setStudioView("datentabelle");
      return;
    }
    loadExerciseSet(setId).then(() => {
      if (mode === "glossar") {
        // Sprachtraining
        if (tool === "lernkarten" || tool === "karteikarten") setSprachView("lk-learn");
        else if (tool === "lueckentext") setSprachView("cl-learn");
        else if (tool === "vokabeltest") setSprachView("vt-learn");
      } else {
        // Lerntools (mode=quelle)
        setStudioView(tool as StudioView);
      }
    });
  }

  // ─── Exercise Sets Functions ──────────────────────────────────────────────

  async function loadExerciseSets(tool?: string) {
    try {
      const url = tool
        ? `/api/ki-tutor/modules/${uuid}/exercise-sets?tool=${tool}`
        : `/api/ki-tutor/modules/${uuid}/exercise-sets`;
      const res = await fetch(url, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        const newSets: ExerciseSet[] = data.sets || [];
        if (tool) {
          // Merge: replace only sets of this tool, keep others
          setExerciseSets((prev) => [
            ...prev.filter((s) => s.tool !== tool),
            ...newSets,
          ]);
        } else {
          setExerciseSets(newSets);
        }
      }
    } catch { /* ignore */ }
  }

  async function loadExerciseSet(setId: number) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/exercise-sets/${setId}`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setActiveSet(data.set);
      }
    } catch { /* ignore */ }
  }

  async function createExerciseSet(tool: string, mode: string, count: number, sourceUuid?: string) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/exercise-sets`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tool, mode, count, source_uuid: sourceUuid }),
      });
      if (res.ok) {
        const data = await res.json();
        // Immediately add placeholder to sets list and start polling
        loadExerciseSets(tool);
        return data.set as ExerciseSet;
      }
    } catch { /* ignore */ }
    return null;
  }

  async function deleteExerciseSet(setId: number, tool: string) {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/exercise-sets/${setId}`, {
        method: "DELETE", credentials: "include",
      });
      loadExerciseSets(tool);
    } catch { /* ignore */ }
  }

  async function submitSingleAnswer(setId: number, itemId: number, correct: boolean, newRun = false) {
    try {
      await fetch(`/api/ki-tutor/modules/${uuid}/exercise-sets/${setId}/progress`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results: [{ item_id: itemId, correct }], new_run: newRun }),
      });
    } catch { /* ignore */ }
  }

  function refreshProgress() {
    loadStreak();
    loadExerciseSets();
    setStatsVersion(v => v + 1);
  }

  async function loadStreak() {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/streak`, { credentials: "include" });
      if (res.ok) setStreakInfo(await res.json());
    } catch { /* ignore */ }
  }

  async function loadGlossaryCount() {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/glossary-count`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setGlossaryCount(data.count);
      }
    } catch { /* ignore */ }
  }

  // Load glossary + sets + streak on mount
  useEffect(() => {
    loadGlossary();
    loadStreak();
    loadGlossaryCount();
    return () => stopGlossaryPolling();
  }, [uuid]); // eslint-disable-line react-hooks/exhaustive-deps

  // Navigate to a sprachtraining subview from the Tools tab
  function handleSprachNavigate(view: SprachtrainingView) {
    if (view === "lk-sets") loadExerciseSets("lernkarten");
    if (view === "cl-sets") loadExerciseSets("lueckentext");
    if (view === "vt-sets") loadExerciseSets("vokabeltest");
    setSprachView(view);
  }

  // Build the sprachtraining content tree
  // Helper: selected source for create-set modal
  const selectedSourceForSet = (() => {
    if (selectedSourceIds.length === 0) return null;
    const src = sources.find((s) => s.uuid === selectedSourceIds[0]);
    return src ? { uuid: src.uuid, filename: src.filename } : null;
  })();

  const sprachtrainingContent = (<div style={{ "--accent": "#9333EA", "--accent-rgb": "147,51,234" } as React.CSSProperties} className="flex flex-col flex-1 overflow-hidden">{(() => {
    switch (sprachView) {
      case "glossar":
        return (
          <GlossarView
            entries={glossary}
            loading={glossaryLoading}
            extracting={glossaryExtracting}
            onGenerate={generateGlossary}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
            sourceCount={selectedSourceIds.length}
            onOpenSource={(page, highlightText) => {
              const src = sources.find((s) => selectedSourceIds.includes(s.uuid));
              if (src) handleOpenViewer(src, page, highlightText);
            }}
            onDelete={deleteGlossaryEntry}
            onDeleteAll={deleteAllGlossaryEntries}
            stats={pageStats}
            showTranslation
          />
        );
      case "karteikarten":
        return (
          <VocabFlashcards
            entries={glossary}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
          />
        );
      case "lueckentext":
        return (
          <LueckentextView
            exercises={clozeExercises}
            loading={clozeLoading}
            onGenerate={generateCloze}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
          />
        );
      case "vokabeltest":
        return (
          <VokabeltestView
            questions={vocabQuestions}
            loading={vocabLoading}
            onGenerate={generateVocabTest}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
          />
        );
      // ─── Lernkarten Sets Flow ──────────────────────────────
      case "lk-sets":
        return (
          <ExerciseSetsOverview
            title="Lernkarten"
            sets={exerciseSets.filter((s) => s.tool === "lernkarten")}
            onBack={() => { setSprachView("overview"); }}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("lk-learn")); }}
            onCreate={() => { setCreateSetTool("lernkarten"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "lernkarten")}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
            category="sprachtraining"
          />
        );
      case "lk-learn":
        return activeSet ? (
          <LernkartenLearnView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={(text) => {
              setChatInput(text);
            }}
            onSourceClick={(filename, page, startTime) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
            }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
            showTranslation
          />
        ) : null;
      case "lk-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("lk-learn")}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); loadExerciseSets("lernkarten"); }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
          />
        ) : null;
      // ─── Lückentext Sets Flow ──────────────────────────────
      case "cl-sets":
        return (
          <ExerciseSetsOverview
            title="Lückentext"
            sets={exerciseSets.filter((s) => s.tool === "lueckentext")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("cl-learn")); }}
            onCreate={() => { setCreateSetTool("lueckentext"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "lueckentext")}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
            category="sprachtraining"
          />
        );
      case "cl-learn":
        return activeSet ? (
          <MCExerciseView
            exerciseSet={activeSet}
            tool="lueckentext"
            onBack={() => { setSprachView("cl-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={(text) => setChatInput(text)}
            onSourceClick={(filename, page, startTime) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
            }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
          />
        ) : null;
      case "cl-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("cl-learn")}
            onBack={() => { setSprachView("cl-sets"); setActiveSet(null); loadExerciseSets("lueckentext"); }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
          />
        ) : null;
      // ─── Vokabeltest Sets Flow ─────────────────────────────
      case "vt-sets":
        return (
          <ExerciseSetsOverview
            title="Begriffe-Quiz"
            sets={exerciseSets.filter((s) => s.tool === "vokabeltest")}
            onBack={() => setSprachView("overview")}
            onSelect={(s) => { loadExerciseSet(s.id).then(() => setSprachView("vt-learn")); }}
            onCreate={() => { setCreateSetTool("vokabeltest"); setShowCreateModal(true); }}
            onDelete={(id) => deleteExerciseSet(id, "vokabeltest")}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => setSprachView("overview") }]}
            category="sprachtraining"
          />
        );
      case "vt-learn":
        return activeSet ? (
          <MCExerciseView
            exerciseSet={activeSet}
            tool="vokabeltest"
            onBack={() => { setSprachView("vt-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={(text) => setChatInput(text)}
            onSourceClick={(filename, page, startTime) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
            }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
          />
        ) : null;
      case "vt-complete":
        return activeSet ? (
          <ExerciseCompletion
            title={activeSet.title.replace(/^(Lernkarten|Lückentext|Vokabeltest|Begriffe-Quiz|Quiz)\s*(aus|von)\s*/i, "")}
            results={[]}
            total={activeSet.card_count}
            onRetryWrong={() => setSprachView("vt-learn")}
            onBack={() => { setSprachView("vt-sets"); setActiveSet(null); loadExerciseSets("vokabeltest"); }}
            breadcrumbs={[{ label: "Fachsprachentraining", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
          />
        ) : null;
      default:
        return null;
    }
  })()}</div>);

  const glossarContent = (
    <GlossarView
      entries={glossary}
      loading={glossaryLoading}
      extracting={glossaryExtracting}
      onGenerate={generateGlossary}
      sourceCount={selectedSourceIds.length}
      onOpenSource={(page, highlightText) => {
        const src = sources.find((s) => selectedSourceIds.includes(s.uuid));
        if (src) handleOpenViewer(src, page, highlightText);
      }}
      onDelete={deleteGlossaryEntry}
      onDeleteAll={deleteAllGlossaryEntries}
      showTranslation={sprachtrainingActive}
    />
  );

  const notizenContent = (
    <NotizenStudio
      notes={notes}
      onAdd={addNote}
      onDelete={deleteNote}
      sources={sources}
      activeSourceIds={selectedSourceIds}
      onPillClick={handlePillClick}
    />
  );

  async function addNote(content: string) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/notes`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (res.ok) {
        const note = await res.json();
        setNotes((prev) => [note, ...prev]);
      }
    } catch { /* ignore */ }
  }

  async function deleteNote(noteId: number) {
    try {
      const res = await fetch(`/api/ki-tutor/modules/${uuid}/notes/${noteId}`, {
        method: "DELETE", credentials: "include",
      });
      if (res.ok) setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch { /* ignore */ }
  }


  // ─── Render ────────────────────────────────────────────────────────────────

  const isLecturer = auth?.role === "lecturer";
  const activeSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;

  const p1Style: React.CSSProperties = panels.quellen
    ? { flex: `1 1 ${p1Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p2Style: React.CSSProperties = panels.chat
    ? { flex: `1 1 ${p2Width}px`, minWidth: MIN_PANEL, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  const p3Style: React.CSSProperties = panels.studio
    ? { flex: `1 1 ${p3Width}px`, minWidth: 200, overflow: "hidden" }
    : { width: 48, flexShrink: 0, flexGrow: 0 };

  if (!initialized) {
    return (
      <ProtectedRoute>
        <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          <Header showLogout />
          <div className="flex-1 flex items-center justify-center">
            <Spinner size="lg" />
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
            style={{ height: 48 }}
          >
            <Link
              href="/ki-tutor"
              className="inline-flex items-center gap-1 text-xs font-medium transition-colors group flex-shrink-0"
              style={{ color: "var(--kb)" }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-hover:-translate-x-0.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
              Zurück zur Übersicht
            </Link>
            <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <span className="text-base font-bold truncate px-16 pointer-events-auto select-text cursor-text" style={{ color: "var(--text)" }}>
                {moduleDetail?.title ?? ""}
              </span>
            </span>
            <div ref={!isMobile ? settingsRef : undefined} className="relative flex-shrink-0 ml-auto">
            <button
              type="button"
              onClick={() => setShowSettings((v) => !v)}
              className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
              style={{ backgroundColor: showSettings ? "var(--kb)" : "var(--surface-dim)", color: showSettings ? "white" : "var(--muted)" }}
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
                {/* Chat-Sprache (disabled – requires full UI + tool language support) */}
                <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)", opacity: 0.4 }}>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Chat-Sprache</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Sprache der KI-Antworten</p>
                  </div>
                  <div className="flex gap-1">
                    {(["de", "en"] as const).map((lang) => (
                      <button
                        key={lang}
                        type="button"
                        disabled
                        className="text-xs font-semibold px-2.5 py-1 rounded-lg cursor-not-allowed"
                        style={{
                          backgroundColor: chatLang === lang ? "var(--kb)" : "var(--border)",
                          color: chatLang === lang ? "white" : "var(--muted)",
                        }}
                      >
                        {lang.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Studio-Panel */}
                <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Studio</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Studio-Panel anzeigen</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={studioEnabled}
                    onClick={() => setStudioEnabled((v) => !v)}
                    className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                    style={{ backgroundColor: studioEnabled ? "var(--kb)" : "#CBD5E1" }}
                  >
                    <span
                      className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                      style={{ transform: studioEnabled ? "translateX(16px)" : "translateX(0)" }}
                    />
                  </button>
                </div>
                {/* Sprachtraining */}
                <div className="flex items-center justify-between px-4 py-3" style={{ opacity: studioEnabled ? 1 : 0.4 }}>
                  <div>
                    <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Fachsprachentraining</p>
                    <p className="text-xs" style={{ color: "var(--muted)" }}>Zeigt Fachsprachentraining-Tab im Studio</p>
                  </div>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={sprachtrainingActive}
                    onClick={() => studioEnabled && setSprachtrainingActive((v) => !v)}
                    disabled={!studioEnabled}
                    className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                    style={{ backgroundColor: sprachtrainingActive && studioEnabled ? "var(--kb)" : "#CBD5E1", cursor: studioEnabled ? "pointer" : "not-allowed" }}
                  >
                    <span
                      className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                      style={{ transform: sprachtrainingActive && studioEnabled ? "translateX(16px)" : "translateX(0)" }}
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
          <div className="flex-shrink-0" style={{ backgroundColor: "var(--surface)" }}>
          <div className="flex items-center gap-2 px-3 pt-2 pb-1">
            <Link
              href="/ki-tutor"
              className="inline-flex items-center justify-center w-7 h-7 flex-shrink-0 transition-colors group"
              style={{ color: "var(--kb)" }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-hover:-translate-x-0.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
            </Link>
            <span className="text-sm font-bold truncate min-w-0" style={{ color: "var(--text)" }}>
              {moduleDetail?.title ?? ""}
            </span>
            <div ref={isMobile ? settingsRef : undefined} className="relative flex-shrink-0 ml-auto">
              <button
                type="button"
                onClick={() => setShowSettings((v) => !v)}
                className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
                style={{ backgroundColor: showSettings ? "var(--kb)" : "var(--surface-dim)", color: showSettings ? "white" : "var(--muted)" }}
                title="Einstellungen"
              >
                <GearSix size={17} weight={showSettings ? "fill" : "regular"} />
              </button>
              {/* Settings dropdown — Mobile */}
              {showSettings && (
                <div
                  className="absolute right-0 top-10 z-50 rounded-xl shadow-lg"
                  style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", width: 260 }}
                >
                  <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                    <p className="text-xs font-semibold" style={{ color: "var(--muted)" }}>Meine Einstellungen</p>
                  </div>
                  <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)", opacity: 0.4 }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Chat-Sprache</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Sprache der KI-Antworten</p>
                    </div>
                    <div className="flex gap-1">
                      {(["de", "en"] as const).map((lang) => (
                        <button
                          key={lang}
                          type="button"
                          disabled
                          className="text-xs font-semibold px-2.5 py-1 rounded-lg cursor-not-allowed"
                          style={{
                            backgroundColor: chatLang === lang ? "var(--kb)" : "var(--border)",
                            color: chatLang === lang ? "white" : "var(--muted)",
                          }}
                        >
                          {lang.toUpperCase()}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Studio</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Studio-Panel anzeigen</p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={studioEnabled}
                      onClick={() => setStudioEnabled((v) => !v)}
                      className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                      style={{ backgroundColor: studioEnabled ? "var(--kb)" : "#CBD5E1" }}
                    >
                      <span
                        className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                        style={{ transform: studioEnabled ? "translateX(16px)" : "translateX(0)" }}
                      />
                    </button>
                  </div>
                  <div className="flex items-center justify-between px-4 py-3" style={{ opacity: studioEnabled ? 1 : 0.4 }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Fachsprachentraining</p>
                      <p className="text-xs" style={{ color: "var(--muted)" }}>Zeigt Fachsprachentraining-Tab im Studio</p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={sprachtrainingActive}
                      onClick={() => studioEnabled && setSprachtrainingActive((v) => !v)}
                      disabled={!studioEnabled}
                      className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                      style={{ backgroundColor: sprachtrainingActive && studioEnabled ? "var(--kb)" : "#CBD5E1", cursor: studioEnabled ? "pointer" : "not-allowed" }}
                    >
                      <span
                        className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                        style={{ transform: sprachtrainingActive && studioEnabled ? "translateX(16px)" : "translateX(0)" }}
                      />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
          <div
            className="flex"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            {(["quellen", "chat", ...(studioEnabled ? ["studio"] : [])] as PanelKey[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(key)}
                className="flex-1 py-3 text-sm font-medium transition-colors relative"
                style={{ color: activeTab === key ? "var(--kb)" : "var(--muted)", background: "none", border: "none" }}
              >
                {key === "quellen" ? "Quellen" : key === "chat" ? "Chat" : "Studio"}
                {activeTab === key && (
                  <span
                    className="absolute bottom-0 left-0 right-0"
                    style={{ height: 2, backgroundColor: "var(--kb)", display: "block" }}
                  />
                )}
              </button>
            ))}
          </div>
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
            <MinimizeContext.Provider value={() => setActiveTab("chat")}>
            <div
              className="flex flex-col flex-1 overflow-hidden rounded-2xl"
              style={{ backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
            >
              {activeTab === "quellen" ? (
                viewerSource ? (
                  _isMediaFile(viewerSource.filename) ? (
                    <MediaPlayer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onMinimize={() => setActiveTab("chat")} />
                  ) : (
                    <PdfViewer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onAskWithSelection={handleAskWithSelection} onCustomQuestion={handleCustomQuestion} popupActions={popupActions} onAddToGlossary={handleAddToGlossary} onMinimize={() => setActiveTab("chat")} />
                  )
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
                  onSendPrompt={(text) => sendChatMessage(text)}
                  onPillClick={handlePillClick}
                  moduleReady={moduleDetail?.status === "ready"}
                  onClear={() => { const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : ""; fetch(`/api/ki-tutor/modules/${uuid}/messages${eidParam}`, { method: "DELETE", credentials: "include" }); setMessages([]); }}
                  externalTextareaRef={chatTextareaRef}
                  onSaveNote={addNote}
                />
              ) : sprachView !== "overview" ? (
                sprachtrainingContent
              ) : studioView === "overview" ? (
                <StudioOverview onSelect={handleStudioSelect} onMinimize={() => setActiveTab("chat")} sprachtrainingActive={sprachtrainingActive} sprachtrainingContent={sprachtrainingContent} glossarContent={glossarContent} notizenContent={notizenContent} moduleUuid={uuid} statsVersion={statsVersion} onNavigateToSet={handleNavigateToSet} onSprachNavigate={handleSprachNavigate} activeSourceCount={selectedSourceIds.length} sprachView={sprachView} />
              ) : activeSet && activeSet.tool === "karteikarten" ? (
                <LernkartenLearnView
                  exerciseSet={activeSet}
                  onBack={() => { setActiveSet(null); refreshProgress(); }}
                  onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                  onAskChat={(text) => { setChatInput(text); setActiveTab("chat"); }}
                  onSourceClick={(filename, page, startTime) => {
                    const src = sources.find((s) => s.filename === filename);
                    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
                  }}
                  breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Karteikarten", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                />
              ) : activeSet && activeSet.tool === "quiz" ? (
                <MCExerciseView
                  exerciseSet={activeSet}
                  tool="quiz"
                  onBack={() => { setActiveSet(null); refreshProgress(); }}
                  onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                  onAskChat={(text) => { setChatInput(text); setActiveTab("chat"); }}
                  onSourceClick={(filename, page, startTime) => {
                    const src = sources.find((s) => s.filename === filename);
                    if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
                  }}
                  breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Quiz", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                />
              ) : studioView === "karteikarten" ? (
                <ExerciseSetsOverview
                  title="Karteikarten"
                  sets={exerciseSets.filter((s) => s.tool === "karteikarten")}
                  onBack={() => setStudioView("overview")}
                  onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                  onCreate={() => { setCreateSetTool("karteikarten"); setShowCreateModal(true); }}
                  onDelete={(id) => deleteExerciseSet(id, "karteikarten")}
                  sourceCount={selectedSourceIds.length}
                  stats={pageStats}
                />
              ) : studioView === "notizen" ? (
                <NotizenStudio
                  notes={notes}
                  onAdd={addNote}
                  onDelete={deleteNote}
                  onBack={() => setStudioView("overview")}
                  sources={sources}
                  activeSourceIds={selectedSourceIds}
                  onPillClick={handlePillClick}
                  stats={pageStats}
                  breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                />
              ) : studioView === "datentabelle" ? (
                <DatentabelleStudio
                    table={datentabelle}
                    sources={datentabelleSources}
                    loading={datentabelleLoading}
                    onGenerate={generateDatentabelle}
                    onBack={() => setStudioView("overview")}
                    savedList={datentabelleList}
                    onSelect={selectDatentabelle}
                    onDelete={deleteDatentabelle}
                    sourceCount={selectedSourceIds.length}
                    allSources={sources}
                    onPillClick={handlePillClick}
                    stats={pageStats}
                    breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                  />
              ) : studioView === "mindmap" ? (
                <MindmapStudio mindmap={mindmapData} loading={mindmapLoading} onGenerate={generateMindmap} onBack={() => setStudioView("overview")} savedList={mindmapList} onSelect={selectMindmap} onDelete={deleteMindmap} sourceCount={selectedSourceIds.length} sources={sources} onPillClick={handlePillClick} stats={pageStats} />
              ) : studioView === "quiz" ? (
                <ExerciseSetsOverview
                  title="Quiz"
                  sets={exerciseSets.filter((s) => s.tool === "quiz")}
                  onBack={() => setStudioView("overview")}
                  onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                  onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
                  onDelete={(id) => deleteExerciseSet(id, "quiz")}
                  sourceCount={selectedSourceIds.length}
                  stats={pageStats}
                  breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                />
              ) : null}
            </div>
            </MinimizeContext.Provider>
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
                  _isMediaFile(viewerSource.filename) ? (
                    <MediaPlayer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onMinimize={() => togglePanel("quellen")} />
                  ) : (
                    <PdfViewer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onAskWithSelection={handleAskWithSelection} onCustomQuestion={handleCustomQuestion} popupActions={popupActions} onAddToGlossary={handleAddToGlossary} onMinimize={() => togglePanel("quellen")} />
                  )
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
                  style={{ height: 48, backgroundColor: "var(--kb)" }}
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
                    onSendPrompt={(text) => sendChatMessage(text)}
                    onPillClick={handlePillClick}
                    moduleReady={moduleDetail?.status === "ready"}
                    onClear={() => { const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : ""; fetch(`/api/ki-tutor/modules/${uuid}/messages${eidParam}`, { method: "DELETE", credentials: "include" }); setMessages([]); }}
                    externalTextareaRef={chatTextareaRef}
                    onSaveNote={addNote}
                    onMinimize={() => togglePanel("chat")}
                  />
                )}
              </div>

              {studioEnabled && (
                <>
                {/* Drag handle 2 */}
                <div
                  className="group flex-shrink-0 flex items-center justify-center"
                  style={{ width: 8, cursor: panels.chat && panels.studio ? "col-resize" : "default" }}
                  onMouseDown={(e) => panels.chat && panels.studio && startDrag(2, e)}
                >
                  <div
                    className="w-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ height: 48, backgroundColor: "var(--kb)" }}
                  />
                </div>

                {/* Panel 3 — Studio */}
                <div
                  ref={p3Ref}
                  className="flex flex-col overflow-hidden rounded-2xl"
                  style={{ ...p3Style, backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
                >
                  <MinimizeContext.Provider value={() => togglePanel("studio")}>
                  {!panels.studio ? (
                    <MiniStrip label="Studio" onClick={() => togglePanel("studio")} side="right" />
                  ) : sprachView !== "overview" ? (
                    sprachtrainingContent
                  ) : studioView === "overview" ? (
                    <StudioOverview onSelect={handleStudioSelect} onMinimize={() => togglePanel("studio")} sprachtrainingActive={sprachtrainingActive} sprachtrainingContent={sprachtrainingContent} glossarContent={glossarContent} notizenContent={notizenContent} moduleUuid={uuid} statsVersion={statsVersion} onNavigateToSet={handleNavigateToSet} onSprachNavigate={handleSprachNavigate} activeSourceCount={selectedSourceIds.length} sprachView={sprachView} />
                  ) : activeSet && activeSet.tool === "karteikarten" ? (
                    <LernkartenLearnView
                      exerciseSet={activeSet}
                      onBack={() => { setActiveSet(null); refreshProgress(); }}
                      onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                      onAskChat={(text) => { setChatInput(text); }}
                      onSourceClick={(filename, page, startTime) => {
                        const src = sources.find((s) => s.filename === filename);
                        if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
                      }}
                      breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Karteikarten", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                    />
                  ) : activeSet && activeSet.tool === "quiz" ? (
                    <MCExerciseView
                      exerciseSet={activeSet}
                      tool="quiz"
                      onBack={() => { setActiveSet(null); refreshProgress(); }}
                      onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                      onAskChat={(text) => { setChatInput(text); setActiveTab("chat"); }}
                      onSourceClick={(filename, page, startTime) => {
                        const src = sources.find((s) => s.filename === filename);
                        if (src) handlePillClick(src.uuid, page, filename, undefined, startTime);
                      }}
                      breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Quiz", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                    />
                  ) : studioView === "karteikarten" ? (
                    <ExerciseSetsOverview
                      title="Karteikarten"
                      sets={exerciseSets.filter((s) => s.tool === "karteikarten")}
                      onBack={() => setStudioView("overview")}
                      onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                      onCreate={() => { setCreateSetTool("karteikarten"); setShowCreateModal(true); }}
                      onDelete={(id) => deleteExerciseSet(id, "karteikarten")}
                      sourceCount={selectedSourceIds.length}
                      stats={pageStats}
                      breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                    />
                  ) : studioView === "notizen" ? (
                    <NotizenStudio
                      notes={notes}
                      onAdd={addNote}
                      onDelete={deleteNote}
                      onBack={() => setStudioView("overview")}
                      sources={sources}
                      activeSourceIds={selectedSourceIds}
                      onPillClick={handlePillClick}
                      stats={pageStats}
                      breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                    />
                  ) : studioView === "datentabelle" ? (
                    <DatentabelleStudio
                      table={datentabelle}
                      sources={datentabelleSources}
                      loading={datentabelleLoading}
                      onGenerate={generateDatentabelle}
                      onBack={() => setStudioView("overview")}
                      savedList={datentabelleList}
                      onSelect={selectDatentabelle}
                      onDelete={deleteDatentabelle}
                      sourceCount={selectedSourceIds.length}
                      allSources={sources}
                      onPillClick={handlePillClick}
                      stats={pageStats}
                      breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                    />
                  ) : studioView === "mindmap" ? (
                    <MindmapStudio mindmap={mindmapData} loading={mindmapLoading} onGenerate={generateMindmap} onBack={() => setStudioView("overview")} savedList={mindmapList} onSelect={selectMindmap} onDelete={deleteMindmap} sourceCount={selectedSourceIds.length} sources={sources} onPillClick={handlePillClick} stats={pageStats} />
                  ) : studioView === "quiz" ? (
                    <ExerciseSetsOverview
                      title="Quiz"
                      sets={exerciseSets.filter((s) => s.tool === "quiz")}
                      onBack={() => setStudioView("overview")}
                      onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                      onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
                      onDelete={(id) => deleteExerciseSet(id, "quiz")}
                      sourceCount={selectedSourceIds.length}
                      stats={pageStats}
                      breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                    />
                  ) : null}
                  </MinimizeContext.Provider>
                </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
      {/* Create Set Modal */}
      {showCreateModal && (
        <CreateSetModal
          tool={createSetTool}
          glossaryCount={glossaryCount || glossary.length}
          selectedSource={selectedSourceForSet}
          creating={setCreating}
          onClose={() => setShowCreateModal(false)}
          onCreate={async (mode, count) => {
            setShowCreateModal(false);
            if (createSetTool === "quiz" || createSetTool === "karteikarten") {
              // Studio tools stay in Studio
              setStudioView(createSetTool as StudioView);
            } else {
              const setsView = `${createSetTool === "lernkarten" ? "lk" : createSetTool === "lueckentext" ? "cl" : "vt"}-sets` as SprachtrainingView;
              setSprachView(setsView);
            }
            await createExerciseSet(
              createSetTool, mode, count,
              mode === "quelle" ? selectedSourceIds[0] : undefined,
            );
            const poll = setInterval(() => loadExerciseSets(createSetTool), 3000);
            setTimeout(() => clearInterval(poll), 120000);
          }}
        />
      )}
    </ProtectedRoute>
  );
}
