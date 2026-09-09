"use client";

/** The public access-code page, a stranger redeems a code to get their own account. */

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { copyTextFromPromise } from "@/lib/clipboard";
import { checkForm } from "./checkForm";

type Fertig = { username: string; password: string; expiresAt: string | null };
type Kopiert = "user" | "password" | null;

export default function AccessCodePage() {
  return (
    <Suspense>
      <AccessCodePageInner />
    </Suspense>
  );
}

function AccessCodePageInner() {
  const t = useTranslations("accessCode");
  const locale = useLocale();
  const searchParams = useSearchParams();

  // A QR code links here with the code already filled in.
  const codeAusLink = useRef(searchParams.get("code") ?? "").current;
  const [code, setCode] = useState(codeAusLink);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [fertig, setFertig] = useState<Fertig | null>(null);
  const [kopiert, setKopiert] = useState<Kopiert>(null);

  // Same checkmark-for-1500ms feedback as the admin's access-code list.
  function kopieren(feld: Exclude<Kopiert, null>, text: string) {
    copyTextFromPromise(Promise.resolve(text));
    setKopiert(feld);
    setTimeout(() => setKopiert(null), 1500);
  }

  async function redeem(wert: string) {
    const geprueft = checkForm({ code: wert });
    if (!geprueft.ok) {
      setError(t("errorCodeMissing"));
      return;
    }

    setError(null);
    setSending(true);
    try {
      const r = await fetch("/api/access-codes/redeem", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: wert.trim() }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
        return;
      }
      const d = await r.json();
      // The session cookie already arrived with this answer, no extra login needed.
      if (d.show_credentials === false) {
        // An event code with credentials switched off: straight into the app, nothing to note down.
        window.location.assign("/");
        return;
      }
      setFertig({ username: d.username, password: d.password, expiresAt: d.expires_at ?? null });
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    redeem(code);
  }

  // Scanning the QR code (or a shared link) with the code already in the URL needs no click at all.
  const bereitsAusgeloest = useRef(false);
  useEffect(() => {
    if (codeAusLink && !bereitsAusgeloest.current) {
      // React Strict Mode runs effects twice in dev, this must still redeem only once.
      bereitsAusgeloest.current = true;
      redeem(codeAusLink);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // A link with the code already tries the redeem right away, no form ever shows for it,
  // only a failed attempt (wrong/expired code) falls back to the normal form with the error.
  const autoLoeseEin = !!codeAusLink && !fertig && !error;

  const bisDatum = fertig?.expiresAt
    ? new Date(fertig.expiresAt).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : "";

  return (
    <>
      <Header />
      <main className="flex items-start justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-bold text-center mb-6">{t("welcome")}</h1>

          {fertig ? (
            <div
              data-testid="access-code-done"
              className="bg-background rounded-xl shadow-sm border border-border-soft p-8 space-y-4"
            >
              <h2 className="text-lg font-semibold">{t("doneTitle")}</h2>

              <div>
                <p className="text-xs font-medium text-foreground-soft mb-1">{t("doneUser")}</p>
                <div className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
                  <span data-testid="access-code-username" className="font-mono text-sm break-all">
                    {fertig.username}
                  </span>
                  <IconButton
                    size="sm"
                    onClick={() => kopieren("user", fertig.username)}
                    aria-label={kopiert === "user" ? t("copied") : t("copyUser")}
                  >
                    {kopiert === "user" ? (
                      <Check size={14} weight="bold" className="text-kb" />
                    ) : (
                      <Copy size={14} weight="bold" />
                    )}
                  </IconButton>
                </div>
              </div>

              <div>
                <p className="text-xs font-medium text-foreground-soft mb-1">{t("donePassword")}</p>
                <div className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
                  <span data-testid="access-code-password" className="font-mono text-sm break-all">
                    {fertig.password}
                  </span>
                  <IconButton
                    size="sm"
                    onClick={() => kopieren("password", fertig.password)}
                    aria-label={kopiert === "password" ? t("copied") : t("copyPassword")}
                  >
                    {kopiert === "password" ? (
                      <Check size={14} weight="bold" className="text-kb" />
                    ) : (
                      <Copy size={14} weight="bold" />
                    )}
                  </IconButton>
                </div>
              </div>

              <p className="text-xs text-muted-soft">{t("doneOnce")}</p>

              <p className="text-sm">{fertig.expiresAt ? t("doneUntil", { date: bisDatum }) : t("doneUnlimited")}</p>

              <button
                type="button"
                data-testid="access-code-continue"
                onClick={() => window.location.assign("/")}
                className="w-full px-4 py-2 text-sm font-medium rounded-md btn-primary"
              >
                {t("doneGo")}
              </button>
            </div>
          ) : autoLoeseEin ? (
            <div
              data-testid="access-code-auto"
              className="bg-background rounded-xl shadow-sm border border-border-soft p-8 flex flex-col items-center gap-3 text-center"
            >
              <Spinner size="lg" />
              <p className="text-sm text-foreground-soft">{t("autoRedeeming")}</p>
            </div>
          ) : (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8">
              <h2 className="text-lg font-semibold mb-1">{t("title")}</h2>
              <p className="text-sm text-foreground-soft mb-4">{t("intro")}</p>

              <form onSubmit={submit} data-testid="access-code-form" className="space-y-4">
                <div>
                  <label htmlFor="access-code" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("code")}
                  </label>
                  <input
                    id="access-code"
                    type="text"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    required
                    disabled={sending}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                  />
                  <p className="mt-1.5 text-xs text-muted-soft">{t("codeHint")}</p>
                </div>

                {error && (
                  <p className="text-sm text-error" role="alert">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={sending || !code.trim()}
                  className="w-full px-4 py-2 text-sm font-medium rounded-md btn-primary disabled:opacity-50"
                >
                  {sending ? t("submitting") : t("submit")}
                </button>

                <p className="text-center text-sm">
                  <a href="/login" className="text-kb hover:underline">
                    {t("toLogin")}
                  </a>
                </p>
              </form>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
