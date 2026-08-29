"use client";

/** Shown when a test account's access has run out, lets the person renew with a code. */

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Eye, EyeSlash } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";

type Fertig = { expiresAt: string | null };

export default function AccessExpiredPage() {
  const t = useTranslations("accessCode");
  const locale = useLocale();
  const router = useRouter();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [fertig, setFertig] = useState<Fertig | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSending(true);
    try {
      const r = await fetch("/api/access-codes/renew", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password, code: code.trim() }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        if (r.status === 403 && body?.detail === "account_not_activated") {
          router.push("/pending");
          return;
        }
        setError(
          r.status === 401
            ? t("expiredWrongLogin")
            : r.status === 403
              ? t("expiredNotATestAccount")
              : r.status === 404 || r.status === 410
                ? t("expiredDeadCode")
                : t("errorGeneric"),
        );
        return;
      }
      const d = await r.json();
      // The session cookie already arrived with this answer, no extra login needed.
      setFertig({ expiresAt: d.expires_at ?? null });
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

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
          <h1 className="text-2xl font-bold text-center mb-6">{t("expiredTitle")}</h1>

          {fertig ? (
            <div
              data-testid="renew-done"
              className="bg-background rounded-xl shadow-sm border border-border-soft p-8 space-y-4"
            >
              <h2 className="text-lg font-semibold">
                {fertig.expiresAt ? t("expiredDone", { date: bisDatum }) : t("expiredDoneUnlimited")}
              </h2>
              <button
                type="button"
                onClick={() => window.location.assign("/")}
                className="w-full px-4 py-2 text-sm font-medium rounded-md btn-primary"
              >
                {t("doneGo")}
              </button>
            </div>
          ) : (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8">
              <p className="text-sm text-foreground-soft mb-4">{t("expiredText")}</p>

              <form onSubmit={submit} data-testid="renew-form" className="space-y-4">
                <div>
                  <label htmlFor="expired-username" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("expiredUser")}
                  </label>
                  <input
                    id="expired-username"
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                    autoCapitalize="none"
                    autoCorrect="off"
                    spellCheck={false}
                    required
                    disabled={sending}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                  />
                </div>

                <div>
                  <label htmlFor="expired-password" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("expiredPassword")}
                  </label>
                  <div className="relative">
                    <input
                      id="expired-password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="current-password"
                      required
                      disabled={sending}
                      className="w-full px-3 py-2 pr-10 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                      className="absolute inset-y-0 right-0 flex items-center px-3 text-muted hover:text-kb transition-colors"
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeSlash size={16} weight="bold" /> : <Eye size={16} weight="bold" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="expired-code" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("expiredCode")}
                  </label>
                  <input
                    id="expired-code"
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
                </div>

                {error && (
                  <p className="text-sm text-error" role="alert">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={sending || !username.trim() || !password || !code.trim()}
                  className="w-full px-4 py-2 text-sm font-medium rounded-md btn-primary disabled:opacity-50"
                >
                  {sending ? t("expiredSubmitting") : t("expiredSubmit")}
                </button>
              </form>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
