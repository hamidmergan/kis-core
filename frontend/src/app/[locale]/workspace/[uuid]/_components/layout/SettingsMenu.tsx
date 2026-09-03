"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import type { MascotVariant } from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { OwnerOnly } from "./OwnerOnly";

interface SettingsMenuProps {
  open: boolean;
  onClose: () => void;
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
  onStartTour: () => void;
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

// Personal and course settings need a visible separation.
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
  languageTrainingAvailable,
  onToggleLanguageTraining,
  languageTrainingOptIn,
  onToggleLanguageTrainingOptIn,
  isOwner,
  onStartTour,
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
  const tFooter = useTranslations("footer");
  const tTour = useTranslations("workspace.detail.tour");
  const { variant: mascotVariant, setVariant: setMascotVariant } = useMascotPref();

  // The languages come from the backend, the names from our own labels.
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

  // Only course and person together show the trainer.
  const languageTrainingVisible = language_trainingActive && languageTrainingOptIn;

  const MASCOT_OPTIONS = [
    { value: "hilde" as const, label: t("mascotHilde") },
    { value: "francis" as const, label: t("mascotFrancis") },
  ];

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-4">
        <SectionHeading
          title={t("sectionPersonalTitle")}
          description={t("sectionPersonalDescription")}
        />
        <div>
          <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("mascotTitle")}</p>
          <p className="text-xs mt-1" style={{ color: "var(--muted)" }}>{t("mascotDescription")}</p>
          <div className="mt-2">
            <Select<MascotVariant>
              value={mascotVariant}
              onChange={setMascotVariant}
              options={MASCOT_OPTIONS}
            />
          </div>
        </div>
        <ToggleRow
          title={t("studioTitle")}
          description={t("studioDescription")}
          checked={studioEnabled}
          onToggle={onToggleStudio}
        />
        {/* Die Verwaltung des Kurses gibt den Trainer frei, hier entscheidet
            jede Person fuer sich, ob sie ihn sieht. Ohne Freigabe ist die Zeile
            ganz weg, sonst stuende hier ein Schalter, der nichts bewirkt. */}
        {language_trainingActive && (
          <ToggleRow
            title={t("languageTrainingPersonalTitle")}
            description={t("languageTrainingPersonalDescription")}
            checked={languageTrainingOptIn}
            onToggle={onToggleLanguageTrainingOptIn}
          />
        )}
        {/* Das Niveau haengt am Nutzer, der Sprachtrainer am Workspace. Ist er
            hier aus, wird das Niveau auch nirgends benutzt, dann hat es in den
            Einstellungen dieses Kurses nichts zu suchen. Gespeichert bleibt es,
            wer den Trainer wieder einschaltet, findet seine Einstufung vor. */}
        {languageTrainingVisible && languageLevel && onResetLanguageLevel && (
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                {tDiag("resetSetting")} <span className="ml-1 px-1.5 py-0.5 rounded text-xs" style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}>{languageLevel}</span>
              </p>
            </div>
            <button
              type="button"
              onClick={handleResetLanguageLevel}
              className="px-3 py-1.5 text-xs rounded-md text-foreground border-2 border-border transition-colors hover:border-kb"
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
        {/* The line separates personal from course settings and is no control, so it stays unmarked. */}
        {isOwner && <div className="mt-4 border-t" style={{ borderColor: "var(--border)" }} />}
        {/* All course settings sit in one box, so the preview marks them once instead of three times. */}
        <OwnerOnly show={isOwner}>
          <div className="mt-4 p-4">
            <SectionHeading
              title={t("sectionWorkspaceTitle")}
              description={t("sectionWorkspaceDescription")}
            />
            <div className="mt-4">
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
            {/* Der Admin gibt den Sprachtrainer plattformweit frei, hier entscheidet
                die Verwaltung des Workspace, ob der Kurs ihn anbietet. Ganz weg statt
                gesperrt, solange die Plattform ihn nicht anbietet, ein toter Schalter
                erklaert nichts. */}
            {languageTrainingAvailable && (
              <div className="mt-5">
                <ToggleRow
                  title={t("languageTrainingTitle")}
                  description={t("languageTrainingDescription")}
                  checked={language_trainingActive}
                  onToggle={onToggleLanguageTraining}
                />
              </div>
            )}
          </div>
        </OwnerOnly>
        <div className="mt-2 pt-4 border-t" style={{ borderColor: "var(--border)" }}>
          <Link
            href="/feedback"
            className="text-xs hover:underline hover:text-[var(--kb)] transition-colors"
            style={{ color: "var(--muted)" }}
          >
            {tFooter("feedback")}
          </Link>
        </div>
      </div>
    </Modal>
  );
}
