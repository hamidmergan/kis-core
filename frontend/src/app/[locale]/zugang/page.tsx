"use client";

/** The public access-code page, a stranger redeems a code to get their own account. */

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Eye, EyeSlash } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import { checkForm, MIN_PASSWORD_LENGTH } from "./checkForm";

type Fertig = { username: string; expiresAt: string };

export default function AccessCodePage() {
  const t = useTranslations("accessCode");
  const locale = useLocale();

  const [code, setCode] = useState("");
  const [givenName, setGivenName] = useState("");
  const [surname, setSurname] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [fertig, setFertig] = useState<Fertig | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const geprueft = checkForm({ code, givenName, surname, password, repeat });
    if (!geprueft.ok) {
      setError(
        geprueft.reason === "codeMissing"
          ? t("errorCodeMissing")
          : geprueft.reason === "nameMissing"
            ? t("errorNameMissing")
            : geprueft.reason === "tooShort"
              ? t("errorTooShort", { min: MIN_PASSWORD_LENGTH })
              : t("errorMismatch"),
      );
      return;
    }

    setError(null);
    setSending(true);
    try {
      const r = await fetch("/api/access-codes/redeem", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: code.trim(),
          given_name: givenName.trim(),
          surname: surname.trim(),
          password,
        }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
        return;
      }
      const d = await r.json();
      // The session cookie already arrived with this answer, no extra login needed.
      setFertig({ username: d.username, expiresAt: d.expires_at });
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

  const bisDatum = fertig
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
              <p className="text-sm">{t("doneName", { uid: fertig.username })}</p>
              <p className="text-sm">{t("doneUntil", { date: bisDatum })}</p>
              <p className="text-xs text-muted-soft">{t("doneHint")}</p>
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

                <div>
                  <label htmlFor="access-given-name" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("givenName")}
                  </label>
                  <input
                    id="access-given-name"
                    type="text"
                    value={givenName}
                    onChange={(e) => setGivenName(e.target.value)}
                    required
                    disabled={sending}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                  />
                </div>

                <div>
                  <label htmlFor="access-surname" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("surname")}
                  </label>
                  <input
                    id="access-surname"
                    type="text"
                    value={surname}
                    onChange={(e) => setSurname(e.target.value)}
                    required
                    disabled={sending}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                  />
                  <p className="mt-1.5 text-xs text-muted-soft">{t("nameHint")}</p>
                </div>

                <div>
                  <label htmlFor="access-password" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("password")}
                  </label>
                  <div className="relative">
                    <input
                      id="access-password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="new-password"
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
                  <p className="mt-1.5 text-xs text-muted-soft">
                    {t("passwordHint", { min: MIN_PASSWORD_LENGTH })}
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="access-password-repeat"
                    className="block text-sm font-medium text-foreground-soft mb-1"
                  >
                    {t("passwordRepeat")}
                  </label>
                  <input
                    id="access-password-repeat"
                    type={showPassword ? "text" : "password"}
                    value={repeat}
                    onChange={(e) => setRepeat(e.target.value)}
                    autoComplete="new-password"
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
                  disabled={sending || !code.trim() || !givenName.trim() || !surname.trim() || !password || !repeat}
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
