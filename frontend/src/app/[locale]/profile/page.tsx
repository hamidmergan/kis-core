"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { genericErrorMessage } from "@/lib/api";
import { LanguageTrainingBlock, type ProfileMe } from "./_components/LanguageTrainingBlock";

/** The person and their language trainer, everything from /api/me. */
export default function ProfilePage() {
  const t = useTranslations("profile");
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

  const roleLabel = (role: string) =>
    role === "admin" ? t("roleAdmin") : role === "staff" ? t("roleStaff") : role === "user" ? t("roleUser") : role;

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
        ) : (
          <div className="flex flex-col gap-6 max-w-2xl">
            <section
              className="rounded-2xl p-5"
              style={{ border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
            >
              <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                <dt style={{ color: "var(--muted)" }}>{t("displayName")}</dt>
                <dd>{me.display_name}</dd>
                <dt style={{ color: "var(--muted)" }}>{t("username")}</dt>
                <dd>{me.username}</dd>
                <dt style={{ color: "var(--muted)" }}>{t("email")}</dt>
                <dd>{me.email ?? t("noEmail")}</dd>
                <dt style={{ color: "var(--muted)" }}>{t("role")}</dt>
                <dd>{roleLabel(me.role)}</dd>
              </dl>
            </section>
            {me.language_training_enabled && <LanguageTrainingBlock me={me} onChanged={load} />}
          </div>
        )}
      </main>
    </ProtectedRoute>
  );
}
