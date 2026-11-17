"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { PencilSimple } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import { InviteCard } from "./InviteCard";
import { readPrefs, updatePrefs } from "@/lib/browserStore";
import { EvaluationStand, merkerFuerRunde, zeigtEinladung } from "./evaluationEinladung";

/**
 * Invite into the evaluation, next to the tour invite on the start page.
 *
 * Only appears while an evaluation is switched on and this account has not
 * answered it yet. Declining hides it for this browser until an admin starts a
 * new round by switching the evaluation, or the whole platform, back on.
 */
export function EvaluationInvite() {
  const t = useTranslations("evaluationInvite");
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [stand, setStand] = useState<EvaluationStand | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Blocked storage reads as no marker, then it just shows every time.
    const merker = readPrefs().evaluationDismissed ?? null;
    fetch("/api/evaluation/active", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: EvaluationStand | null) => {
        if (cancelled || !d) return;
        setStand(d);
        setVisible(zeigtEinladung(d, merker));
      })
      .catch(() => {
        /* the invite can wait for the next visit */
      });
    return () => { cancelled = true; };
  }, []);

  if (!visible) return null;

  const spaeter = () => {
    updatePrefs({ evaluationDismissed: merkerFuerRunde(stand) });
    setVisible(false);
  };

  return (
    <InviteCard icon={PencilSimple} title={t("title")} body={t("body")}>
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
    </InviteCard>
  );
}
