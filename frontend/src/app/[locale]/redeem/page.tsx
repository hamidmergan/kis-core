"use client";

/** The public access-code page, a stranger redeems a code to get their own account. */

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import AuthSplit from "@/components/layout/AuthSplit";
import { Link } from "@/i18n/navigation";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { copyTextFromPromise } from "@/lib/clipboard";
import { checkAuthStatus } from "@/lib/auth";
import { checkForm } from "./checkForm";

const FIELD =
  "w-full px-3 py-2.5 text-base bg-background text-foreground border-2 border-border rounded-lg outline-none hover:border-kb focus:border-kb transition-colors disabled:opacity-50";

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
  // A plain link only fills in the field, redeeming stays the person's own click.
  const vorbelegt = useRef(searchParams.get("vorbelegt") ?? "").current;
  const [code, setCode] = useState(codeAusLink || vorbelegt);
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
        window.location.assign("/workspace");
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
      checkAuthStatus().then((s) => (s.authenticated ? window.location.assign("/workspace") : redeem(codeAusLink)));
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
    <AuthSplit heading={t("welcome")}>
      <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">
        {fertig ? t("doneTitle") : t("title")}
      </h2>

      {fertig ? (
        <div data-testid="access-code-done" className="mt-6 space-y-5">
          {(["user", "password"] as const).map((f) => {
            const wert = f === "user" ? fertig.username : fertig.password;
            return (
              <div key={f}>
                <p className="text-sm font-medium text-foreground-soft mb-1.5">
                  {f === "user" ? t("doneUser") : t("donePassword")}
                </p>
                <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-border px-3 py-2.5">
                  <span data-testid={f === "user" ? "access-code-username" : "access-code-password"} className="font-mono text-base break-all">
                    {wert}
                  </span>
                  <IconButton
                    size="sm"
                    onClick={() => kopieren(f, wert)}
                    aria-label={kopiert === f ? t("copied") : f === "user" ? t("copyUser") : t("copyPassword")}
                  >
                    {kopiert === f ? <Check size={14} weight="bold" className="text-kb" /> : <Copy size={14} weight="bold" />}
                  </IconButton>
                </div>
              </div>
            );
          })}
          <p className="text-sm text-muted">{t("doneOnce")}</p>
          <p className="text-sm text-foreground">
            {fertig.expiresAt ? t("doneUntil", { date: bisDatum }) : t("doneUnlimited")}
          </p>
          <button
            type="button"
            data-testid="access-code-continue"
            onClick={() => window.location.assign("/workspace")}
            className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
          >
            {t("doneGo")}
          </button>
        </div>
      ) : autoLoeseEin ? (
        <div data-testid="access-code-auto" className="mt-6 flex items-center gap-3">
          <Spinner size="lg" />
          <p className="text-sm text-foreground-soft">{t("autoRedeeming")}</p>
        </div>
      ) : (
        <form onSubmit={submit} data-testid="access-code-form" className="mt-6 space-y-5">
          <p className="text-sm text-foreground-soft">{t("intro")}</p>
          <div>
            <label htmlFor="access-code" className="block text-sm font-medium text-foreground-soft mb-1.5">
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
              placeholder={t("codeHint")}
              className={`${FIELD} font-mono`}
            />
          </div>

          {error && (
            <p className="text-sm text-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={sending || !code.trim()}
            className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
          >
            {sending ? t("submitting") : t("submit")}
          </button>
        </form>
      )}

      <Link href="/login" className="mt-6 inline-block text-sm text-kb-dark hover:underline">
        {t("toLogin")}
      </Link>
    </AuthSplit>
  );
}
