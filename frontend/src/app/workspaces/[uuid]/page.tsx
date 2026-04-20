"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import HelpTooltip from "@/components/ui/HelpTooltip";
import Spinner from "@/components/ui/Spinner";
import {
  CaretLeft,
  CaretRight,
  Chat,
  Check,
  FilePdf,
  Plus,
  SidebarSimple,
  Cards,
  Question,
  XIcon,
  Lightbulb,
  BookOpenText,
  ChartBar,
  Table,
  TreeStructure,
  GearSix,
  Trash,
  Book,
  TextAa,
  Exam,
  ArrowCounterClockwise,
  WarningCircle,
  DownloadSimple,
  Files,
  ClockCounterClockwise,
  DotsThreeVertical,
} from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { checkAuthStatus } from "@/lib/auth";
import type { AuthStatus } from "@/types";

import type {
  ModuleDetail,
  Source,
  SourceRef,
  SourceQmap,
  ChatMessage,
  LernKarte,
  QuizQuestion,
  ViewerState,
  DatentabelleRowSource,
  DatentabelleData,
  DatentabelleSource,
  StudioView,
  PanelKey,
  GlossaryEntry,
  ClozeExercise,
  VocabTestQuestion,
  SprachtrainingView,
  ExerciseItemSource,
  ExerciseItemExtras,
  ExerciseItem,
  ExerciseSet,
  StreakInfo,
  ExerciseOverview,
  HeatmapDay,
  StudentStats,
} from "./_types";
import {
  _formatApiError,
  _isMediaFile,
  _getChipIcon,
  _md,
  _chunkLabel,
} from "./_utils";
import { MinimizeContext } from "./_context";
// Types from heavy modules (type-only imports don't pull in runtime code)
import type { MindmapNodeData } from "./_components/MindmapStudio";
import type { Note } from "./_components/NotizenStudio";

// Lightweight components needed on initial render
import { SourcesPanel } from "./_components/SourcesPanel";
import { ChatPanel } from "./_components/ChatPanel";
import { SubviewHeader } from "./_components/SubviewHeader";
import { ExerciseSetsOverview } from "./_components/ExerciseSetsOverview";
import { ExerciseCompletion } from "./_components/ExerciseCompletion";
import { CreateSetModal } from "./_components/CreateSetModal";
import { GlossarMenu, GlossarView } from "./_components/GlossarView";
import { SprachtrainingOverview } from "./_components/SprachtrainingOverview";
import { TOOL_COLORS, TOOL_LABELS } from "./_constants";
import { MasteryBar } from "./_components/MasteryBar";
import { LerntoolsGrid } from "./_components/LerntoolsGrid";
import { RecentActivities } from "./_components/RecentActivities";
import { StudioTabs } from "./_components/StudioTabs";
import { MiniStrip } from "./_components/MiniStrip";

// Heavy / conditionally-rendered components: loaded on demand to keep initial bundle small
const dynamicLoader = () => <div className="flex-1 flex items-center justify-center p-6"><Spinner size="md" /></div>;

const PdfViewer = dynamic(() => import("./_components/PdfViewer").then((m) => ({ default: m.PdfViewer })), { loading: dynamicLoader, ssr: false });
const MediaPlayer = dynamic(() => import("./_components/MediaPlayer").then((m) => ({ default: m.MediaPlayer })), { loading: dynamicLoader, ssr: false });
const MindmapStudio = dynamic(() => import("./_components/MindmapStudio").then((m) => ({ default: m.MindmapStudio })), { loading: dynamicLoader, ssr: false });
const DatentabelleStudio = dynamic(() => import("./_components/DatentabelleStudio").then((m) => ({ default: m.DatentabelleStudio })), { loading: dynamicLoader, ssr: false });
const NotizenStudio = dynamic(() => import("./_components/NotizenStudio").then((m) => ({ default: m.NotizenStudio })), { loading: dynamicLoader, ssr: false });
const StudentStatsView = dynamic(() => import("./_components/StudentStatsView").then((m) => ({ default: m.StudentStatsView })), { loading: dynamicLoader, ssr: false });
const ZeitplanView = dynamic(() => import("./_components/ZeitplanView").then((m) => ({ default: m.ZeitplanView })), { loading: dynamicLoader, ssr: false });
const LernkartenLearnView = dynamic(() => import("./_components/LernkartenLearnView").then((m) => ({ default: m.LernkartenLearnView })), { loading: dynamicLoader, ssr: false });
const MCExerciseView = dynamic(() => import("./_components/MCExerciseView").then((m) => ({ default: m.MCExerciseView })), { loading: dynamicLoader, ssr: false });
const VocabFlashcards = dynamic(() => import("./_components/VocabFlashcards").then((m) => ({ default: m.VocabFlashcards })), { loading: dynamicLoader, ssr: false });
const LueckentextView = dynamic(() => import("./_components/LueckentextView").then((m) => ({ default: m.LueckentextView })), { loading: dynamicLoader, ssr: false });
const VokabeltestView = dynamic(() => import("./_components/VokabeltestView").then((m) => ({ default: m.VokabeltestView })), { loading: dynamicLoader, ssr: false });

// ─── Studio Overview ──────────────────────────────────────────────────────────

