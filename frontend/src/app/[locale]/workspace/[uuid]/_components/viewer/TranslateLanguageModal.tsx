"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import { langLabel } from "../../_types";
import { chooseableTargetLangs } from "./_transcript";

/** Picks the one language a transcript gets translated into. */
export function TranslateLanguageModal({
  open,
  onClose,
  sourceLang,
  onStart,
}: {
  open: boolean;
  onClose: () => void;
  /** The language of the recording, it is no target for itself. */
  sourceLang: string | null;
  onStart: (lang: string) => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  const [codes, setCodes] = useState<string[]>([]);
  const [lang, setLang] = useState<string>("");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/ai-assistant/transcript-languages", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data?.languages) return;
        const all = (data.languages as { id: string }[]).map((l) => l.id);
        setCodes(chooseableTargetLangs(all, sourceLang));
      })
      .catch(() => { /* picker stays empty */ });
    return () => { cancelled = true; };
  }, [open, sourceLang]);

  // Preselect the first entry so the button is never a dead end.
  useEffect(() => {
    if (codes.length && !codes.includes(lang)) setLang(codes[0]);
  }, [codes, lang]);

  const options = codes.map((c) => ({ value: c, label: langLabel(c, locale) }));

  // The footer buttons carry the shared btn-* classes, never their own styling.
  const fuss = (
    <>
      <button
        type="button"
        onClick={onClose}
        className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg"
      >
        {t("translateModalCancel")}
      </button>
      <button
        type="button"
        onClick={() => { if (lang) onStart(lang); }}
        disabled={!lang}
        className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50"
      >
        {t("translateModalStart")}
      </button>
    </>
  );

  return (
    <Modal open={open} onClose={onClose} title={t("translateModalTitle")} size="sm" footer={fuss}>
      <div className="flex flex-col gap-4">
        <p className="text-xs" style={{ color: "var(--muted)" }}>{t("translateModalHint")}</p>
        <div>
          <label htmlFor="translate-target-lang" className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
            {t("translateModalLangLabel")}
          </label>
          <div className="mt-2">
            <Select<string>
              id="translate-target-lang"
              value={lang}
              onChange={setLang}
              options={options}
            />
          </div>
        </div>
      </div>
    </Modal>
  );
}
