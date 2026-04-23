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
import type { Source, StudioView, SprachtrainingView, StudentStats } from "../../_types";
import { LerntoolsGrid } from "../sprachtraining/LerntoolsGrid";
import { RecentActivities } from "./RecentActivities";
import { StudioTabs } from "./StudioTabs";

const dynamicLoader = () => (
  <div className="flex-1 flex items-center justify-center p-6">
    <Spinner size="md" />
  </div>
);

const StudentStatsView = dynamic(
  () => import("../sprachtraining/StudentStatsView").then((m) => ({ default: m.StudentStatsView })),
  { loading: dynamicLoader, ssr: false },
);

const ZeitplanView = dynamic(
  () => import("./ZeitplanView").then((m) => ({ default: m.ZeitplanView })),
  { loading: dynamicLoader, ssr: false },
);

interface StudioOverviewProps {
  onSelect: (v: StudioView) => void;
  onMinimize: () => void;
  sprachtrainingActive: boolean;
  sprachtrainingContent?: React.ReactNode;
  glossarContent?: React.ReactNode;
  notizenContent?: React.ReactNode;
  moduleUuid: string;
  statsVersion: number;
  onNavigateToSet?: (setId: number, tool: string, mode: string) => void;
  onSprachNavigate?: (view: SprachtrainingView) => void;
  activeSourceCount?: number;
  sprachView?: string;
  requestedTab?: { tab: "tools" | "glossar" | "notizen" | "statistik" | "zeitplan"; nonce: number } | null;
  sources: Source[];
  selectedSourceIds: string[];
  onPillClick?: (sourceUuid: string, page: number, filename: string, sourceText?: string, startTime?: number) => void;
  hideHeader?: boolean;
}

type StudioTab = "tools" | "sprachtraining" | "glossar" | "notizen" | "statistik" | "zeitplan";

export function StudioOverview({
  onSelect,
  onMinimize,
  sprachtrainingActive,
  sprachtrainingContent,
  glossarContent,
  notizenContent,
  moduleUuid,
  statsVersion,
  onNavigateToSet,
  onSprachNavigate,
  activeSourceCount,
  sprachView,
  requestedTab,
  sources,
  selectedSourceIds,
  onPillClick,
  hideHeader,
}: StudioOverviewProps) {
  const [studioTab, _setStudioTab] = useState<StudioTab>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("kis-studio-tab");
      if (saved && ["tools", "glossar", "notizen", "statistik", "zeitplan"].includes(saved))
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
    fetch(`/api/ki-assistent/modules/${moduleUuid}/stats`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setStudentStats(data);
      })
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

  void activeSourceCount;

  useEffect(() => {
    if (studioTab === "sprachtraining" && (!sprachView || sprachView === "overview")) {
      setStudioTab("tools");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sprachView, studioTab]);

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
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Studio
          </span>
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
      )}

      <StudioTabs
        tabs={[
          { key: "tools" as const, label: "Tools" },
          { key: "glossar" as const, label: "Glossar" },
          { key: "notizen" as const, label: "Notizen" },
          { key: "statistik" as const, label: "Statistik" },
          { key: "zeitplan" as const, label: "Zeitplan" },
        ]}
        active={effectiveTab === "sprachtraining" ? "tools" : effectiveTab}
        onSelect={(k) => setStudioTab(k as StudioTab)}
      />

      {studioTab === "tools" && (
        <div className="flex-1 overflow-y-auto flex flex-col">
          <div className="px-3 pt-3 pb-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
              Lerntools
            </span>
          </div>
          <LerntoolsGrid tiles={lerntoolsTiles} onSelect={(key) => onSelect(key as StudioView)} />

          {sprachtrainingActive && (
            <>
              <div className="px-3 pb-1">
                <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
                  Fachsprachentraining
                </span>
              </div>
              <LerntoolsGrid
                tiles={sprachTiles}
                onSelect={(key) => {
                  if (onSprachNavigate) {
                    onSprachNavigate(key as SprachtrainingView);
                    setStudioTab("sprachtraining");
                  }
                }}
              />
            </>
          )}

          <RecentActivities moduleUuid={moduleUuid} onNavigateToSet={onNavigateToSet} refreshKey={statsVersion} />
        </div>
      )}

      {studioTab === "sprachtraining" && (
        <div className="flex-1 overflow-hidden flex flex-col">{sprachtrainingContent}</div>
      )}

      {studioTab === "glossar" && (
        <div className="flex-1 overflow-hidden flex flex-col">{glossarContent}</div>
      )}

      {studioTab === "notizen" && (
        <div className="flex-1 overflow-hidden flex flex-col">{notizenContent}</div>
      )}

      {studioTab === "statistik" && (
        <StudentStatsView
          stats={studentStats}
          loading={statsLoading}
          moduleUuid={moduleUuid}
          onNavigateToSet={onNavigateToSet}
          sprachtrainingActive={sprachtrainingActive}
        />
      )}

      {studioTab === "zeitplan" && (
        <div className="flex-1 overflow-hidden flex flex-col">
          <ZeitplanView
            moduleUuid={moduleUuid}
            sources={sources}
            selectedSourceIds={selectedSourceIds}
            onPillClick={onPillClick}
          />
        </div>
      )}
    </div>
  );
}
