"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Translate } from "@phosphor-icons/react";
import { useRouter } from "@/i18n/navigation";
import { InviteCard } from "./InviteCard";

interface MeState {
  language_training_enabled: boolean;
  language_training_asked_at: string | null;
}

/**
 * Offer of the language trainer, on the start page next to the tour invite.
 *
 * Stands until the person answers once, either way. Starting switches the
 * trainer on and leads straight to the test, declining only records the answer.
 */
export function LanguageTrainerInvite() {
  const t = useTranslations("languageTrainerInvite");
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((me: MeState | null) => {
        if (cancelled || !me) return;
        setVisible(me.language_training_enabled === true && me.language_training_asked_at === null);
      })
      .catch(() => {
        /* the offer can wait for the next visit */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!visible) return null;

  const answer = async (active: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/me/language-training", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
      if (!res.ok) throw new Error("save failed");
      if (active) router.push("/language-level/test");
      else setVisible(false);
    } catch {
      setBusy(false);
    }
  };

  return (
    <InviteCard icon={Translate} title={t("title")} body={t("body")}>
      <button
        type="button"
        onClick={() => void answer(true)}
        disabled={busy}
        className="btn-primary text-sm rounded-lg px-4 py-2 disabled:opacity-50"
      >
        {t("start")}
      </button>
      <button
        type="button"
        onClick={() => void answer(false)}
        disabled={busy}
        className="text-sm rounded-lg px-3 py-2 text-foreground-soft border-2 border-border hover:border-kb transition-colors disabled:opacity-50"
      >
        {t("dismiss")}
      </button>
    </InviteCard>
  );
}
