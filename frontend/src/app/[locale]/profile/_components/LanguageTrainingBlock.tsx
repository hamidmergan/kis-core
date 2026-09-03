"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import ToggleRow from "@/components/ui/ToggleRow";

export interface ProfileMe {
  id: number;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  language_level: string | null;
  language_level_set_at: string | null;
  language_training_enabled: boolean;
  language_training_active: boolean;
  language_training_asked_at: string | null;
}

/** The one switch, the level and the way to the test. */
export function LanguageTrainingBlock({ me, onChanged }: { me: ProfileMe; onChanged: () => void }) {
  const t = useTranslations("profile.languageTraining");
  const tDiag = useTranslations("workspace.detail.languageTraining.diagnosis");
  const locale = useLocale();
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/me/language-training", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !me.language_training_active }),
      });
      if (res.ok) onChanged();
    } catch {
      // A network error stays silent, the switch just does not move.
    } finally {
      setBusy(false);
    }
  };

  // The stored level goes, then the test page starts a fresh run.
  const redo = async () => {
    if (busy) return;
    if (!window.confirm(tDiag("resetConfirmBody"))) return;
    setBusy(true);
    try {
      const res = await fetch("/api/ai-assistant/language-diagnosis/me", {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) router.push("/profile/language-test");
    } catch {
      // A network error stays silent, the level just stays as it was.
    } finally {
      setBusy(false);
    }
  };

  const setAt = me.language_level_set_at
    ? new Date(me.language_level_set_at).toLocaleDateString(locale === "en" ? "en-GB" : "de-DE")
    : null;

  return (
    <section
      className="rounded-2xl p-5 flex flex-col gap-4"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
    >
      <ToggleRow
        title={t("switchTitle")}
        description={t("switchDescription")}
        checked={me.language_training_active}
        onToggle={() => void toggle()}
        disabled={busy}
      />
      {me.language_training_active && me.language_level && (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm" style={{ color: "var(--foreground)" }}>
            {t("levelLabel")}
            <span
              className="ml-1 px-1.5 py-0.5 rounded text-xs"
              style={{ backgroundColor: "var(--kb)", color: "var(--on-accent)" }}
            >
              {me.language_level}
            </span>
            {setAt && (
              <span className="ml-2 text-xs" style={{ color: "var(--muted)" }}>
                {t("levelSince", { date: setAt })}
              </span>
            )}
          </p>
          <button
            type="button"
            onClick={() => void redo()}
            disabled={busy}
            className="px-3 py-1.5 text-xs rounded-md text-foreground border-2 border-border transition-colors hover:border-kb"
          >
            {t("redo")}
          </button>
        </div>
      )}
      {me.language_training_active && !me.language_level && (
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("noLevel")}</p>
          <button
            type="button"
            onClick={() => router.push("/profile/language-test")}
            className="btn-primary text-sm rounded-lg px-4 py-2 flex-shrink-0"
          >
            {t("takeTest")}
          </button>
        </div>
      )}
    </section>
  );
}