function StudioOverview({ onSelect, onMinimize, sprachtrainingActive, sprachtrainingContent, glossarContent, notizenContent, moduleUuid, statsVersion, onNavigateToSet, onSprachNavigate, activeSourceCount, sprachView, requestedTab, sources, selectedSourceIds, onPillClick }: { onSelect: (v: StudioView) => void; onMinimize: () => void; sprachtrainingActive: boolean; sprachtrainingContent?: React.ReactNode; glossarContent?: React.ReactNode; notizenContent?: React.ReactNode; moduleUuid: string; statsVersion: number; onNavigateToSet?: (setId: number, tool: string, mode: string) => void; onSprachNavigate?: (view: SprachtrainingView) => void; activeSourceCount?: number; sprachView?: string; requestedTab?: { tab: "tools" | "glossar" | "notizen" | "statistik" | "zeitplan"; nonce: number } | null; sources: Source[]; selectedSourceIds: string[]; onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void }) {
  const [studioTab, _setStudioTab] = useState<"tools" | "sprachtraining" | "glossar" | "notizen" | "statistik" | "zeitplan">(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("kis-studio-tab");
      if (saved && ["tools", "glossar", "notizen", "statistik", "zeitplan"].includes(saved)) return saved as any;
    }
    return "tools";
  });
  const setStudioTab = (tab: typeof studioTab) => { _setStudioTab(tab); sessionStorage.setItem("kis-studio-tab", tab); };

  const [studentStats, setStudentStats] = useState<StudentStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const refreshStats = useCallback(() => {
    setStatsLoading(true);
    fetch(`/api/ki-assistent/modules/${moduleUuid}/stats`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setStudentStats(data); })
      .catch(() => { })
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

  // External request to switch studio tab (e.g. from PDF "Zum Glossar")
  useEffect(() => {
    if (requestedTab) setStudioTab(requestedTab.tab);
  }, [requestedTab?.nonce]); // eslint-disable-line react-hooks/exhaustive-deps

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
              { key: "zeitplan" as const, label: "Zeitplan" },
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
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>Fachsprachentraining</span>
              </div>
              <LerntoolsGrid tiles={sprachTiles} onSelect={(key) => {
                if (onSprachNavigate) {
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
        <StudentStatsView stats={studentStats} loading={statsLoading} moduleUuid={moduleUuid} onNavigateToSet={onNavigateToSet} sprachtrainingActive={sprachtrainingActive} />
      )}

      {/* Zeitplan Inhalt */}
      {studioTab === "zeitplan" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <ZeitplanView moduleUuid={moduleUuid} sources={sources} selectedSourceIds={selectedSourceIds} onPillClick={onPillClick} />
        </div>
      )}
    </div>
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
      const stored = localStorage.getItem(`ki-assistent-panels-${uuid}`);
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
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; percent: number } | null>(null);
  const [uploadErrors, setUploadErrors] = useState<{ filename: string; message: string }[]>([]);

  // Persist selected sources to sessionStorage
  useEffect(() => {
    if (selectedSourceIds.length > 0) {
      sessionStorage.setItem(`kis-selected-sources-${uuid}`, JSON.stringify(selectedSourceIds));
    }
  }, [selectedSourceIds, uuid]);

  const [viewerSource, setViewerSource] = useState<ViewerState | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatTextareaRef = useRef<HTMLTextAreaElement>(null);
  const chatSetInputRef = useRef<((v: string) => void) | null>(null);
  const registerChatSetInput = useCallback((setter: ((v: string) => void) | null) => {
    chatSetInputRef.current = setter;
  }, []);

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
  const [hideHeader, setHideHeader] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem(`ki-assistent-hide-header-${uuid}`) === "1"; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem(`ki-assistent-hide-header-${uuid}`, hideHeader ? "1" : "0"); } catch { /* ignore */ }
  }, [hideHeader, uuid]);

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
  const [pendingTitleIds, setPendingTitleIds] = useState<Set<number>>(new Set());

  // ─── Sprachtraining State ─────────────────────────────────────────────────
  const [sprachView, setSprachView] = useState<SprachtrainingView>("overview");
  const [studioTabRequest, setStudioTabRequest] = useState<{ tab: "tools" | "glossar" | "notizen" | "statistik" | "zeitplan"; nonce: number } | null>(null);
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/messages${eidParam}`, { credentials: "include" });
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

        const modRes = await fetch(`/api/ki-assistent/modules/${uuid}`, { credentials: "include" });
        if (cancelled) return;
        if (!modRes.ok) { router.push("/workspaces"); return; }
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

        const settingsRes = await fetch(`/api/ki-assistent/modules/${uuid}/settings`, { credentials: "include" });
        if (!cancelled && settingsRes.ok) {
          const s = await settingsRes.json();
          setChatLang(s.chat_lang ?? "de");
          setStudioEnabled(s.studio_enabled ?? true);
          setSprachtrainingActive(s.sprachtraining_active ?? false);
        }

        const actionsRes = await fetch("/api/ki-assistent/popup-actions", { credentials: "include" });
        if (!cancelled && actionsRes.ok) {
          const d = await actionsRes.json();
          setPopupActions(d.actions ?? []);
        }

        const notesRes = await fetch(`/api/ki-assistent/modules/${uuid}/notes`, { credentials: "include" });
        if (!cancelled && notesRes.ok) setNotes(await notesRes.json());

        if (!cancelled) setInitialized(true);
      } catch {
        if (!cancelled) router.push("/workspaces");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [uuid, router, loadMessages]);

  // Fetch stats at page level so sub-views can show mastery bar
  const refreshPageStats = useCallback(() => {
    fetch(`/api/ki-assistent/modules/${uuid}/stats`, { credentials: "include" })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setPageStats(data); })
      .catch(() => { });
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
    try { localStorage.setItem(`ki-assistent-panels-${uuid}`, JSON.stringify(panels)); } catch { /* ignore */ }
  }, [panels, uuid]);

  // Persist settings to DB (only after init to avoid overwriting with defaults)
  useEffect(() => {
    if (!initialized) return;
    fetch(`/api/ki-assistent/modules/${uuid}/settings`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, { credentials: "include" });
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

  // Freeze isMobile while a media file is open so orientation changes don't
  // remount <MediaPlayer> (which would reset video currentTime to 0:00).
  const mediaOpen = viewerSource !== null && _isMediaFile(viewerSource.filename);
  const mediaOpenRef = useRef(mediaOpen);
  mediaOpenRef.current = mediaOpen;

  // Treat a phone in landscape (short height + touch pointer) as "mobile" too,
  // so the layout stays single-column instead of switching to desktop columns
  // just because the viewport got wider after rotation.
  const mobileMediaQuery = `(max-width: ${MOBILE_BREAKPOINT - 1}px), (max-height: 500px) and (pointer: coarse)`;

  useEffect(() => {
    const mq = window.matchMedia(mobileMediaQuery);
    setIsMobile(mq.matches);
    if (mq.matches) setActiveTab("quellen");
    const handler = (e: MediaQueryListEvent) => {
      if (mediaOpenRef.current) return;
      setIsMobile(e.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mobileMediaQuery]);

  useEffect(() => {
    if (!mediaOpen) {
      setIsMobile(window.matchMedia(mobileMediaQuery).matches);
    }
  }, [mediaOpen, mobileMediaQuery]);

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
    const p = panelsRef.current;

    const panelKeys: PanelKey[] = ["quellen", "chat", "studio"];
    const refs = [p1Ref, p2Ref, p3Ref];
    const keys = ["p1", "p2", "p3"] as const;

    // Collect all open panel indices
    const openIdxs = [0, 1, 2].filter((i) => p[panelKeys[i]]);
    if (openIdxs.length < 2) return;

    // Pick the two open panels to resize:
    // - If both neighbors of the divider are open, use them
    // - Otherwise use the first two open panels (they're the only resizable pair)
    const idx = divider === 1 ? 1 : 2;
    let leftIdx: number, rightIdx: number;
    const directLeft = openIdxs.filter((i) => i < idx);
    const directRight = openIdxs.filter((i) => i >= idx);
    if (directLeft.length > 0 && directRight.length > 0) {
      leftIdx = directLeft[directLeft.length - 1];
      rightIdx = directRight[0];
    } else {
      leftIdx = openIdxs[0];
      rightIdx = openIdxs[1];
    }

    const refA = refs[leftIdx], refB = refs[rightIdx];
    const keyA = keys[leftIdx], keyB = keys[rightIdx];

    const widths = { p1: p1Width, p2: p2Width, p3: p3Width };
    const startX = e.clientX;
    const startA = widths[keyA];
    const startB = widths[keyB];

    function clampDelta(raw: number) {
      return Math.min(startB - MIN_PANEL, Math.max(-(startA - MIN_PANEL), raw));
    }

    function onMove(ev: MouseEvent) {
      if (!refA.current || !refB.current) return;
      const d = clampDelta(ev.clientX - startX);
      refA.current.style.flexBasis = `${startA + d}px`;
      refB.current.style.flexBasis = `${startB - d}px`;
    }

    function onUp(ev: MouseEvent) {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      const d = clampDelta(ev.clientX - startX);
      const setA = keyA === "p1" ? setP1Width : keyA === "p2" ? setP2Width : setP3Width;
      const setB = keyB === "p1" ? setP1Width : keyB === "p2" ? setP2Width : setP3Width;
      setA(startA + d);
      setB(startB - d);
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/sources/${srcUuid}`, { method: "DELETE", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.filter((s) => s.uuid !== srcUuid));
        setSelectedSourceIds((prev) => prev.filter((id) => id !== srcUuid));
      }
    } catch { /* ignore */ }
  }

  async function handleRetrySource(srcUuid: string) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/sources/${srcUuid}/retry`, { method: "POST", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.map((s) => s.uuid === srcUuid ? { ...s, status: "pending", error_message: null } : s));
      }
    } catch { /* ignore */ }
  }

  async function handleUpload(files: File[]) {
    if (files.length === 0) return;
    const MAX_BATCH = 10;
    const skipped = files.length > MAX_BATCH ? files.slice(MAX_BATCH) : [];
    const toUpload = files.length > MAX_BATCH ? files.slice(0, MAX_BATCH) : files;
    const errors: { filename: string; message: string }[] = skipped.map((f) => ({
      filename: f.name,
      message: `Übersprungen, maximal ${MAX_BATCH} Dateien gleichzeitig hochladen.`,
    }));
    setUploadErrors(errors);
    for (let i = 0; i < toUpload.length; i++) {
      const file = toUpload[i];
      setUploadProgress({ current: i + 1, total: toUpload.length, percent: 0 });
      try {
        await new Promise<void>((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", `/api/ki-assistent/modules/${uuid}/sources`);
          xhr.withCredentials = true;
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) setUploadProgress({ current: i + 1, total: toUpload.length, percent: Math.round((e.loaded / e.total) * 100) });
          };
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              const newSrc: Source = JSON.parse(xhr.responseText);
              setSources((prev) => [newSrc, ...prev]);
              resolve();
            } else {
              let detail = "Upload fehlgeschlagen";
              try {
                const body = JSON.parse(xhr.responseText);
                if (body?.detail) detail = body.detail;
              } catch { /* ignore */ }
              reject(new Error(detail));
            }
          };
          xhr.onerror = () => reject(new Error("Netzwerkfehler"));
          const form = new FormData();
          form.append("file", file);
          xhr.send(form);
        });
      } catch (err) {
        errors.push({ filename: file.name, message: err instanceof Error ? err.message : "Upload fehlgeschlagen" });
      }
    }
    setUploadProgress(null);
    if (errors.length > 0) setUploadErrors(errors);
  }

  // ─── Chat ──────────────────────────────────────────────────────────────────

  async function sendChatMessage(content: string, directText = false, sourceInfo?: { uuid: string; filename: string; page: number; selectedText?: string }) {
    // Strip leftover citation markers from pasted AI text
    content = content.replace(/\s*\[(?:Q\d+,\s*)?S\.\s*\d+\]/g, "");
    const effectiveSourceIds = viewerSource ? [viewerSource.uuid] : selectedSourceIds;
    if (!content.trim()) return;
    if (!directText && effectiveSourceIds.length === 0) return;
    const msgSourceCount = directText ? 1 : effectiveSourceIds.length;
    const popupSel = sourceInfo?.selectedText
      ? { uuid: sourceInfo.uuid, page: sourceInfo.page, text: sourceInfo.selectedText }
      : undefined;
    setMessages((prev) => [...prev, { role: "user", content: content.trim(), sourceCount: msgSourceCount, popup_selection: popupSel }]);
    setChatLoading(true);
    // Add placeholder assistant message for streaming
    setMessages((prev) => [...prev, { role: "assistant", content: "", sourceCount: msgSourceCount, popup_selection: popupSel }]);

    const updateLast = (patch: Partial<ChatMessage>) =>
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last) updated[updated.length - 1] = { ...last, ...patch };
        return updated;
      });

    try {
      const res = await fetch(`/api/ki-assistent-stream/${uuid}`, {
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
              // Apply corrected answer (page numbers fixed) + metadata
              const patch: Record<string, unknown> = { source_pages: evt.source_pages, source_qmap: evt.source_qmap };
              if (evt.answer) patch.content = evt.answer;
              updateLast(patch);
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
        updateLast({ content: "Der Workspace wird noch indiziert. Bitte warte einen Moment und versuche es erneut." });
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
  const [glossaryFeedback, setGlossaryFeedback] = useState<{ kind: "success" | "info" | "error"; message: string } | null>(null);
  const glossaryFeedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function showGlossaryFeedback(kind: "success" | "info" | "error", message: string) {
    if (glossaryFeedbackTimerRef.current) clearTimeout(glossaryFeedbackTimerRef.current);
    setGlossaryFeedback({ kind, message });
    glossaryFeedbackTimerRef.current = setTimeout(() => setGlossaryFeedback(null), 6000);
  }

  async function handleAddToGlossary(text: string, sourceUuid: string, page: number) {
    // Open Studio > Glossar tab and show extracting state
    setSprachView("overview");
    setStudioTabRequest({ tab: "glossar", nonce: Date.now() });
    if (isMobile) setActiveTab("studio");
    else setPanels((prev) => ({ ...prev, studio: true }));
    setGlossaryFeedback(null);
    setGlossaryExtracting(true);
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/glossary/extract`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, source_uuid: sourceUuid, page_number: page }),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.added > 0) {
          loadGlossary();
          loadGlossaryCount();
          showGlossaryFeedback("success", data.message || `${data.added} Begriff(e) hinzugefügt.`);
        } else {
          showGlossaryFeedback("info", data.message || "Keine neuen Begriffe gefunden.");
        }
      } else {
        showGlossaryFeedback("error", "Extraktion fehlgeschlagen. Bitte erneut versuchen.");
      }
    } catch {
      showGlossaryFeedback("error", "Netzwerkfehler. Bitte erneut versuchen.");
    } finally {
      setGlossaryExtracting(false);
    }
  }

  function handleAskChat(text: string, switchTab = false) {
    const chatWasOpen = isMobile ? activeTab === "chat" : panels.chat;
    const value = text + "\n\n";
    chatSetInputRef.current?.(value);
    if (isMobile || switchTab) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    const delay = chatWasOpen ? 50 : 300;
    setTimeout(() => {
      const el = chatTextareaRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(value.length, value.length);
      el.scrollTop = el.scrollHeight;
    }, delay);
  }

  function handleCustomQuestion(selectedText: string) {
    const chatWasOpen = isMobile ? activeTab === "chat" : panels.chat;
    if (isMobile) setActiveTab("chat");
    else setPanels((prev) => ({ ...prev, chat: true }));
    const value = `"${selectedText}"\n\n`;
    chatSetInputRef.current?.(value);
    // If chat was closed, wait longer for React to render the panel before focusing
    const delay = chatWasOpen ? 50 : 300;
    setTimeout(() => {
      const ta = chatTextareaRef.current;
      if (!ta) return;
      ta.focus();
      ta.setSelectionRange(value.length, value.length);
      ta.scrollTop = ta.scrollHeight;
    }, delay);
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/lernkarten/generate`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/mindmaps`, { credentials: "include" });
      if (res.ok) setMindmapList(await res.json());
    } catch { /* ignore */ }
  }

  function startMindmapPolling(mindmapId: number) {
    stopMindmapPolling();
    setMindmapLoading(true);
    mindmapPollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/mindmap/${mindmapId}`, { credentials: "include" });
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
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/mindmap`, { credentials: "include" });
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/mindmap/generate`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/mindmap/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.mindmap) {
        setMindmapData(data.mindmap);
      }
    } catch { /* ignore */ }
  }

  async function deleteMindmap(id: number) {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/mindmap/${id}`, { method: "DELETE", credentials: "include" });
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabellen`, { credentials: "include" });
      if (res.ok) setDatentabelleList(await res.json());
    } catch { /* ignore */ }
  }

  function startDatentabellePolling(dtId: number) {
    stopDatentabellePolling();
    setDatentabelleLoading(true);
    datentabellePollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${dtId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.table_data) {
          setDatentabelle(data.table_data);
          setDatentabelleSources(data.sources || data.table_data.sources || []);
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
        const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle`, { credentials: "include" });
        if (res.ok) {
          const data = await res.json();
          if (data && data.status === "success" && data.table_data) {
            setDatentabelle(data.table_data);
            setDatentabelleSources(data.sources || data.table_data.sources || []);
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/generate`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.table_data) {
        setDatentabelle(data.table_data);
        setDatentabelleSources(data.sources || data.table_data.sources || []);
      }
    } catch { /* ignore */ }
  }

  async function deleteDatentabelle(id: number) {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/datentabelle/${id}`, { method: "DELETE", credentials: "include" });
      setDatentabelleList((prev) => prev.filter((d) => d.id !== id));
    } catch { /* ignore */ }
  }

  // ─── Sprachtraining Functions ────────────────────────────────────────────

  // Active sources for sprachtraining (max 3, from left panel checkboxes)
  const sprachActiveIds = selectedSourceIds.slice(0, 3);

  async function deleteGlossaryEntry(entryId: number) {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/glossary/${entryId}`, {
        method: "DELETE", credentials: "include",
      });
      setGlossary((prev) => prev.filter((e) => e.id !== entryId));
      loadGlossaryCount();
    } catch { /* ignore */ }
  }

  async function deleteAllGlossaryEntries() {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/glossary`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/glossary`, { credentials: "include" });
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/glossary/generate`, {
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
            const res2 = await fetch(`/api/ki-assistent/modules/${uuid}/glossary`, { credentials: "include" });
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercises/cloze`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercises/vocab-test`, {
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
      // Route by tool: Sprachtraining-only tools go to sprachView, Lerntools to studioView
      if (tool === "lernkarten" || (tool === "karteikarten" && mode === "glossar")) setSprachView("lk-learn");
      else if (tool === "lueckentext") setSprachView("cl-learn");
      else if (tool === "vokabeltest") setSprachView("vt-learn");
      else setStudioView(tool as StudioView);
    });
  }

  // ─── Exercise Sets Functions ──────────────────────────────────────────────

  async function loadExerciseSets(tool?: string) {
    try {
      const url = tool
        ? `/api/ki-assistent/modules/${uuid}/exercise-sets?tool=${tool}`
        : `/api/ki-assistent/modules/${uuid}/exercise-sets`;
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}`, { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setActiveSet(data.set);
      }
    } catch { /* ignore */ }
  }

  async function createExerciseSet(tool: string, mode: string, count: number, sourceUuid?: string) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets`, {
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
      await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}`, {
        method: "DELETE", credentials: "include",
      });
      loadExerciseSets(tool);
    } catch { /* ignore */ }
  }

  async function downloadExerciseSet(s: ExerciseSet) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${s.id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      const set = data.set as ExerciseSet;
      const items = set.items || [];
      const lines: string[] = [];
      lines.push(set.title);
      lines.push("=".repeat(set.title.length));
      lines.push("");
      items.forEach((item, i) => {
        lines.push(`${i + 1}. ${item.front}`);
        lines.push("");
        lines.push(`   ${item.back.replace(/\n/g, "\n   ")}`);
        if (item.back_en) {
          lines.push(`   EN: ${item.back_en}`);
        }
        if (item.extras?.word_parts) {
          lines.push(`   Wortzerlegung: ${item.extras.word_parts}`);
          if (item.extras.word_parts_explained) {
            lines.push(`     ${item.extras.word_parts_explained}`);
          }
        }
        if (item.extras?.example_sentence) {
          lines.push(`   Beispiel: „${item.extras.example_sentence}"`);
        }
        // List all sources/chips with their highlighted text
        const sources = item.sources?.length
          ? item.sources
          : (item.source_label ? [{ source_label: item.source_label, page_number: item.page_number, start_time: item.start_time, highlight_text: undefined }] : []);
        if (sources.length > 0) {
          lines.push(`   Quellen:`);
          sources.forEach((s) => {
            const label = s.page_number
              ? `, ${_chunkLabel(s.source_label, s.page_number, s.start_time)}`
              : "";
            lines.push(`     - ${s.source_label}${label}`);
            if (s.highlight_text) {
              lines.push(`       „${s.highlight_text.replace(/\n/g, " ").trim()}"`);
            }
          });
        }
        lines.push("");
      });
      const text = lines.join("\n");
      const safeTitle = (set.title || set.tool || "karteikarten").replace(/[^a-zA-Z0-9äöüÄÖÜß_-]+/g, "_").slice(0, 60);
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${safeTitle}_${set.id}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  }

  async function submitSingleAnswer(setId: number, itemId: number, correct: boolean, newRun = false) {
    try {
      await fetch(`/api/ki-assistent/modules/${uuid}/exercise-sets/${setId}/progress`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/streak`, { credentials: "include" });
      if (res.ok) setStreakInfo(await res.json());
    } catch { /* ignore */ }
  }

  async function loadGlossaryCount() {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/glossary-count`, { credentials: "include" });
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

  const isAdmin = auth?.is_admin ?? false;

  const sprachtrainingContent = (<div style={{ "--accent": "#9333EA", "--accent-rgb": "147,51,234" } as React.CSSProperties} className="flex flex-col flex-1 overflow-hidden">{(() => {
    switch (sprachView) {
      case "karteikarten":
        return (
          <VocabFlashcards
            entries={glossary}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
          />
        );
      case "lueckentext":
        return (
          <LueckentextView
            exercises={clozeExercises}
            loading={clozeLoading}
            onGenerate={generateCloze}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
          />
        );
      case "vokabeltest":
        return (
          <VokabeltestView
            questions={vocabQuestions}
            loading={vocabLoading}
            onGenerate={generateVocabTest}
            onBack={() => setSprachView("overview")}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
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
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
            category="sprachtraining"
          />
        );
      case "lk-learn":
        return activeSet ? (
          <LernkartenLearnView
            exerciseSet={activeSet}
            onBack={() => { setSprachView("lk-sets"); setActiveSet(null); refreshProgress(); }}
            onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
            onAskChat={(text) => handleAskChat(text)}
            onSourceClick={(filename, page, startTime, highlightText) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
            }}
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
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
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lernkarten", onClick: () => { setActiveSet(null); setSprachView("lk-sets"); } }]}
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
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
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
            onAskChat={(text) => handleAskChat(text)}
            onSourceClick={(filename, page, startTime, highlightText) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
            }}
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
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
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Lückentext", onClick: () => { setActiveSet(null); setSprachView("cl-sets"); } }]}
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
            onDownload={isAdmin ? downloadExerciseSet : undefined}
            sourceCount={selectedSourceIds.length}
            stats={pageStats}
            breadcrumbs={[{ label: "Studio", onClick: () => setSprachView("overview") }]}
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
            onAskChat={(text) => handleAskChat(text)}
            onSourceClick={(filename, page, startTime, highlightText) => {
              const src = sources.find((s) => s.filename === filename);
              if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
            }}
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
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
            breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setSprachView("overview"); } }, { label: "Begriffe-Quiz", onClick: () => { setActiveSet(null); setSprachView("vt-sets"); } }]}
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
      onOpenSource={(page, highlightText, startTime) => {
        const src = sources.find((s) => selectedSourceIds.includes(s.uuid));
        if (!src) return;
        if (_isMediaFile(src.filename) && startTime != null) {
          setPrevSelectedSourceIds(selectedSourceIds);
          setSelectedSourceIds([src.uuid]);
          setViewerSource({ uuid: src.uuid, filename: src.filename, page: 0, startTime, nonce: Date.now() });
          setPanels((prev) => ({ ...prev, quellen: true }));
        } else {
          handleOpenViewer(src, page, highlightText);
        }
      }}
      onDelete={deleteGlossaryEntry}
      onDeleteAll={deleteAllGlossaryEntries}
      stats={pageStats}
      showTranslation={sprachtrainingActive}
      feedback={glossaryFeedback}
      onDismissFeedback={() => setGlossaryFeedback(null)}
    />
  );

  const notizenContent = (
    <NotizenStudio
      notes={notes}
      onAdd={addNote}
      onDelete={deleteNote}
      onUpdateTitle={updateNoteTitle}
      sources={sources}
      activeSourceIds={selectedSourceIds}
      onPillClick={handlePillClick}
      pendingTitleIds={pendingTitleIds}
    />
  );

  async function addNote(content: string, sourceUuids?: string[]) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, source_uuids: sourceUuids ?? null }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        alert(_formatApiError(data) ?? "Notiz konnte nicht gespeichert werden.");
        return;
      }
      const note = await res.json();
      setNotes((prev) => [note, ...prev]);
      if (!note.title) _pollForNoteTitle(note.id);
    } catch { /* ignore */ }
  }

  async function _pollForNoteTitle(noteId: number) {
    setPendingTitleIds((prev) => { const next = new Set(prev); next.add(noteId); return next; });
    const clear = () => setPendingTitleIds((prev) => { const next = new Set(prev); next.delete(noteId); return next; });
    const delays = [3000, 4000, 6000, 8000, 10000]; // ~31s total
    for (const wait of delays) {
      await new Promise((r) => setTimeout(r, wait));
      try {
        const r = await fetch(`/api/ki-assistent/modules/${uuid}/notes`, { credentials: "include" });
        if (!r.ok) continue;
        const fresh = await r.json();
        const updated = fresh.find((n: { id: number; title?: string | null }) => n.id === noteId);
        if (updated?.title) {
          setNotes((cur) => cur.map((n) => n.id === noteId ? { ...n, title: updated.title } : n));
          clear();
          return;
        }
      } catch { /* keep polling */ }
    }
    clear();
  }

  async function deleteNote(noteId: number) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes/${noteId}`, {
        method: "DELETE", credentials: "include",
      });
      if (res.ok) setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch { /* ignore */ }
  }

  async function updateNoteTitle(noteId: number, title: string | null) {
    const prev = notes;
    setNotes((cur) => cur.map((n) => n.id === noteId ? { ...n, title } : n));
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes/${noteId}/title`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) setNotes(prev);
    } catch { setNotes(prev); }
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

  const openCount = [panels.quellen, panels.chat, panels.studio].filter(Boolean).length;
  const canDrag = openCount >= 2;

  if (!initialized) {
    return (
      <ProtectedRoute>
        <div className="flex flex-col overflow-hidden" style={{ height: "100vh" }}>
          {!hideHeader && <Header showLogout />}
          <div className="flex-1 flex items-center justify-center">
            <Spinner size="lg" />
          </div>
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="flex flex-col overflow-hidden mobile-flow" style={{ height: "100vh" }}>
        {!hideHeader && <Header showLogout />}

        {/* Topbar — Desktop only */}
        {!isMobile && (
          <div
            className="flex items-center px-5 flex-shrink-0 relative"
            style={{ height: 48 }}
          >
            <Link
              href="/workspaces"
              className="inline-flex items-center gap-1 text-xs font-medium transition-colors group flex-shrink-0"
              style={{ color: "var(--kb)" }}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-hover:-translate-x-0.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
              Zurück zur Übersicht
            </Link>
            <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <span className="text-base font-bold truncate px-16 pointer-events-auto select-text cursor-text" style={{ color: "var(--kb)" }}>
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
                  {/* Header ausblenden (nur Ersteller/Lecturer) */}
                  {isLecturer && (
                    <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: "1px solid var(--border)" }}>
                      <div>
                        <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Header ausblenden</p>
                        <p className="text-xs" style={{ color: "var(--muted)" }}>Nur auf dieser Workspace-Seite</p>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={hideHeader}
                        onClick={() => setHideHeader((v) => !v)}
                        className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                        style={{ backgroundColor: hideHeader ? "var(--kb)" : "#CBD5E1" }}
                      >
                        <span
                          className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                          style={{ transform: hideHeader ? "translateX(16px)" : "translateX(0)" }}
                        />
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab bar — Mobile only */}
        {isMobile && (
          <div className="flex-shrink-0" style={{ backgroundColor: "var(--surface)" }}>
            <div className="hide-on-short flex items-center gap-2 px-3 pt-2 pb-1 relative">
              <Link
                href="/workspaces"
                className="inline-flex items-center justify-center w-7 h-7 flex-shrink-0 transition-colors group"
                style={{ color: "var(--kb)" }}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-hover:-translate-x-0.5"><path d="M19 12H5M12 5l-7 7 7 7" /></svg>
              </Link>
              <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <span className="text-sm font-bold truncate px-12 pointer-events-auto select-text cursor-text" style={{ color: "var(--text)" }}>
                  {moduleDetail?.title ?? ""}
                </span>
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
                    {isLecturer && (
                      <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: "1px solid var(--border)" }}>
                        <div>
                          <p className="text-sm font-medium" style={{ color: "var(--text)" }}>Header ausblenden</p>
                          <p className="text-xs" style={{ color: "var(--muted)" }}>Nur auf dieser Workspace-Seite</p>
                        </div>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={hideHeader}
                          onClick={() => setHideHeader((v) => !v)}
                          className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent transition-colors duration-200"
                          style={{ backgroundColor: hideHeader ? "var(--kb)" : "#CBD5E1" }}
                        >
                          <span
                            className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
                            style={{ transform: hideHeader ? "translateX(16px)" : "translateX(0)" }}
                          />
                        </button>
                      </div>
                    )}
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
                  className="flex-1 py-3 compact-on-short text-sm font-medium transition-colors relative"
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
          className="flex flex-1 overflow-hidden mobile-flow"
          style={{ padding: 8, gap: 0, backgroundColor: "var(--bg)" }}
        >
          {isMobile ? (
            /* Mobile: single panel, switched via activeTab */
            <MinimizeContext.Provider value={() => setActiveTab("chat")}>
              <div
                className="flex flex-col flex-1 overflow-hidden rounded-2xl mobile-flow mobile-center"
                style={{ backgroundColor: "var(--surface)", boxShadow: "0 1px 4px rgba(0,0,0,0.07)" }}
              >
                {activeTab === "quellen" ? (
                  viewerSource ? (
                    _isMediaFile(viewerSource.filename) ? (
                      <MediaPlayer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onMinimize={() => setActiveTab("chat")} canDownload={isLecturer || isAdmin} onSaveNote={addNote} />
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
                      onRetrySource={handleRetrySource}
                      onUpload={handleUpload}
                      uploadProgress={uploadProgress}
                      uploadErrors={uploadErrors}
                      onDismissUploadErrors={() => setUploadErrors([])}
                      isLecturer={isLecturer}
                      onMinimize={() => setActiveTab("chat")}
                      moduleUuid={uuid}
                    />
                  )
                ) : activeTab === "chat" ? (
                  <ChatPanel
                    messages={messages}
                    activeSourceIds={activeSourceIds}
                    sources={sources}
                    loading={chatLoading}
                    onSend={(v) => sendChatMessage(v)}
                    onSendPrompt={(text) => sendChatMessage(text)}
                    onPillClick={handlePillClick}
                    moduleReady={moduleDetail?.status === "ready"}
                    onClear={() => { const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : ""; fetch(`/api/ki-assistent/modules/${uuid}/messages${eidParam}`, { method: "DELETE", credentials: "include" }); setMessages([]); }}
                    externalTextareaRef={chatTextareaRef}
                    onSaveNote={addNote}
                    registerSetInput={registerChatSetInput}
                  />
                ) : sprachView !== "overview" ? (
                  sprachtrainingContent
                ) : studioView === "overview" ? (
                  <StudioOverview onSelect={handleStudioSelect} onMinimize={() => setActiveTab("chat")} sprachtrainingActive={sprachtrainingActive} sprachtrainingContent={sprachtrainingContent} glossarContent={glossarContent} notizenContent={notizenContent} moduleUuid={uuid} statsVersion={statsVersion} onNavigateToSet={handleNavigateToSet} onSprachNavigate={handleSprachNavigate} activeSourceCount={selectedSourceIds.length} sprachView={sprachView} requestedTab={studioTabRequest} sources={sources} selectedSourceIds={selectedSourceIds} onPillClick={handlePillClick} />
                ) : activeSet && activeSet.tool === "karteikarten" ? (
                  <LernkartenLearnView
                    exerciseSet={activeSet}
                    onBack={() => { setActiveSet(null); refreshProgress(); }}
                    onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                    onAskChat={(text) => handleAskChat(text, true)}
                    onSourceClick={(filename, page, startTime, highlightText) => {
                      const src = sources.find((s) => s.filename === filename);
                      if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
                    }}
                    breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Karteikarten", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                  />
                ) : activeSet && activeSet.tool === "quiz" ? (
                  <MCExerciseView
                    exerciseSet={activeSet}
                    tool="quiz"
                    onBack={() => { setActiveSet(null); refreshProgress(); }}
                    onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                    onAskChat={(text) => handleAskChat(text, true)}
                    onSourceClick={(filename, page, startTime, highlightText) => {
                      const src = sources.find((s) => s.filename === filename);
                      if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
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
                    onDownload={isAdmin ? downloadExerciseSet : undefined}
                    sourceCount={selectedSourceIds.length}
                    stats={pageStats}
                    breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                  />
                ) : studioView === "notizen" ? (
                  <NotizenStudio
                    notes={notes}
                    onAdd={addNote}
                    onDelete={deleteNote}
                    onUpdateTitle={updateNoteTitle}
                    onBack={() => setStudioView("overview")}
                    sources={sources}
                    activeSourceIds={selectedSourceIds}
                    onPillClick={handlePillClick}
                    stats={pageStats}
                    breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                    pendingTitleIds={pendingTitleIds}
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
                  <MindmapStudio mindmap={mindmapData} loading={mindmapLoading} onGenerate={generateMindmap} onBack={() => setStudioView("overview")} savedList={mindmapList} onSelect={selectMindmap} onDelete={deleteMindmap} sourceCount={selectedSourceIds.length} sources={sources} onPillClick={handlePillClick} stats={pageStats} breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]} />
                ) : studioView === "quiz" ? (
                  <ExerciseSetsOverview
                    title="Quiz"
                    sets={exerciseSets.filter((s) => s.tool === "quiz")}
                    onBack={() => setStudioView("overview")}
                    onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                    onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
                    onDelete={(id) => deleteExerciseSet(id, "quiz")}
                    onDownload={isAdmin ? downloadExerciseSet : undefined}
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
                    <MediaPlayer source={viewerSource} onClose={handleCloseViewer} moduleUuid={uuid} onMinimize={() => togglePanel("quellen")} canDownload={isLecturer || isAdmin} onSaveNote={addNote} />
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
                    onRetrySource={handleRetrySource}
                    onUpload={handleUpload}
                    uploadProgress={uploadProgress}
                    uploadErrors={uploadErrors}
                    onDismissUploadErrors={() => setUploadErrors([])}
                    isLecturer={isLecturer}
                    onMinimize={() => togglePanel("quellen")}
                    moduleUuid={uuid}
                  />
                )}
              </div>

              {/* Drag handle 1 */}
              <div
                className="group flex-shrink-0 flex items-center justify-center"
                style={{ width: 8, cursor: canDrag ? "col-resize" : "default" }}
                onMouseDown={(e) => canDrag && startDrag(1, e)}
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
                    onSend={(v) => sendChatMessage(v)}
                    onSendPrompt={(text) => sendChatMessage(text)}
                    onPillClick={handlePillClick}
                    moduleReady={moduleDetail?.status === "ready"}
                    onClear={() => { const eidParam = enrollmentId ? `?enrollment_id=${enrollmentId}` : ""; fetch(`/api/ki-assistent/modules/${uuid}/messages${eidParam}`, { method: "DELETE", credentials: "include" }); setMessages([]); }}
                    externalTextareaRef={chatTextareaRef}
                    onSaveNote={addNote}
                    onMinimize={() => togglePanel("chat")}
                    registerSetInput={registerChatSetInput}
                  />
                )}
              </div>

              {studioEnabled && (
                <>
                  {/* Drag handle 2 */}
                  <div
                    className="group flex-shrink-0 flex items-center justify-center"
                    style={{ width: 8, cursor: canDrag ? "col-resize" : "default" }}
                    onMouseDown={(e) => canDrag && startDrag(2, e)}
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
                        <StudioOverview onSelect={handleStudioSelect} onMinimize={() => togglePanel("studio")} sprachtrainingActive={sprachtrainingActive} sprachtrainingContent={sprachtrainingContent} glossarContent={glossarContent} notizenContent={notizenContent} moduleUuid={uuid} statsVersion={statsVersion} onNavigateToSet={handleNavigateToSet} onSprachNavigate={handleSprachNavigate} activeSourceCount={selectedSourceIds.length} sprachView={sprachView} requestedTab={studioTabRequest} sources={sources} selectedSourceIds={selectedSourceIds} onPillClick={handlePillClick} />
                      ) : activeSet && activeSet.tool === "karteikarten" ? (
                        <LernkartenLearnView
                          exerciseSet={activeSet}
                          onBack={() => { setActiveSet(null); refreshProgress(); }}
                          onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                          onAskChat={(text) => handleAskChat(text)}
                          onSourceClick={(filename, page, startTime, highlightText) => {
                            const src = sources.find((s) => s.filename === filename);
                            if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
                          }}
                          breadcrumbs={[{ label: "Studio", onClick: () => { setActiveSet(null); setStudioView("overview"); } }, { label: "Karteikarten", onClick: () => { setActiveSet(null); refreshProgress(); } }]}
                        />
                      ) : activeSet && activeSet.tool === "quiz" ? (
                        <MCExerciseView
                          exerciseSet={activeSet}
                          tool="quiz"
                          onBack={() => { setActiveSet(null); refreshProgress(); }}
                          onAnswer={(itemId, correct, newRun) => submitSingleAnswer(activeSet.id, itemId, correct, newRun)}
                          onAskChat={(text) => handleAskChat(text, true)}
                          onSourceClick={(filename, page, startTime, highlightText) => {
                            const src = sources.find((s) => s.filename === filename);
                            if (src) handlePillClick(src.uuid, page, filename, highlightText, startTime);
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
                          onDownload={isAdmin ? downloadExerciseSet : undefined}
                          sourceCount={selectedSourceIds.length}
                          stats={pageStats}
                          breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                        />
                      ) : studioView === "notizen" ? (
                        <NotizenStudio
                          notes={notes}
                          onAdd={addNote}
                          onDelete={deleteNote}
                          onUpdateTitle={updateNoteTitle}
                          onBack={() => setStudioView("overview")}
                          sources={sources}
                          activeSourceIds={selectedSourceIds}
                          onPillClick={handlePillClick}
                          stats={pageStats}
                          breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]}
                          pendingTitleIds={pendingTitleIds}
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
                        <MindmapStudio mindmap={mindmapData} loading={mindmapLoading} onGenerate={generateMindmap} onBack={() => setStudioView("overview")} savedList={mindmapList} onSelect={selectMindmap} onDelete={deleteMindmap} sourceCount={selectedSourceIds.length} sources={sources} onPillClick={handlePillClick} stats={pageStats} breadcrumbs={[{ label: "Studio", onClick: () => setStudioView("overview") }]} />
                      ) : studioView === "quiz" ? (
                        <ExerciseSetsOverview
                          title="Quiz"
                          sets={exerciseSets.filter((s) => s.tool === "quiz")}
                          onBack={() => setStudioView("overview")}
                          onSelect={(s) => { setActiveSet(s); loadExerciseSet(s.id); }}
                          onCreate={() => { setCreateSetTool("quiz"); setShowCreateModal(true); }}
                          onDelete={(id) => deleteExerciseSet(id, "quiz")}
                          onDownload={isAdmin ? downloadExerciseSet : undefined}
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
