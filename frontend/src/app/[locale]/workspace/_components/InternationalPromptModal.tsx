"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";
import { persistLocale, rememberLocaleCookie } from "@/lib/switchLocale";
import Modal from "@/components/ui/Modal";

const LOCALES = UI_LOCALES as readonly Locale[];

interface Props {
  /** Missing while auth is still loading, or during an admin impersonation. */
  userId?: number;
  /** Only the role "user" is asked, staff and admins find the switch in the profile. */
  role?: string;
  /** The welcome dialog goes first, this one waits until it is closed. */
  blocked: boolean;
}

interface MeState {
  language_training_enabled: boolean;
  language_training_asked_at: string | null;
}

/** Asks once per account whether the person is an international student. */
export default function InternationalPromptModal({ userId, role, blocked }: Props) {
  const t = useTranslations("internationalPrompt");
  const tLang = useTranslations("languageSwitch");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const [due, setDue] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!userId || role !== "user") return;
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((me: MeState | null) => {
        if (cancelled || !me) return;
        setDue(me.language_training_enabled === true && me.language_training_asked_at === null);
      })
      .catch(() => {
        /* the question can wait for the next visit */
      });
    return () => {
      cancelled = true;
    };
  }, [userId, role]);

  // Yes switches on and leads to the test, no and later only close the question for good.
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
      setDue(false);
      if (active) router.push("/profile/language-test");
    } catch {
      setBusy(false);
    }
  };

  const chooseLocale = (next: Locale) => {
    if (next === currentLocale) return;
    rememberLocaleCookie(next);
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };

  return (
    <Modal
      open={due && !blocked}
      onClose={() => void answer(false)}
      title={t("title")}
      closeOnBackdropClick={false}
      closeOnEscape={false}
      footer={
        <div className="flex flex-wrap gap-2 justify-end">
          <button
            type="button"
            onClick={() => void answer(false)}
            disabled={busy}
            className="text-sm rounded-lg px-4 py-2"
            style={{ color: "var(--muted)" }}
          >
            {t("later")}
          </button>
          <button
            type="button"
            onClick={() => void answer(false)}
            disabled={busy}
            className="text-sm rounded-lg px-4 py-2 border-2 border-border"
          >
            {t("no")}
          </button>
          <button
            type="button"
            onClick={() => void answer(true)}
            disabled={busy}
            className="btn-primary text-sm rounded-lg px-4 py-2"
          >
            {t("yes")}
          </button>
        </div>
      }
    >
      <div className="flex gap-1 mb-3" role="group" aria-label={tLang("ariaLabel")}>
        {LOCALES.map((loc) => (
          <button
            key={loc}
            type="button"
            onClick={() => chooseLocale(loc)}
            aria-pressed={loc === currentLocale}
            className="text-xs uppercase font-mono px-2 py-1 rounded-md border-2"
            style={{
              borderColor: loc === currentLocale ? "var(--kb)" : "var(--border)",
              color: "var(--foreground)",
            }}
          >
            {loc}
          </button>
        ))}
      </div>
      <p className="text-sm whitespace-pre-line">{t("body")}</p>
    </Modal>
  );
}
