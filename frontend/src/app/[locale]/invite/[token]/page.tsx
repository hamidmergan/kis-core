"use client";

/** The public invitation page, the key in the URL is the credential. */

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { Check, Copy, Eye, EyeSlash, WarningCircle } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import { copyTextFromPromise } from "@/lib/clipboard";
import { checkPassword, MIN_PASSWORD_LENGTH } from "./checkPassword";

const FIELD =
  "w-full px-3 py-2.5 text-base bg-background text-foreground border-2 border-border rounded-lg outline-none hover:border-kb focus:border-kb transition-colors disabled:opacity-50";

type Einladung = { uid: string };

export default function InvitePage() {
  const t = useTranslations("invite");
  const tl = useTranslations("login");
  const params = useParams<{ token: string }>();
  const token = String(params?.token ?? "");
  const { variant } = useMascotPref();

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
      window.location.assign("/workspace");
    } catch {
      setError(t("errorGeneric"));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col lg:min-h-dvh">
      <Header />
      <main className="grid lg:flex-1 lg:grid-cols-[5fr_6fr]">
        <h1 className="sr-only">{t("welcome")}</h1>
        <section className="relative hidden lg:flex items-center justify-center bg-kb px-14 py-14">
          <div className="flex w-full max-w-md flex-col items-center">
            <div className="relative">
              <span
                aria-hidden="true"
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-72 w-72 rounded-full border-2 border-white/15"
              />
              <span
                aria-hidden="true"
                className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-52 w-52 rounded-full bg-white/10"
              />
              <div className="relative"><Mascot variant={variant} size={200} state="wave" /></div>
            </div>
            <div className="mt-16 text-center">
              <p className="text-2xl font-semibold leading-snug text-on-accent">{tl("francisName")}</p>
              <p className="mt-1 text-base text-on-accent/80">{tl("francisRole")}</p>
            </div>
          </div>
        </section>

        <section className="flex items-center px-6 py-10 sm:px-10 lg:px-16">
          <div className="w-full max-w-md mx-auto lg:mx-0">
            {pruefend ? (
              <Spinner className="flex justify-center py-12" />
            ) : ladefehler ? (
              <div className="space-y-4">
                <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("loadErrorTitle")}</h2>
                <p className="text-sm text-foreground-soft">{t("loadErrorText")}</p>
                <button
                  type="button"
                  onClick={() => window.location.reload()}
                  className="w-full px-4 py-3 text-base font-medium btn-secondary rounded-lg"
                >
                  {t("retry")}
                </button>
              </div>
            ) : ungueltig ? (
              <div className="space-y-4">
                <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("invalidTitle")}</h2>
                <div className="flex items-start gap-2 bg-error-bg border border-error-border rounded-md px-3 py-3">
                  <WarningCircle size={18} weight="bold" className="mt-0.5 shrink-0 text-error-strong" />
                  <span className="text-sm text-error-strong">{t("invalidText")}</span>
                </div>
                <p className="text-sm text-foreground-soft">{t("invalidHint")}</p>
                <Link href="/login" className="block w-full text-center px-4 py-3 text-base font-medium btn-secondary rounded-lg">
                  {t("toLogin")}
                </Link>
              </div>
            ) : (
              <>
                <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h2>

                <form onSubmit={submit} className="mt-6 space-y-5">
                  <div>
                    <span className="block text-sm font-medium text-foreground-soft mb-1.5">
                      {t("username")}
                    </span>
                    <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-border px-3 py-2.5">
                      <span data-testid="invite-username" className="font-mono text-base break-all">
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
                    <label htmlFor="invite-password" className="block text-sm font-medium text-foreground-soft mb-1.5">
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
                        className={`${FIELD} pr-11`}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        aria-label={showPassword ? t("hidePassword") : t("showPassword")}
                        className="absolute inset-y-0 right-0 flex items-center px-3 text-muted hover:text-kb transition-colors"
                        tabIndex={-1}
                      >
                        {showPassword ? <EyeSlash size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
                      </button>
                    </div>
                    <p className="mt-1.5 text-xs text-muted-soft">
                      {t("passwordHint", { min: MIN_PASSWORD_LENGTH })}
                    </p>
                  </div>

                  <div>
                    <label htmlFor="invite-password-repeat" className="block text-sm font-medium text-foreground-soft mb-1.5">
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
                      className={FIELD}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="invite-given-name" className="block text-sm font-medium text-foreground-soft mb-1.5">
                        {t("givenName")} <span className="font-normal text-muted-soft">{t("optional")}</span>
                      </label>
                      <input
                        id="invite-given-name"
                        type="text"
                        value={givenName}
                        onChange={(e) => setGivenName(e.target.value)}
                        disabled={sending}
                        className={FIELD}
                      />
                    </div>
                    <div>
                      <label htmlFor="invite-surname" className="block text-sm font-medium text-foreground-soft mb-1.5">
                        {t("surname")} <span className="font-normal text-muted-soft">{t("optional")}</span>
                      </label>
                      <input
                        id="invite-surname"
                        type="text"
                        value={surname}
                        onChange={(e) => setSurname(e.target.value)}
                        disabled={sending}
                        className={FIELD}
                      />
                    </div>
                  </div>

                  <p className="text-sm text-foreground-soft">{t("nameHint")}</p>

                  {error && (
                    <p className="text-sm text-error" role="alert">
                      {error}
                    </p>
                  )}

                  <button
                    type="submit"
                    disabled={sending || !password || !repeat}
                    className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
                  >
                    {sending ? t("submitting") : t("submit")}
                  </button>
                </form>
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
