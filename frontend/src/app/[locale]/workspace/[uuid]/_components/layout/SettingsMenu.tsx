"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import { useMascotPref, type MascotMode } from "@/hooks/useMascotPref";
import { LearnerProfilePanel } from "../LearnerProfilePanel";

interface SettingsMenuProps {
  open: boolean;
  onClose: () => void;
  studioEnabled: boolean;
  onToggleStudio: () => void;
  language_trainingActive: boolean;
  onToggleLanguageTraining: () => void;
  isOwner: boolean;
  isAdmin: boolean;
  transcriptTargetLang: string;
  onChangeTranscriptTargetLang: (lang: string) => void;
  popupTranslateLang: string;
  onChangePopupTranslateLang: (lang: string) => void;
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

// The dialog mixes two kinds of settings: personal ones every reader has for
// themselves, and workspace ones only owners and tutors see that apply to
// everyone. Without a visible break, an owner cannot tell which is which.
function SectionHeading({
  title,
  description,
  divider,
}: {
  title: string;
  description: string;
  divider?: boolean;
}) {
  return (
    <div
      className={divider ? "pt-4 border-t" : undefined}
      style={divider ? { borderColor: "var(--border)" } : undefined}
    >
      <p
        className="text-xs font-semibold uppercase tracking-wide"
        style={{ color: "var(--foreground)" }}
      >
        {title}
      </p>
      <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{description}</p>
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
  isAdmin,
  transcriptTargetLang,
  onChangeTranscriptTargetLang,
  popupTranslateLang,
  onChangePopupTranslateLang,
  languageLevel,
  onResetLanguageLevel,
}: SettingsMenuProps) {
  const t = useTranslations("workspace.detail.settings");
  const tDiag = useTranslations("workspace.detail.languageTraining.diagnosis");
  const tLang = useTranslations("langLabels");
  const { mode: mascotMode, setMode: setMascotMode, globalEnabled: mascotGlobalEnabled } = useMascotPref();

  // The learner profile opens as a subview of this same modal instead of a
  // second overlay. Reset it whenever the modal is closed from outside, so it
  // never reopens straight into the subview.
  const [showLearnerProfile, setShowLearnerProfile] = useState(false);
  useEffect(() => {
    if (!open) setShowLearnerProfile(false);
  }, [open]);

  // WHICH languages exist comes from the backend (single source of truth,
  // i18n.TRANSCRIPT_LANGUAGES). What they are CALLED comes from our own
  // langLabels messages, like every other language picker in the app - the
  // backend's own label follows Accept-Language, not the UI locale, so it would
  // read "Turkish" inside a German dialog.
  // Not gated on isOwner: the popup-translation target is a per-reader setting,
  // so every enrolled person needs this list, not just the owner.
  const [targetLangCodes, setTargetLangCodes] = useState<{ id: string; deepl: string }[]>([]);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/ai-assistant/transcript-languages", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data?.languages) return;
        setTargetLangCodes(
          data.languages.map((l: { id: string; deepl: string }) => ({ id: l.id, deepl: l.deepl })),
        );
      })
      .catch(() => { /* picker stays empty */ });
    return () => { cancelled = true; };
  }, []);

  const targetLangOptions = targetLangCodes.map(({ id, deepl }) => ({
    value: id,
    label: tLang(deepl),
  }));

  const handleResetLanguageLevel = () => {
    if (!onResetLanguageLevel) return;
    if (!window.confirm(tDiag("resetConfirmBody"))) return;
    void onResetLanguageLevel();
  };

  const MASCOT_OPTIONS = [
    { value: "off" as const, label: t("mascotOff") },
    { value: "hilde" as const, label: t("mascotHilde") },
    { value: "francis" as const, label: t("mascotFrancis") },
  ];

  if (showLearnerProfile && isAdmin) {
    return (
      <Modal open={open} onClose={onClose} title={t("learnerProfileTitle")} size="lg">
        <div className="flex flex-col gap-4">
          <button
            type="button"
            onClick={() => setShowLearnerProfile(false)}
            className="self-start text-xs font-medium"
            style={{ color: "var(--kb)" }}
          >
            {t("learnerProfileBack")}
          </button>
          <LearnerProfilePanel />
        </div>
      </Modal>
    );
  }

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-4">
        <SectionHeading
          title={t("sectionPersonalTitle")}
          description={t("sectionPersonalDescription")}
        />
        {mascotGlobalEnabled && (
          <div>
            <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("mascotTitle")}</p>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{t("mascotDescription")}</p>
            <div className="mt-2">
              <Select<MascotMode>
                value={mascotMode}
                onChange={setMascotMode}
                options={MASCOT_OPTIONS}
              />
            </div>
          </div>
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
        {/* Admin-only: the learner profile is a debugging/insight view. It confuses
            regular users, so only an admin sees the entry (and can open it). */}
        {isAdmin && (
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium flex items-center gap-1.5" style={{ color: "var(--foreground)" }}>
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide" style={{ backgroundColor: "var(--kb)", color: "white" }}>{t("learnerProfileAdminOnly")}</span>
                {t("learnerProfileTitle")}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{t("learnerProfileDescription")}</p>
            </div>
            <button
              type="button"
              onClick={() => setShowLearnerProfile(true)}
              className="px-3 py-1.5 text-xs rounded-md border"
              style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
            >
              {t("learnerProfileOpen")}
            </button>
          </div>
        )}
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
        <div className="mt-3">
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("popupTranslateLangTitle")}</p>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
            {t("popupTranslateLangDescription")}
          </p>
          <div className="mt-3">
            <Select<string>
              value={popupTranslateLang}
              onChange={onChangePopupTranslateLang}
              options={targetLangOptions}
            />
          </div>
        </div>
        {isOwner && (
          <SectionHeading
            title={t("sectionWorkspaceTitle")}
            description={t("sectionWorkspaceDescription")}
            divider
          />
        )}
        {isOwner && (
          <div className="mt-3">
            <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("transcriptTargetLangTitle")}</p>
            <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>
              {t("transcriptTargetLangDescription")}
            </p>
            <div className="mt-3">
              <Select<string>
                value={transcriptTargetLang}
                onChange={onChangeTranscriptTargetLang}
                options={targetLangOptions}
              />
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
