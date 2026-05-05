"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { GearSix, CaretUp, CaretDown } from "@phosphor-icons/react";
import { SettingsMenu } from "./SettingsMenu";
import type { PanelKey, TranscriptTranslationMode, TranscriptDefaultLang } from "../../_types";

interface WorkspaceTopbarProps {
  isMobile: boolean;
  title: string;
  // Settings modal
  showSettings: boolean;
  onToggleSettings: () => void;
  onCloseSettings: () => void;
  studioEnabled: boolean;
  onToggleStudio: () => void;
  language_trainingActive: boolean;
  onToggleLanguageTraining: () => void;
  isLecturer: boolean;
  isOwner: boolean;
  hideHeader: boolean;
  onToggleHideHeader: () => void;
  translationMode: TranscriptTranslationMode;
  onChangeTranslationMode: (mode: TranscriptTranslationMode) => void;
  transcriptDefaultLang: TranscriptDefaultLang;
  onChangeTranscriptDefaultLang: (lang: TranscriptDefaultLang) => void;
  // Mobile tabs
  activeTab: PanelKey;
  setActiveTab: (k: PanelKey) => void;
}

const BackArrow = ({ size }: { size: 12 | 14 }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="transition-transform group-hover:-translate-x-0.5">
    <path d="M19 12H5M12 5l-7 7 7 7" />
  </svg>
);

export function WorkspaceTopbar(props: WorkspaceTopbarProps) {
  const {
    isMobile, title,
    showSettings, onToggleSettings, onCloseSettings,
    studioEnabled, onToggleStudio,
    language_trainingActive, onToggleLanguageTraining,
    isLecturer, isOwner, hideHeader, onToggleHideHeader,
    translationMode, onChangeTranslationMode,
    transcriptDefaultLang, onChangeTranscriptDefaultLang,
    activeTab, setActiveTab,
  } = props;
  const t = useTranslations("workspace.detail.topbar");
  const tPanels = useTranslations("workspace.detail.panels");

  const settingsModal = (
    <SettingsMenu
      open={showSettings}
      onClose={onCloseSettings}
      studioEnabled={studioEnabled}
      onToggleStudio={onToggleStudio}
      language_trainingActive={language_trainingActive}
      onToggleLanguageTraining={onToggleLanguageTraining}
      isOwner={isOwner}
      translationMode={translationMode}
      onChangeTranslationMode={onChangeTranslationMode}
      transcriptDefaultLang={transcriptDefaultLang}
      onChangeTranscriptDefaultLang={onChangeTranscriptDefaultLang}
    />
  );

  const settingsButton = (
    <button
      type="button"
      onClick={onToggleSettings}
      className={`w-7 h-7 flex items-center justify-center rounded-full ${showSettings ? "text-white" : "btn-icon"}`}
      style={{ backgroundColor: showSettings ? "var(--kb)" : "var(--surface-dim)" }}
      title={t("settings")}
    >
      <GearSix size={17} weight={showSettings ? "fill" : "regular"} />
    </button>
  );

  const headerToggleButton = isLecturer ? (
    <button
      type="button"
      onClick={onToggleHideHeader}
      className={`w-7 h-7 flex items-center justify-center rounded-full ${hideHeader ? "text-white" : "btn-icon"}`}
      style={{ backgroundColor: hideHeader ? "var(--kb)" : "var(--surface-dim)" }}
      title={hideHeader ? t("showHeader") : t("hideHeader")}
      aria-label={hideHeader ? t("showHeader") : t("hideHeader")}
      aria-pressed={hideHeader}
    >
      {hideHeader ? <CaretDown size={16} weight="bold" /> : <CaretUp size={16} weight="bold" />}
    </button>
  ) : null;

  if (!isMobile) {
    return (
      <>
        <div className="flex items-center px-5 flex-shrink-0 relative" style={{ height: 48 }}>
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-xs font-medium transition-colors group flex-shrink-0"
            style={{ color: "var(--kb)" }}
          >
            <BackArrow size={12} />
            {t("backToOverview")}
          </Link>
          <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <h1 className="text-lg font-bold truncate px-16 pointer-events-auto select-text cursor-text" style={{ color: "var(--kb)" }}>
              {title}
            </h1>
          </span>
          <div className="flex items-center gap-1.5 ml-auto">
            {headerToggleButton}
            {settingsButton}
          </div>
        </div>
        {settingsModal}
      </>
    );
  }

  return (
    <div className="flex-shrink-0" style={{ backgroundColor: "var(--surface)" }}>
      <div className="hide-on-short flex items-center gap-2 px-3 pt-2 pb-1 relative">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-xs font-medium flex-shrink-0 transition-colors group"
          style={{ color: "var(--kb)" }}
        >
          <BackArrow size={12} />
          {t("back")}
        </Link>
        <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span className="text-sm font-bold truncate px-12 pointer-events-auto select-text cursor-text" style={{ color: "var(--foreground)" }}>
            {title}
          </span>
        </span>
        <div className="flex items-center gap-1.5 ml-auto">
          {headerToggleButton}
          {settingsButton}
        </div>
      </div>
      <div className="flex" style={{ borderBottom: "1px solid var(--border)" }}>
        {(["quellen", "chat", ...(studioEnabled ? ["studio"] : [])] as PanelKey[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveTab(key)}
            className="flex-1 py-3 compact-on-short text-sm font-medium transition-colors relative"
            style={{ color: activeTab === key ? "var(--kb)" : "var(--muted)", background: "none", border: "none" }}
          >
            {key === "quellen" ? tPanels("sources") : key === "chat" ? tPanels("chat") : tPanels("studio")}
            {activeTab === key && (
              <span className="absolute bottom-0 left-0 right-0" style={{ height: 2, backgroundColor: "var(--kb)", display: "block" }} />
            )}
          </button>
        ))}
      </div>
      {settingsModal}
    </div>
  );
}
