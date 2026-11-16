"use client";

/** The public page of a reset link, the key in the URL is the credential. */

import { useState } from "react";
import { useParams } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { CheckCircle, WarningCircle } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import Spinner from "@/components/ui/Spinner";
import NewPasswordFields from "@/components/auth/NewPasswordFields";
import { useTokenCheck } from "@/components/auth/useTokenCheck";
import { checkPassword, MIN_PASSWORD_LENGTH } from "../../invite/[token]/checkPassword";

export default function ResetPasswordPage() {
  const t = useTranslations("resetPassword");
  const params = useParams<{ token: string }>();
  const token = String(params?.token ?? "");

  const { uid, pruefend, ungueltig, setUngueltig, ladefehler } = useTokenCheck("/api/password-reset", token);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [fertig, setFertig] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const geprueft = checkPassword(password, repeat);
    if (!geprueft.ok) {
      setError(
        geprueft.reason === "tooShort"
          ? t("errorTooShort", { min: MIN_PASSWORD_LENGTH })
          : t("errorMismatch"),
      );
      return;
    }
    setError(null);
    setSending(true);
    try {
      const r = await fetch(`/api/password-reset/${encodeURIComponent(token)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (r.ok) {
        setFertig(true);
      } else if (r.status === 410) {
        setUngueltig(true);
      } else {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
      }
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

  const toLogin = (
    <Link href="/login" className="block w-full text-center px-4 py-3 text-base font-medium btn-secondary rounded-lg">
      {t("toLogin")}
    </Link>
  );

  return (
    <div className="flex flex-col min-h-dvh">
      <Header />
      <main className="flex flex-1 items-center px-6 py-10 sm:px-10">
        <div className="w-full max-w-md mx-auto">
          {pruefend ? (
            <Spinner className="flex justify-center py-12" />
          ) : ladefehler ? (
            <div className="space-y-4">
              <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("loadErrorTitle")}</h1>
              <p className="text-sm text-foreground-soft">{t("loadErrorText")}</p>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="w-full px-4 py-3 text-base font-medium btn-secondary rounded-lg"
              >
                {t("retry")}
              </button>
            </div>
          ) : fertig ? (
            <div className="space-y-4">
              <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-[-0.01em] text-foreground">
                <CheckCircle size={26} weight="bold" className="text-kb" />
                {t("doneTitle")}
              </h1>
              <p className="text-sm text-foreground-soft">{t("doneText")}</p>
              {toLogin}
            </div>
          ) : ungueltig ? (
            <div className="space-y-4">
              <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("invalidTitle")}</h1>
              <div className="flex items-start gap-2 bg-error-bg border border-error-border rounded-md px-3 py-3">
                <WarningCircle size={18} weight="bold" className="mt-0.5 shrink-0 text-error-strong" />
                <span className="text-sm text-error-strong">{t("invalidText")}</span>
              </div>
              <p className="text-sm text-foreground-soft">{t("invalidHint")}</p>
              {toLogin}
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h1>
              <p className="mt-2 text-sm text-foreground-soft">{t("intro")}</p>
              <form onSubmit={submit} className="mt-6 space-y-5">
                <div>
                  <span className="block text-sm font-medium text-foreground-soft mb-1.5">{t("username")}</span>
                  <div className="rounded-lg border-2 border-border px-3 py-2.5">
                    <span data-testid="reset-username" className="font-mono text-base break-all">{uid}</span>
                  </div>
                </div>

                <NewPasswordFields
                  namespace="resetPassword"
                  idPrefix="reset"
                  password={password}
                  repeat={repeat}
                  onPassword={setPassword}
                  onRepeat={setRepeat}
                  disabled={sending}
                />

                {error && (
                  <div role="alert" className="flex items-start gap-2 bg-error-bg border border-error-border rounded-md px-3 py-3">
                    <WarningCircle size={18} weight="bold" className="mt-0.5 shrink-0 text-error-strong" />
                    <span className="text-sm text-error-strong">{error}</span>
                  </div>
                )}

                <button
                  type="submit"
                  disabled={sending}
                  className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {sending && <Spinner size="xs" color="current" />}
                  {t("submit")}
                </button>
              </form>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
