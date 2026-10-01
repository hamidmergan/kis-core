"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import ToggleRow from "@/components/ui/ToggleRow";

interface SettingsMenuProps {
  open: boolean;
  onClose: () => void;
  studioEnabled: boolean;
  onToggleStudio: () => void;
  /** Switch offered at all: owners always, enrolled people only in the demo course. */
  canPreview: boolean;
  previewOn: boolean;
  /** true: previews the owner side, false: the owner previews the student side. */
  previewsOwnerSide: boolean;
  onTogglePreview: () => void;
  onStartTour: () => void;
  /** The one demo course the guided tour runs in, only there is restarting it offered. */
  isTourModule: boolean;
  popupTranslateLang: string;
  onChangePopupTranslateLang: (lang: string) => void;
}

export function SettingsMenu({
  open,
  onClose,
  studioEnabled,
  onToggleStudio,
  canPreview,
  previewOn,
  previewsOwnerSide,
  onTogglePreview,
  onStartTour,
  isTourModule,
  popupTranslateLang,
  onChangePopupTranslateLang,
}: SettingsMenuProps) {
  const t = useTranslations("workspace.detail.settings");
  const tLang = useTranslations("langLabels");
  const tFooter = useTranslations("footer");
  const tTour = useTranslations("workspace.detail.tour");

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

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-4">
        <ToggleRow
          title={t("studioTitle")}
          description={t("studioDescription")}
          checked={studioEnabled}
          onToggle={onToggleStudio}
        />
        {canPreview && (
          <ToggleRow
            title={previewsOwnerSide ? t("previewOwnerTitle") : t("previewStudentTitle")}
            description={previewsOwnerSide ? t("previewOwnerDescription") : t("previewStudentDescription")}
            checked={previewOn}
            /* The window closes on switching, otherwise it covers the view it just changed. */
            onToggle={() => { onTogglePreview(); onClose(); }}
            dataTour="preview-toggle"
          />
        )}
        {isTourModule && (
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{tTour("label")}</p>
              <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{tTour("description")}</p>
            </div>
            <button
              type="button"
              onClick={onStartTour}
              aria-label={tTour("label")}
              className="flex-shrink-0 text-sm rounded-lg px-3 py-2 text-foreground-soft border-2 border-border hover:border-kb transition-colors"
            >
              {tTour("inviteStart")}
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
