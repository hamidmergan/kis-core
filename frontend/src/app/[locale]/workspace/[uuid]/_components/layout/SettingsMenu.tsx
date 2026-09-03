"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import ToggleRow from "@/components/ui/ToggleRow";
import type { MascotVariant } from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import { OwnerOnly } from "./OwnerOnly";

interface SettingsMenuProps {
  open: boolean;
  onClose: () => void;
  studioEnabled: boolean;
  onToggleStudio: () => void;
  isOwner: boolean;
  onStartTour: () => void;
  transcriptTargetLang: string;
  onChangeTranscriptTargetLang: (lang: string) => void;
  popupTranslateLang: string;
  onChangePopupTranslateLang: (lang: string) => void;
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
  isOwner,
  onStartTour,
  transcriptTargetLang,
  onChangeTranscriptTargetLang,
  popupTranslateLang,
  onChangePopupTranslateLang,
}: SettingsMenuProps) {
  const t = useTranslations("workspace.detail.settings");
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
