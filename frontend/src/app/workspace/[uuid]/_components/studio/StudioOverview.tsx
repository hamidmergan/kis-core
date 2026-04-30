"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  SidebarSimple,
  Cards,
  Question,
  Table,
  TreeStructure,
  BookOpenText,
  TextAa,
  Exam,
} from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { Source, StudioView, LanguageTrainingView, StudentStats } from "../../_types";
import { LerntoolsGrid } from "../language_training/LerntoolsGrid";
import { RecentActivities } from "./RecentActivities";
import { StudioTabs } from "./StudioTabs";

const dynamicLoader = () => (
  <div className="flex-1 flex items-center justify-center p-6">
    <Spinner size="md" />
  </div>
);

const StudentStatsView = dynamic(
  () => import("../language_training/StudentStatsView").then((m) => ({ default: m.StudentStatsView })),
  { loading: dynamicLoader, ssr: false },
);

const ScheduleView = dynamic(
  () => import("./ScheduleView").then((m) => ({ default: m.ScheduleView })),
  { loading: dynamicLoader, ssr: false },
);

interface StudioOverviewProps {
  onSelect: (v: StudioView) => void;
  onMinimize: () => void;
  language_trainingActive: boolean;
  language_trainingContent?: React.ReactNode;
  glossaryContent?: React.ReactNode;
  notesContent?: React.ReactNode;
  workspaceUuid: string;
  statsVersion: number;
  onNavigateToSet?: (setId: number, tool: string, mode: string) => void;
  onSprachNavigate?: (view: LanguageTrainingView) => void;
  activeSourceCount?: number;
  langTrainingView?: string;
  requestedTab?: { tab: "tools" | "glossary" | "notes" | "statistik" | "schedule"; nonce: number } | null;
  sources: Source[];
  selectedSourceIds: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  hideHeader?: boolean;
}

type StudioTab = "tools" | "language_training" | "glossary" | "notes" | "statistik" | "schedule";

