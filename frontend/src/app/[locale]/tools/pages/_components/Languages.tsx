"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Translate } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import * as api from "../_lib/api";
import type { LanguageChoice, Languages } from "../_lib/types";

// A running translation is asked for again at this pace until it is done.
const POLL_MS = 4000;

/** The pill above the page with every language it can be read in, only when there is more than one. */
export function LanguageSwitch({ value, choices, disabled, title, className, onChange }: {
  value: string; choices: LanguageChoice[]; disabled?: boolean; title?: string; className?: string; onChange: (key: string) => void;
}) {
  const t = useTranslations("tools.pages");
  if (choices.length < 2) return null;
  return (
    <span title={title} className={className}>
      <Select<string> size="sm" value={value} onChange={onChange} disabled={disabled} ariaLabel={t("languageSelect")}
        options={choices.map((c) => ({ value: c.key, label: c.label }))} />
    </span>
  );
}

/** The languages of what the owner can read and switch to, the page's own first. */
export function readableOf(l: Languages | null): LanguageChoice[] {
  if (!l) return [];
  return [l.own, ...l.languages.filter((x) => x.state === "done").map(({ key, label }) => ({ key, label }))];
}

/** The round button in the editor's bar, with a dot when a language is older than the page. */
export function LanguagesButton({ languages, onClick }: { languages: Languages | null; onClick: () => void }) {
  const t = useTranslations("tools.pages");
  const stale = !!languages?.languages.some((l) => l.stale);
  return (
    <button type="button" onClick={onClick} className="relative w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0"
      style={{ backgroundColor: "var(--surface-dim)" }} title={stale ? t("languagesStale") : t("languages")} aria-label={t("languages")}>
      <Translate size={17} weight="regular" />
      {stale && (
        <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full" style={{ backgroundColor: "var(--warn-strong)", border: "2px solid var(--background)" }} />
      )}
    </button>
  );
}

/** Adding, renewing and removing the languages of a page; a done one can be opened for editing. */
export function LanguagesModal({ open, uuid, languages, dirty, onClose, onChange, onEdit }: {
  open: boolean; uuid: string; languages: Languages | null; dirty: boolean;
  onClose: () => void; onChange: (l: Languages) => void; onEdit: (key: string) => void;
}) {
  const t = useTranslations("tools.pages");
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = !!languages?.languages.some((l) => l.state === "running");

  useEffect(() => {
    if (!open || !running) return;
    const id = window.setInterval(() => { api.getLanguages(uuid).then(onChange).catch(() => {}); }, POLL_MS);
    return () => window.clearInterval(id);
  }, [open, running, uuid, onChange]);

  useEffect(() => { if (open) setError(null); }, [open]);

  const act = async (key: string, fn: () => Promise<Languages>) => {
    setBusy(key);
    setError(null);
    try {
      onChange(await fn());
      setPick("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const full = !!languages && languages.languages.length >= languages.max;
  return (
    <Modal open={open} onClose={onClose} size="md" title={t("languages")}
      footer={<button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg" onClick={onClose}>{t("done")}</button>}>
      <p className="text-sm" style={{ color: "var(--muted)" }}>{t("languagesHint")}</p>
      {dirty && <p className="text-sm mt-2" style={{ color: "var(--warn-strong)" }}>{t("languagesUnsaved")}</p>}
      {!languages ? (
        <div className="flex justify-center py-6"><Spinner /></div>
      ) : (
        <>
          <ul className="mt-4 flex flex-col">
            <li className="flex items-center gap-3 py-2.5 text-sm" style={{ borderTop: "2px solid var(--border-soft)" }}>
              <span className="font-medium flex-1">{languages.own.label}</span>
              <span className="text-xs" style={{ color: "var(--muted)" }}>{t("ownLanguage")}</span>
            </li>
            {languages.languages.map((l) => (
              <li key={l.key} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5 text-sm" style={{ borderTop: "2px solid var(--border-soft)" }}>
                <span className="font-medium flex-1 min-w-[8rem]">{l.label}</span>
                {l.state === "running" && (
                  <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: "var(--muted)" }}><Spinner size="sm" />{t("langRunning")}</span>
                )}
                {l.state === "failed" && <span className="text-xs text-error">{t("langFailed")}</span>}
                {l.stale && <span className="text-xs" style={{ color: "var(--warn-strong)" }}>{t("langStale")}</span>}
                <span className="flex gap-1.5">
                  {l.state === "done" && (
                    <button type="button" className="px-2.5 py-1 text-xs font-medium btn-secondary rounded-lg disabled:opacity-40 disabled:cursor-not-allowed"
                      disabled={dirty} title={dirty ? t("saveFirst") : undefined} onClick={() => onEdit(l.key)}>{t("modeEdit")}</button>
                  )}
                  {l.state !== "running" && (
                    <button type="button" className="px-2.5 py-1 text-xs font-medium btn-secondary rounded-lg disabled:opacity-40"
                      disabled={busy !== null} onClick={() => act(l.key, () => api.addLanguage(uuid, l.key))}
                      title={l.state === "done" ? t("langUpdateTitle") : undefined}>
                      {l.state === "failed" ? t("langRetry") : t("langUpdate")}
                    </button>
                  )}
                  <button type="button" className="px-2.5 py-1 text-xs font-medium btn-secondary rounded-lg disabled:opacity-40"
                    disabled={busy !== null} onClick={() => act(l.key, () => api.dropLanguage(uuid, l.key))}>{t("remove")}</button>
                </span>
              </li>
            ))}
          </ul>
          {languages.choices.length > 0 && (
            <div className="flex items-center gap-2 mt-3 pt-3" style={{ borderTop: "2px solid var(--border-soft)" }}>
              <div className="flex-1 min-w-0">
                <Select<string> value={pick} onChange={setPick} disabled={full} placeholder={t("langAdd")} ariaLabel={t("langAdd")}
                  options={languages.choices.map((c) => ({ value: c.key, label: c.label }))} />
              </div>
              <button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={!pick || full || busy !== null} onClick={() => act(pick, () => api.addLanguage(uuid, pick))}
                title={full ? t("langMax", { max: languages.max }) : undefined}>
                {busy === pick && <Spinner size="sm" color="current" />}{t("langAddButton")}
              </button>
            </div>
          )}
          {full && <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>{t("langMax", { max: languages.max })}</p>}
          {error && <p className="text-sm mt-2 text-error" role="alert">{error}</p>}
        </>
      )}
    </Modal>
  );
}
