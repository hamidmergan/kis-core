"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link, useRouter } from "@/i18n/navigation";
import Header from "@/components/layout/Header";
import Spinner from "@/components/ui/Spinner";
import Checkbox from "@/components/ui/Checkbox";
import Modal from "@/components/ui/Modal";
import { api } from "@/lib/api";
import { checkAuthStatus, clearAuthCache } from "@/lib/auth";
import { readPrefs, updatePrefs } from "@/lib/browserStore";
import { EMPTY_PERMS, PERM, hasPerm } from "@/lib/permissions";
import type { UserPermissions } from "@/types";

function isSamePath(path: string | null): path is string {
  return !!path && path.startsWith("/") && !path.startsWith("//");
}

async function pendingWelcomeText(userId: number, perms: UserPermissions): Promise<string | null> {
  if (!hasPerm(perms, PERM.generalWelcome)) return null;
  try {
    const res = await fetch("/api/health/labels", { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    const body = data && typeof data.welcome_modal_text === "string" ? data.welcome_modal_text : "";
    if (!data || data.welcome_modal_enabled !== true || !body.trim()) return null;
    if (readPrefs().welcomeSeen?.includes(userId)) return null;
    return body;
  } catch {
    return null;
  }
}

/** The one notice every account confirms once, before any service is reachable. Same screen for TH, external or demo access. */
export default function ConsentPage() {
  const t = useTranslations("consent");
  const tWelcome = useTranslations("welcomeModal");
  const router = useRouter();

  const [step, setStep] = useState<"loading" | "consent" | "welcome">("loading");
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [userId, setUserId] = useState<number | null>(null);
  const [perms, setPerms] = useState<UserPermissions>(EMPTY_PERMS);
  const [welcomeText, setWelcomeText] = useState("");
  const [nextPath, setNextPath] = useState("/services");

  useEffect(() => {
    const raw = typeof window === "undefined" ? null : new URLSearchParams(window.location.search).get("next");
    if (isSamePath(raw)) setNextPath(raw);

    checkAuthStatus().then(async (status) => {
      if (!status.authenticated) {
        router.replace("/login");
        return;
      }
      const uid = status.user_id ?? null;
      const p = status.permissions ?? EMPTY_PERMS;
      setUserId(uid);
      setPerms(p);

      if (status.global_consent_accepted) {
        const text = uid ? await pendingWelcomeText(uid, p) : null;
        if (text) {
          setWelcomeText(text);
          setStep("welcome");
        } else {
          router.replace(isSamePath(raw) ? raw : "/services");
        }
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
      const text = userId ? await pendingWelcomeText(userId, perms) : null;
      if (text) {
        setWelcomeText(text);
        setStep("welcome");
      } else {
        router.replace(nextPath);
      }
    } finally {
      setBusy(false);
    }
  };

  const finishWelcome = () => {
    if (userId) {
      const seen = readPrefs().welcomeSeen ?? [];
      if (!seen.includes(userId)) updatePrefs({ welcomeSeen: [...seen, userId] });
    }
    router.replace(nextPath);
  };

  return (
    <div className="min-h-dvh flex flex-col">
      <Header showLogout />
      <div className="flex-1 flex items-center justify-center px-4">
        {step === "loading" && <Spinner size="lg" />}
        {step !== "loading" && (
          <div className="max-w-lg w-full space-y-6">
            <h1 className="text-2xl font-semibold text-foreground">{t("title")}</h1>
            <p className="text-base leading-relaxed text-foreground-soft">
              {t.rich("body", {
                link: (chunks) => (
                  <Link href="/privacy" className="text-kb hover:underline">
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
      <Modal
        open={step === "welcome"}
        onClose={finishWelcome}
        title={tWelcome("title")}
        footer={
          <button type="button" onClick={finishWelcome} className="btn-primary text-sm rounded-lg px-4 py-2">
            {tWelcome("cta")}
          </button>
        }
      >
        <p className="text-sm whitespace-pre-line">{welcomeText}</p>
      </Modal>
    </div>
  );
}
