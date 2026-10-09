"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import Header from "@/components/layout/Header";
import Spinner from "@/components/ui/Spinner";
import Checkbox from "@/components/ui/Checkbox";
import { api } from "@/lib/api";
import { checkAuthStatus, clearAuthCache } from "@/lib/auth";

function isSamePath(path: string | null): path is string {
  return !!path && path.startsWith("/") && !path.startsWith("//");
}

/** The one notice every account confirms once, before any service is reachable. Same screen for TH, external or demo access. */
export default function ConsentPage() {
  const t = useTranslations("consent");
  const router = useRouter();

  const [step, setStep] = useState<"loading" | "consent">("loading");
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [nextPath, setNextPath] = useState("/services");

  useEffect(() => {
    const raw = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("next");
    const target = isSamePath(raw) ? raw : "/services";
    setNextPath(target);

    checkAuthStatus().then((status) => {
      if (!status.authenticated) {
        router.replace("/login");
        return;
      }
      if (status.global_consent_accepted) {
        router.replace(target);
        return;
      }
      setStep("consent");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const accept = async () => {
    if (!read || busy) return;
    setBusy(true);
    try {
      const res = await api.fetch("/api/me/consent", { method: "POST" });
      if (!res.ok) return;
      clearAuthCache();
      // The target page's own WelcomeModal decides from there, once it has loaded.
      router.replace(nextPath);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-dvh flex flex-col">
      <Header showLogout />
      <div className="flex-1 flex items-center justify-center px-4">
        {step === "loading" && <Spinner size="lg" />}
        {step === "consent" && (
          <div className="max-w-lg w-full space-y-6">
            <h1 className="text-2xl font-semibold text-foreground">{t("title")}</h1>
            <p className="text-base leading-relaxed text-foreground-soft">
              {t.rich("body", {
                link: (chunks) => (
                  <Link href="/privacy" target="_blank" rel="noopener noreferrer" className="text-kb hover:underline">
                    {chunks}
                  </Link>
                ),
              })}
            </p>
            <p className="text-sm leading-relaxed text-muted-soft">{t("dataProtection")}</p>
            <Checkbox
              checked={read}
              onChange={setRead}
              label={t("checkbox")}
              labelClassName="whitespace-normal! text-base text-foreground text-left"
              className="items-start!"
            />
            <button
              type="button"
              onClick={() => void accept()}
              disabled={!read || busy}
              className="px-5 py-2.5 text-base font-medium rounded-md btn-primary disabled:opacity-50"
            >
              {t("cta")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
