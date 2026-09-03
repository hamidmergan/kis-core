"use client";

import React from "react";
import { useTranslations } from "next-intl";
import { GearSix, Eye, EyeSlash } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import { SettingsMenu } from "./SettingsMenu";
import type { PanelKey } from "../../_types";

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
  /** Sprachtrainer offered on this platform at all (admin setting). */
  languageTrainingAvailable: boolean;
  onToggleLanguageTraining: () => void;
  /** Personal decision whether the released language trainer is shown. */
  languageTrainingOptIn: boolean;
  onToggleLanguageTrainingOptIn: () => void;
  isOwner: boolean;
  /** Switch offered at all: owners always, enrolled people only in the demo course. */
  canPreview: boolean;
  previewOn: boolean;
  /** true: previews the owner side, false: the owner previews the student side. */
  previewsOwnerSide: boolean;
  onTogglePreview: () => void;
  onStartTour: () => void;
  transcriptTargetLang: string;
  onChangeTranscriptTargetLang: (lang: string) => void;
  popupTranslateLang: string;
  onChangePopupTranslateLang: (lang: string) => void;
  // Mobile tabs
  activeTab: PanelKey;
  setActiveTab: (k: PanelKey) => void;
  // Language level diagnosis
  languageLevel?: string | null;
  onResetLanguageLevel?: () => void | Promise<void>;
}

export function WorkspaceTopbar(props: WorkspaceTopbarProps) {
  const {
    isMobile, title,
    showSettings, onToggleSettings, onCloseSettings,
    studioEnabled, onToggleStudio,
    language_trainingActive, languageTrainingAvailable, onToggleLanguageTraining,
    languageTrainingOptIn, onToggleLanguageTrainingOptIn,
    isOwner, canPreview, previewOn, previewsOwnerSide, onTogglePreview, onStartTour,
    transcriptTargetLang, onChangeTranscriptTargetLang,
    popupTranslateLang, onChangePopupTranslateLang,
    activeTab, setActiveTab,
    languageLevel, onResetLanguageLevel,
  } = props;
  const t = useTranslations("workspace.detail.topbar");
  const tPanels = useTranslations("workspace.detail.panels");
  const tHeader = useTranslations("header");

  const settingsModal = (
    <SettingsMenu
      open={showSettings}
      onClose={onCloseSettings}
      studioEnabled={studioEnabled}
      onToggleStudio={onToggleStudio}
      language_trainingActive={language_trainingActive}
      languageTrainingAvailable={languageTrainingAvailable}
      onToggleLanguageTraining={onToggleLanguageTraining}
      languageTrainingOptIn={languageTrainingOptIn}
      onToggleLanguageTrainingOptIn={onToggleLanguageTrainingOptIn}
      isOwner={isOwner}
      onStartTour={onStartTour}
      transcriptTargetLang={transcriptTargetLang}
      onChangeTranscriptTargetLang={onChangeTranscriptTargetLang}
      popupTranslateLang={popupTranslateLang}
      onChangePopupTranslateLang={onChangePopupTranslateLang}
      languageLevel={languageLevel}
      onResetLanguageLevel={onResetLanguageLevel}
    />
  );

  const settingsButton = (
    <button
      type="button"
      onClick={onToggleSettings}
      data-tour="module-settings"
      className={`w-7 h-7 flex items-center justify-center rounded-full ${showSettings ? "text-white" : "btn-icon"}`}
      style={{ backgroundColor: showSettings ? "var(--kb)" : "var(--surface-dim)" }}
      title={t("settings")}
    >
      <GearSix size={17} weight={showSettings ? "fill" : "regular"} />
    </button>
  );

  // Says what you get after pressing, not what you are looking at now.
  const previewLabel = previewsOwnerSide
    ? previewOn ? t("previewLeaveOwner") : t("previewOwner")
    : previewOn ? t("previewLeaveStudent") : t("previewStudent");

  const previewButton = canPreview ? (
    <button
      type="button"
      onClick={onTogglePreview}
      className={`w-7 h-7 flex items-center justify-center rounded-full ${previewOn ? "text-white" : "btn-icon"}`}
      style={{ backgroundColor: previewOn ? "var(--kb)" : "var(--surface-dim)" }}
      title={previewLabel}
      aria-label={previewLabel}
      aria-pressed={previewOn}
      data-tour="preview-toggle"
    >
      {previewOn ? <EyeSlash size={16} weight="bold" /> : <Eye size={16} weight="bold" />}
    </button>
  ) : null;

  // Without this line the inert controls read as a broken page.
  const previewBanner = previewOn ? (
    <div
      className="px-5 py-1.5 text-xs flex items-center gap-2"
      style={{
        backgroundColor: "rgba(var(--kb-rgb),0.10)",
        borderTop: "1px dashed var(--muted-soft)",
        borderBottom: "1px dashed var(--muted-soft)",
      }}
      data-tour="preview-banner"
    >
      <Eye size={14} weight="bold" style={{ color: "var(--kb)", flexShrink: 0 }} />
      <span>{previewsOwnerSide ? t("previewBannerOwner") : t("previewBannerStudent")}</span>
    </div>
  ) : null;

  // A module has no blue bar any more, so the way back home hangs on the logo here.
  const logo = (
    <Link
      href="/"
      aria-label={tHeader("homeAria")}
      title={tHeader("homeAria")}
      className="flex items-center gap-1.5 flex-shrink-0 no-underline logo-link"
      style={{ color: "var(--kb)" }}
    >
      <span className="text-xl font-semibold tracking-tight">KIS</span>
      {process.env.NODE_ENV === "development" && (
        <span className="text-2xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: "#532bdd", color: "#fff" }}>
          DEV
        </span>
      )}
    </Link>
  );

  if (!isMobile) {
    return (
      <>
        <div className="flex items-center px-5 flex-shrink-0 relative" style={{ height: 48 }}>
          {logo}
          <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
            {/* The centred title lies above the buttons, so it is capped short of them and no longer swallows their taps. */}
            <h1 className="text-lg font-bold truncate pointer-events-auto select-text cursor-text" style={{ color: "var(--kb)", maxWidth: "calc(100% - 12rem)" }}>
              {title}
            </h1>
          </span>
          <div className="flex items-center gap-1.5 ml-auto">
            {previewButton}
            {settingsButton}
          </div>
        </div>
        {previewBanner}
        {settingsModal}
      </>
    );
  }

  return (
    <div className="flex-shrink-0" style={{ backgroundColor: "var(--surface)" }}>
      <div className="hide-on-short flex items-center gap-2 px-3 pt-2 pb-1 relative">
        {logo}
        <span className="absolute inset-0 flex items-center justify-center pointer-events-none">
          {/* The centred title lies above the buttons, so it is capped short of them and no longer swallows their taps. */}
          <span className="text-sm font-bold truncate pointer-events-auto select-text cursor-text" style={{ color: "var(--foreground)", maxWidth: "calc(100% - 11rem)" }}>
            {title}
          </span>
        </span>
        <div className="flex items-center gap-1.5 ml-auto">
          {previewButton}
          {settingsButton}
        </div>
      </div>
      {previewBanner}
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
