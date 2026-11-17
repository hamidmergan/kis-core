"use client";

/** Redeeming an access code, shared by the code tab of the login and the public code page. */

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import { AUTH_FIELD } from "@/components/auth/authField";
import { copyTextFromPromise } from "@/lib/clipboard";
import { checkForm } from "./checkForm";

export type Fertig = { username: string; password: string; expiresAt: string | null };

/** The day an access runs out, in the way all three access-code pages write it. */
export function formatUntil(iso: string | null | undefined, locale: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Berlin",
  });
}

/** The code field with its request, an event code without credentials goes straight into the app. */
export function useAccessCode(initial = "") {
  const t = useTranslations("accessCode");
  const [code, setCode] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [fertig, setFertig] = useState<Fertig | null>(null);

  async function redeem(value: string) {
    if (!checkForm({ code: value }).ok) {
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
        body: JSON.stringify({ code: value.trim() }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
        return;
      }
      const d = await r.json();
      // The session cookie already arrived with this answer, an event code without credentials goes straight in.
      if (d.show_credentials === false) {
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

  return { code, setCode, error, sending, fertig, redeem };
}

type AccessCode = ReturnType<typeof useAccessCode>;

/** The form a code is typed into. */
export function AccessCodeForm({ state }: { state: AccessCode }) {
  const t = useTranslations("accessCode");
  const { code, setCode, error, sending, redeem } = state;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        redeem(code);
      }}
      data-testid="access-code-form"
      className="mt-6 space-y-5"
    >
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
          className={`${AUTH_FIELD} font-mono`}
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
  );
}

/** The fresh account, shown once, with a copy button per line. */
export function AccessCodeDone({ fertig }: { fertig: Fertig }) {
  const t = useTranslations("accessCode");
  const locale = useLocale();
  const [kopiert, setKopiert] = useState<"user" | "password" | null>(null);

  function copy(field: "user" | "password", text: string) {
    copyTextFromPromise(Promise.resolve(text));
    setKopiert(field);
    setTimeout(() => setKopiert(null), 1500);
  }

  return (
    <div data-testid="access-code-done" className="mt-6 space-y-5">
      {(["user", "password"] as const).map((f) => {
        const value = f === "user" ? fertig.username : fertig.password;
        return (
          <div key={f}>
            <p className="text-sm font-medium text-foreground-soft mb-1.5">
              {f === "user" ? t("doneUser") : t("donePassword")}
            </p>
            <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-border px-3 py-2.5">
              <span data-testid={f === "user" ? "access-code-username" : "access-code-password"} className="font-mono text-base break-all">
                {value}
              </span>
              <IconButton
                size="sm"
                onClick={() => copy(f, value)}
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
        {fertig.expiresAt ? t("doneUntil", { date: formatUntil(fertig.expiresAt, locale) }) : t("doneUnlimited")}
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
  );
}
