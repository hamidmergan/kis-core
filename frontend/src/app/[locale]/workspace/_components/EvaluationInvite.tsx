"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { PencilSimple } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";

const DISMISS_KEY = "kis-evaluation-dismissed";

/**
 * Invite into the evaluation, next to the tour invite on the start page.
 *
 * Only appears while an evaluation is switched on and this account has not
 * answered it yet. Declining hides it for this browser, an admin turning the
 * evaluation off and on again brings it back.
 */
export function EvaluationInvite() {
  const t = useTranslations("evaluationInvite");
  const router = useRouter();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let abgelehnt = false;
    try {
      abgelehnt = localStorage.getItem(DISMISS_KEY) === "true";
    } catch {
      /* private mode or blocked storage, then it just shows every time */
    }
    if (abgelehnt) return;
    fetch("/api/evaluation/active", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { active?: boolean; already_responded?: boolean } | null) => {
        if (cancelled || !d) return;
        setVisible(d.active === true && d.already_responded !== true);
      })
      .catch(() => {
        /* the invite can wait for the next visit */
      });
    return () => { cancelled = true; };
  }, []);

  if (!visible) return null;

  const spaeter = () => {
    try {
      localStorage.setItem(DISMISS_KEY, "true");
    } catch {
      /* nothing to persist then, the invite just shows again next time */
    }
    setVisible(false);
  };

  return (
    <div
      className="rounded-xl p-4 flex-1 flex items-start gap-3"
      style={{ backgroundColor: "var(--surface-dim)", border: "1px solid var(--border-soft)" }}
    >
      <PencilSimple size={20} weight="bold" style={{ color: "var(--kb)", flexShrink: 0, marginTop: 2 }} />
      <div className="min-w-0 flex-1 self-stretch flex flex-col">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{t("title")}</p>
        <p className="text-sm mt-1" style={{ color: "var(--foreground-soft)" }}>{t("body")}</p>
        <div className="flex items-stretch gap-2 mt-auto pt-3">
          <button
            type="button"
            onClick={() => router.push("/evaluation")}
            className="btn-primary text-sm rounded-lg px-4 py-2"
          >
            {t("start")}
          </button>
          <button
            type="button"
            onClick={spaeter}
            className="text-sm rounded-lg px-3 py-2 text-foreground-soft border-2 border-border hover:border-kb transition-colors"
          >
            {t("dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
