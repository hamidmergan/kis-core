"use client";

import React from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import { useHildePref } from "@/hooks/useHildePref";
import type { TranscriptTranslationMode, TranscriptDefaultLang } from "../../_types";

interface SettingsMenuProps {
  open: boolean;
  onClose: () => void;
  studioEnabled: boolean;
  onToggleStudio: () => void;
  language_trainingActive: boolean;
  onToggleLanguageTraining: () => void;
  isOwner: boolean;
  translationMode: TranscriptTranslationMode;
  onChangeTranslationMode: (mode: TranscriptTranslationMode) => void;
  transcriptDefaultLang: TranscriptDefaultLang;
  onChangeTranscriptDefaultLang: (lang: TranscriptDefaultLang) => void;
  languageLevel?: string | null;
  onResetLanguageLevel?: () => void | Promise<void>;
}

function ToggleRow({
  title,
  description,
  checked,
  onToggle,
  disabled,
}: {
  title: string;
  description: string;
  checked: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4" style={{ opacity: disabled ? 0.4 : 1 }}>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{title}</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={title}
        onClick={() => !disabled && onToggle()}
        disabled={disabled}
        className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] disabled:hover:border-transparent transition-colors duration-200"
        style={{ backgroundColor: checked && !disabled ? "var(--kb)" : "var(--border)", cursor: disabled ? "not-allowed" : "pointer" }}
      >
        <span
          className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
          style={{ transform: checked && !disabled ? "translateX(16px)" : "translateX(0)" }}
        />
      </button>
    </div>
  );
}

export function SettingsMenu({
  open,
  onClose,
  studioEnabled,
  onToggleStudio,
  language_trainingActive,
  onToggleLanguageTraining,
  isOwner,
  translationMode,
  onChangeTranslationMode,
  transcriptDefaultLang,
  onChangeTranscriptDefaultLang,
  languageLevel,
  onResetLanguageLevel,
}: SettingsMenuProps) {
  const t = useTranslations("workspace.detail.settings");
  const tDiag = useTranslations("workspace.detail.languageTraining.diagnosis");
  const { enabled: hildeEnabled, toggle: toggleHilde, globalEnabled: mascotGlobalEnabled } = useHildePref();

  const handleResetLanguageLevel = () => {
    if (!onResetLanguageLevel) return;
    if (!window.confirm(tDiag("resetConfirmBody"))) return;
    void onResetLanguageLevel();
  };

  const TRANSLATION_MODE_OPTIONS = [
    { value: "off" as const, label: t("translationModeOff") },
    { value: "auto" as const, label: t("translationModeAuto") },
    { value: "manual" as const, label: t("translationModeManual") },
  ];

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-4">
        {mascotGlobalEnabled && (
          <ToggleRow
            title={t("hildeTitle")}
            description={t("hildeDescription")}
            checked={hildeEnabled}
            onToggle={toggleHilde}
          />
        )}
        <ToggleRow
          title={t("studioTitle")}
          description={t("studioDescription")}
          checked={studioEnabled}
          onToggle={onToggleStudio}
        />
        <ToggleRow
          title={t("languageTrainingTitle")}
          description={t("languageTrainingDescription")}
          checked={language_trainingActive}
          onToggle={onToggleLanguageTraining}
          disabled={!studioEnabled}
        />
        {languageLevel && onResetLanguageLevel && (
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                {tDiag("resetSetting")} <span className="ml-1 px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}>{languageLevel}</span>
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{tDiag("resetConfirmBody")}</p>
            </div>
            <button
              type="button"
              onClick={handleResetLanguageLevel}
              className="px-3 py-1.5 text-xs rounded-md border"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
            >
              {tDiag("resetSetting")}
            </button>
          </div>
        )}
        {isOwner && (
          <div className="mt-3">
            <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("translationModeTitle")}</p>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("translationModeDescription")}
            </p>
            <ul className="text-xs mt-2 space-y-1 pl-4 list-disc" style={{ color: "var(--muted)" }}>
              <li><strong>{t("translationModeOff")}</strong> {t("translationModeOffHint")}</li>
              <li><strong>{t("translationModeAuto")}</strong> {t("translationModeAutoHint")}</li>
              <li><strong>{t("translationModeManual")}</strong> {t("translationModeManualHint")}</li>
            </ul>
            <div className="mt-3">
              <Select<TranscriptTranslationMode>
                value={translationMode}
                onChange={onChangeTranslationMode}
                options={TRANSLATION_MODE_OPTIONS}
              />
            </div>
          </div>
        )}
        {isOwner && (
          <div className="mt-3">
            <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("transcriptDefaultLangTitle")}</p>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("transcriptDefaultLangDescription")}
            </p>
            <div className="mt-3 flex gap-1">
              {(["de", "en", "both"] as const).map((lang) => {
                const active = transcriptDefaultLang === lang;
                const label = lang === "de" ? t("transcriptDefaultLangDe")
                  : lang === "en" ? t("transcriptDefaultLangEn")
                  : t("transcriptDefaultLangBoth");
                return (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => onChangeTranscriptDefaultLang(lang)}
                    className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
                    style={{
                      backgroundColor: active ? "var(--kb)" : "transparent",
                      color: active ? "white" : "var(--muted)",
                      border: `1px solid ${active ? "var(--kb)" : "var(--border)"}`,
                    }}
                    aria-pressed={active}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
