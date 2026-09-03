"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Spinner from "@/components/ui/Spinner";
import { genericErrorMessage } from "@/lib/api";
import { LanguageDiagnosisPanel } from "@/app/[locale]/workspace/[uuid]/_components/language_training/LanguageDiagnosisPanel";

interface Me {
  id: number;
  language_training_enabled: boolean;
  language_training_active: boolean;
}

/** The language test on its own page, reachable from the profile. */
export default function LanguageTestPage() {
  const t = useTranslations("profile.languageTest");
  const router = useRouter();
  // undefined while loading, null when the request failed.
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const offered = !!me && me.language_training_enabled && me.language_training_active;
  const toProfile = () => router.push("/profile");

  return (
    <ProtectedRoute>
      <main className="page-shell py-8 aia-scale">
        {me === undefined ? (
          <div className="flex justify-center py-16">
            <Spinner size="lg" />
          </div>
        ) : me === null ? (
          // A failed fetch must not read like a switched-off trainer.
          <div className="max-w-xl mx-auto text-center">
            <p className="text-sm" style={{ color: "var(--muted)" }}>{genericErrorMessage()}</p>
            <Link href="/profile" className="btn-primary text-sm rounded-lg px-4 py-2 inline-block mt-4">
              {t("toProfile")}
            </Link>
          </div>
        ) : !offered ? (
          <div className="max-w-xl mx-auto text-center">
            <p className="text-sm" style={{ color: "var(--muted)" }}>{t("notOffered")}</p>
            <Link href="/profile" className="btn-primary text-sm rounded-lg px-4 py-2 inline-block mt-4">
              {t("toProfile")}
            </Link>
          </div>
        ) : (
          <div
            className="rounded-2xl overflow-hidden"
            style={{ border: "1px solid var(--border)", height: "calc(100vh - 12rem)", minHeight: 480 }}
          >
            <LanguageDiagnosisPanel userId={me.id} onComplete={toProfile} onAbort={toProfile} />
          </div>
        )}
      </main>
    </ProtectedRoute>
  );
}
