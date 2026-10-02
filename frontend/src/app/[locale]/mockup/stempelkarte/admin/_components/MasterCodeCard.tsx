"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";
import { SettingCard } from "@/app/[locale]/admin/_settings/fields";
import { copyTextFromPromise } from "@/lib/clipboard";
import { resetMockup, useMockup } from "../../../_lib/store";
import { CODE_LENGTH, isValidMasterCode, newMasterCode, normalizeCode } from "../../../_lib/masterCode";
import { BTN_PRIMARY, BTN_SECONDARY, INPUT } from "./fields";

const FEEDBACK_MS = 1500;

/** Uses a short-lived flag for the copy tick and the reset note. */
function useFlash(): [boolean, () => void] {
  const [on, setOn] = useState(false);
  useEffect(() => {
    if (!on) return;
    const timer = window.setTimeout(() => setOn(false), FEEDBACK_MS);
    return () => window.clearTimeout(timer);
  }, [on]);
  return [on, () => setOn(true)];
}

export default function MasterCodeCard() {
  const t = useTranslations("mockup.admin.master");
  const [config, update] = useMockup("config");
  const [draft, setDraft] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [copied, flashCopied] = useFlash();
  const [reset, flashReset] = useFlash();

  const copy = () => {
    copyTextFromPromise(Promise.resolve(config.masterCode));
    flashCopied();
  };
  const apply = () => {
    const code = normalizeCode(draft);
    if (!isValidMasterCode(code)) {
      setInvalid(true);
      return;
    }
    update({ masterCode: code });
    setDraft("");
    setInvalid(false);
  };

  return (
    <SettingCard
      title={t("title")}
      description={t("description")}
      error={invalid ? t("invalid") : null}
      control={
        <>
          <span className="font-mono text-lg font-semibold tracking-widest text-foreground" data-testid="master-code">
            {config.masterCode}
          </span>
          <button type="button" onClick={copy} className={`${BTN_SECONDARY} inline-flex items-center gap-2`} data-testid="master-copy">
            {copied && <Check size={14} weight="bold" aria-hidden="true" className="text-kb" />}
            {copied ? t("copied") : t("copy")}
          </button>
          <button type="button" onClick={() => update({ masterCode: newMasterCode() })} className={BTN_SECONDARY} data-testid="master-reroll">
            {t("reroll")}
          </button>
        </>
      }
    >
      <div className="mt-4 flex flex-col gap-3">
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-muted">{t("ownLabel")}</span>
            <input
              type="text"
              value={draft}
              maxLength={CODE_LENGTH}
              autoCapitalize="characters"
              onChange={(e) => { setDraft(e.target.value.toUpperCase()); setInvalid(false); }}
              onKeyDown={(e) => { if (e.key === "Enter") apply(); }}
              className={`${INPUT} w-32 font-mono tracking-widest uppercase`}
              data-testid="master-input"
            />
          </label>
          <button type="button" onClick={apply} disabled={!draft} className={`${BTN_PRIMARY} disabled:opacity-50`} data-testid="master-apply">
            {t("apply")}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => { resetMockup("card"); flashReset(); }} className={BTN_SECONDARY}>
            {t("resetCard")}
          </button>
          {reset && <span className="text-sm text-foreground-soft">{t("resetDone")}</span>}
        </div>
      </div>
    </SettingCard>
  );
}
