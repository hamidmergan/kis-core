"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { genericErrorMessage } from "@/lib/api";
import { LanguageTrainingBlock, type ProfileMe } from "./_components/LanguageTrainingBlock";
import { LanguageTrainingSwitch } from "./_components/LanguageTrainingSwitch";

/** The person's language level, everything from /api/me. */
export default function ProfilePage() {
  const t = useTranslations("languageLevel");
  // undefined while loading, null when the request failed.
  const [me, setMe] = useState<ProfileMe | null | undefined>(undefined);

  const load = useCallback(() => {
    fetch("/api/me", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setMe(data ?? null);
      })
      .catch(() => {
        setMe(null);
      });
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  return (
    <ProtectedRoute>
      <main className="page-shell py-8">
        <h2 className="text-xl font-semibold mb-4">{t("title")}</h2>
        {me === undefined ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : me === null ? (
          <div className="max-w-xl mx-auto text-center">
            <p className="text-sm" style={{ color: "var(--muted)" }}>{genericErrorMessage()}</p>
          </div>
        ) : !me.language_training_enabled ? (
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("notOffered")}</p>
        ) : (
          <div className="max-w-2xl mx-auto">
            {/* Without this line the level sits there without saying what it acts on. */}
            <p className="text-sm text-center" style={{ color: "var(--foreground-soft)" }}>{t("purpose")}</p>
            {me.language_training_active && <LanguageTrainingBlock me={me} onChanged={load} />}
            <LanguageTrainingSwitch active={me.language_training_active} onChanged={load} />
          </div>
        )}
      </main>
    </ProtectedRoute>
  );
}