export function StudioOverview({
  onSelect,
  onMinimize,
  language_trainingActive,
  language_trainingContent,
  glossaryContent,
  notesContent,
  workspaceUuid,
  statsVersion,
  onNavigateToSet,
  onSprachNavigate,
  activeSourceCount,
  langTrainingView,
  requestedTab,
  sources,
  selectedSourceIds,
  onPillClick,
  hideHeader,
}: StudioOverviewProps) {
  const [studioTab, _setStudioTab] = useState<StudioTab>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("kis-studio-tab");
      if (saved && ["tools", "glossary", "notes", "statistik", "schedule"].includes(saved))
        return saved as StudioTab;
    }
    return "tools";
  });
  const setStudioTab = (tab: StudioTab) => {
    _setStudioTab(tab);
    sessionStorage.setItem("kis-studio-tab", tab);
  };

  const [studentStats, setStudentStats] = useState<StudentStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  const refreshStats = useCallback(() => {
    setStatsLoading(true);
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/stats`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setStudentStats(data);
      })
      .catch(() => {})
      .finally(() => setStatsLoading(false));
  }, [workspaceUuid]);

  useEffect(() => {
    if (studioTab === "statistik") refreshStats();
  }, [studioTab, workspaceUuid, refreshStats, statsVersion]);

  const lerntoolsTiles = [
    { key: "karteikarten" as const, Icon: Cards, label: "Karteikarten", iconBg: "rgba(220,252,231,0.7)", iconColor: "var(--success-strong)" },
    { key: "quiz" as const, Icon: Question, label: "Quiz", iconBg: "rgba(254,249,195,0.7)", iconColor: "#A16207" },
    { key: "data_table" as const, Icon: Table, label: "Datentabelle", iconBg: "rgba(255,237,213,0.7)", iconColor: "#C2410C" },
    { key: "mindmap" as const, Icon: TreeStructure, label: "Mindmap", iconBg: "rgba(236,254,255,0.7)", iconColor: "#0E7490" },
  ];

  const langTrainingTiles = [
    { key: "lk-sets" as const, Icon: BookOpenText, label: "Lernkarten", iconBg: "rgba(245,235,220,0.7)", iconColor: "#78350F" },
    { key: "cl-sets" as const, Icon: TextAa, label: "Lückentext", iconBg: "rgba(254,226,226,0.7)", iconColor: "var(--error-strong)" },
    { key: "vt-sets" as const, Icon: Exam, label: "Begriffe-Quiz", iconBg: "rgba(237,233,254,0.7)", iconColor: "#534AB7" },
  ];

  void activeSourceCount;

  useEffect(() => {
    if (studioTab === "language_training" && (!langTrainingView || langTrainingView === "overview")) {
      setStudioTab("tools");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [langTrainingView, studioTab]);

  useEffect(() => {
    if (requestedTab) setStudioTab(requestedTab.tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestedTab?.nonce]);

  const effectiveTab = studioTab;

  return (
    <div className="flex flex-col h-full">
      {!hideHeader && (
        <div
          className="flex items-center justify-between px-4 py-3 flex-shrink-0"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span className="text-base font-semibold" style={{ color: "var(--foreground)" }}>
            Studio
          </span>
          <button
            type="button"
            onClick={onMinimize}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title="Panel minimieren"
          >
            <SidebarSimple size={13} style={{ transform: "scaleX(-1)" }} />
          </button>
        </div>
      )}

      <StudioTabs
        tabs={[
          { key: "tools" as const, label: "Tools" },
          { key: "glossary" as const, label: "Glossar" },
          { key: "notes" as const, label: "Notizen" },
          { key: "statistik" as const, label: "Statistik" },
          { key: "schedule" as const, label: "Zeitplan" },
        ]}
        active={effectiveTab === "language_training" ? "tools" : effectiveTab}
        onSelect={(k) => setStudioTab(k as StudioTab)}
      />

      {studioTab === "tools" && (
        <div className="flex-1 overflow-y-auto flex flex-col">
          <div className="px-3 pt-3 pb-1">
            <span className="text-xs font-semibold uppercase tracking-wider" >
              Lerntools
            </span>
          </div>
          <LerntoolsGrid tiles={lerntoolsTiles} onSelect={(key) => onSelect(key as StudioView)} />

          {language_trainingActive && (
            <>
              <div className="px-3 pb-1">
                <span className="text-xs font-semibold uppercase tracking-wider" >
                  Fachsprachentraining
                </span>
              </div>
              <LerntoolsGrid
                tiles={langTrainingTiles}
                onSelect={(key) => {
                  if (onSprachNavigate) {
                    onSprachNavigate(key as LanguageTrainingView);
                    setStudioTab("language_training");
                  }
                }}
              />
            </>
          )}

          <RecentActivities workspaceUuid={workspaceUuid} onNavigateToSet={onNavigateToSet} refreshKey={statsVersion} />
        </div>
      )}

      {studioTab === "language_training" && (
        <div className="flex-1 overflow-hidden flex flex-col">{language_trainingContent}</div>
      )}

      {studioTab === "glossary" && (
        <div className="flex-1 overflow-hidden flex flex-col">{glossaryContent}</div>
      )}

      {studioTab === "notes" && (
        <div className="flex-1 overflow-hidden flex flex-col">{notesContent}</div>
      )}

      {studioTab === "statistik" && (
        <StudentStatsView
          stats={studentStats}
          loading={statsLoading}
          workspaceUuid={workspaceUuid}
          onNavigateToSet={onNavigateToSet}
          language_trainingActive={language_trainingActive}
        />
      )}

      {studioTab === "schedule" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <ScheduleView
            workspaceUuid={workspaceUuid}
            sources={sources}
            selectedSourceIds={selectedSourceIds}
            onPillClick={onPillClick}
          />
        </div>
      )}
    </div>
  );
}
