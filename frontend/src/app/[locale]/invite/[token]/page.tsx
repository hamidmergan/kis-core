"use client";

/** The public invitation page, the key in the URL is the credential. */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Check, Copy, Eye, EyeSlash, WarningCircle } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { copyTextFromPromise } from "@/lib/clipboard";
import { checkPassword, MIN_PASSWORD_LENGTH } from "./checkPassword";

type Einladung = { uid: string };

export default function InvitePage() {
  const t = useTranslations("invite");
  const params = useParams<{ token: string }>();
  const token = String(params?.token ?? "");

  const [einladung, setEinladung] = useState<Einladung | null>(null);
  const [pruefend, setPruefend] = useState(true);
  const [ungueltig, setUngueltig] = useState(false);
  const [ladefehler, setLadefehler] = useState(false);
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [givenName, setGivenName] = useState("");
  const [surname, setSurname] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [kopiert, setKopiert] = useState(false);

  /** Same checkmark-for-1500ms feedback as the access-code page. */
  function benutzernamenKopieren(uid: string) {
    copyTextFromPromise(Promise.resolve(uid));
    setKopiert(true);
    setTimeout(() => setKopiert(false), 1500);
  }

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const r = await fetch(`/api/invites/${encodeURIComponent(token)}`, { cache: "no-store" });
        if (r.ok) {
          const d = await r.json();
          setEinladung({ uid: d.uid });
        } else if (r.status === 404 || r.status === 410) {
          // Only these two really mean 'no longer exists'.
          setUngueltig(true);
        } else {
          setLadefehler(true);
        }
      } catch {
        setLadefehler(true);
      } finally {
        setPruefend(false);
      }
    })();
  }, [token]);

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
      const r = await fetch(`/api/invites/${encodeURIComponent(token)}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          password,
          given_name: givenName.trim(),
          surname: surname.trim(),
        }),
      });
      if (!r.ok) {
        if (r.status === 410) {
          setUngueltig(true);
          return;
        }
        const body = await r.json().catch(() => ({}));
        setError(typeof body?.detail === "string" ? body.detail : t("errorGeneric"));
        return;
      }
      // A hard jump so the server layout reads the fresh session.
      window.location.assign("/services");
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <Header />
      <main className="flex items-start justify-center px-4 py-12">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-bold text-center mb-6">{t("welcome")}</h1>

          {pruefend ? (
            <Spinner className="flex justify-center py-12" />
          ) : ladefehler ? (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8 space-y-4">
              <h2 className="text-lg font-semibold">{t("loadErrorTitle")}</h2>
              <p className="text-sm text-foreground-soft">{t("loadErrorText")}</p>
              <button
                type="button"
                onClick={() => window.location.reload()}
                className="w-full px-4 py-2 text-sm font-medium border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
              >
                {t("retry")}
              </button>
            </div>
          ) : ungueltig ? (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8 space-y-4">
              <h2 className="text-lg font-semibold">{t("invalidTitle")}</h2>
              <div className="flex items-start gap-2 bg-error-bg border border-error-border rounded-md px-3 py-3">
                <WarningCircle size={18} weight="bold" className="mt-0.5 shrink-0 text-error-strong" />
                <span className="text-sm text-error-strong">{t("invalidText")}</span>
              </div>
              <p className="text-sm text-foreground-soft">{t("invalidHint")}</p>
              <a
                href="/login"
                className="block w-full text-center px-4 py-2 text-sm font-medium border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)]"
              >
                {t("toLogin")}
              </a>
            </div>
          ) : (
            <div className="bg-background rounded-xl shadow-sm border border-border-soft p-8">
              <h2 className="text-lg font-semibold mb-4">{t("title")}</h2>

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <span className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("username")}
                  </span>
                  <div className="flex items-center justify-between gap-2 px-3 py-2 border border-border rounded-md">
                    <span data-testid="invite-username" className="font-mono text-sm break-all">
                      {einladung?.uid}
                    </span>
                    <IconButton
                      size="sm"
                      onClick={() => benutzernamenKopieren(einladung?.uid ?? "")}
                      aria-label={kopiert ? t("copied") : t("copyUsername")}
                    >
                      {kopiert ? (
                        <Check size={14} weight="bold" className="text-kb" />
                      ) : (
                        <Copy size={14} weight="bold" />
                      )}
                    </IconButton>
                  </div>
                  <p className="mt-1.5 text-xs text-muted-soft">{t("usernameHint")}</p>
                </div>

                <div>
                  <label htmlFor="invite-password" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("password")}
                  </label>
                  <div className="relative">
                    <input
                      id="invite-password"
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
                  <label htmlFor="invite-password-repeat" className="block text-sm font-medium text-foreground-soft mb-1">
                    {t("passwordRepeat")}
                  </label>
                  <input
                    id="invite-password-repeat"
                    type={showPassword ? "text" : "password"}
                    value={repeat}
                    onChange={(e) => setRepeat(e.target.value)}
                    autoComplete="new-password"
                    required
                    disabled={sending}
                    className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="invite-given-name" className="block text-sm font-medium text-foreground-soft mb-1">
                      {t("givenName")} <span className="font-normal text-muted-soft">{t("optional")}</span>
                    </label>
                    <input
                      id="invite-given-name"
                      type="text"
                      value={givenName}
                      onChange={(e) => setGivenName(e.target.value)}
                      disabled={sending}
                      className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label htmlFor="invite-surname" className="block text-sm font-medium text-foreground-soft mb-1">
                      {t("surname")} <span className="font-normal text-muted-soft">{t("optional")}</span>
                    </label>
                    <input
                      id="invite-surname"
                      type="text"
                      value={surname}
                      onChange={(e) => setSurname(e.target.value)}
                      disabled={sending}
                      className="w-full px-3 py-2 border border-border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-kb focus:border-transparent disabled:opacity-50"
                    />
                  </div>
                </div>

                <p className="text-xs text-muted-soft">{t("nameHint")}</p>

                {error && (
                  <p className="text-sm text-error" role="alert">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={sending || !password || !repeat}
                  className="w-full px-4 py-2 text-sm font-medium rounded-md btn-primary disabled:opacity-50"
                >
                  {sending ? t("submitting") : t("submit")}
                </button>
              </form>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
