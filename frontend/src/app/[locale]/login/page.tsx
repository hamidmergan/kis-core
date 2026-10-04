"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Check, Copy, Eye, EyeSlash } from "@phosphor-icons/react";
import Header from "@/components/layout/Header";
import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";
import IconButton from "@/components/ui/IconButton";
import Tabs from "@/components/ui/Tabs";
import { login, checkAuthStatus } from "@/lib/auth";
import { copyTextFromPromise } from "@/lib/clipboard";
import { alreadySignedIn } from "../redeem/alreadySignedIn";
import { checkForm } from "../redeem/checkForm";

const FIELD =
  "w-full px-3 py-2.5 text-base bg-background text-foreground border-2 border-border rounded-lg outline-none hover:border-kb focus:border-kb transition-colors disabled:opacity-50";

type Fertig = { username: string; password: string; expiresAt: string | null };

export default function LoginPage() {
  const t = useTranslations("login");
  const tc = useTranslations("accessCode");
  const locale = useLocale();
    const router = useRouter();
  const { variant } = useMascotPref();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [loading, setLoading] = useState(false);
  const [maintenanceOn, setMaintenanceOn] = useState(false);
  const [zugangOffen, setZugangOffen] = useState(false);
  const [abgelaufen, setAbgelaufen] = useState(false);
  const [tab, setTab] = useState<"login" | "code">("login");
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);
  const [codeSending, setCodeSending] = useState(false);
  const [fertig, setFertig] = useState<Fertig | null>(null);
  const [kopiert, setKopiert] = useState<"user" | "password" | null>(null);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      if (status.authenticated) router.replace("/services");
      else setChecking(false);
    });
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch("/api/health/maintenance", { cache: "no-store" });
        if (!res.ok) return;
        const d = await res.json();
        if (!cancelled) setMaintenanceOn(!!d.enabled);
      } catch {
        /* ignore */
      }
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  // Whoever was thrown out by an expired access arrives with this marker in the address.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("expired")) setAbgelaufen(true);
  }, []);

  // A QR code links here with the code in the address, that opens the code tab and redeems it at once.
  const autoDone = useRef(false);
  useEffect(() => {
    const fromLink = new URLSearchParams(window.location.search).get("code");
    if (fromLink && !autoDone.current) {
      autoDone.current = true;
      setTab("code");
      setCode(fromLink);
      alreadySignedIn().then((ja) => (ja ? window.location.assign("/services") : redeem(fromLink)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetch("/api/access-codes/enabled", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setZugangOffen(!!d?.enabled))
      .catch(() => {});
  }, []);

  async function redeem(value: string) {
    if (!checkForm({ code: value }).ok) {
      setCodeError(tc("errorCodeMissing"));
      return;
    }
    setCodeError(null);
    setCodeSending(true);
    try {
      const r = await fetch("/api/access-codes/redeem", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: value.trim() }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setCodeError(typeof body?.detail === "string" ? body.detail : tc("errorGeneric"));
        return;
      }
      const d = await r.json();
      // The session cookie already arrived with this answer, an event code without credentials goes straight in.
      if (d.show_credentials === false) {
        window.location.assign("/services");
        return;
      }
      setFertig({ username: d.username, password: d.password, expiresAt: d.expires_at ?? null });
    } catch {
      setCodeError(tc("errorGeneric"));
    } finally {
      setCodeSending(false);
    }
  }

  function copy(field: "user" | "password", text: string) {
    copyTextFromPromise(Promise.resolve(text));
    setKopiert(field);
    setTimeout(() => setKopiert(null), 1500);
  }

  const untilDate = fertig?.expiresAt
    ? new Date(fertig.expiresAt).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Berlin",
      })
    : "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
      await checkAuthStatus();
      // A hard navigation so the server reads the new session cookie.
      window.location.assign("/services");
      return;
    } catch (err) {
      const message = err instanceof Error ? err.message : "";
      if (message === "account_not_activated") router.push("/pending");
      else if (message === "access_expired") setAbgelaufen(true);
      else if (maintenanceOn) setError(t("maintenanceBanner"));
      else setError(t("invalidCredentials"));
    } finally {
      setLoading(false);
    }
  };

  if (checking) return null;

  return (
    <div className="flex flex-col lg:min-h-dvh">
    <Header hasSession={false} showLogout hideLogin />
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
            <p className="text-2xl font-semibold leading-snug text-on-accent">{t("francisName")}</p>
            <p className="mt-1 text-base text-on-accent/80">{t("francisRole")}</p>
          </div>
        </div>
      </section>

      <section className="flex items-center px-6 py-10 sm:px-10 lg:px-16">
        <div className="w-full max-w-md mx-auto lg:mx-0">
          <h2 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">
            {fertig ? tc("doneTitle") : t("title")}
          </h2>
          {zugangOffen && !fertig && (
            <Tabs
              items={[
                { key: "login", label: t("tabAccount") },
                { key: "code", label: t("tabCode") },
              ]}
              active={tab}
              onChange={setTab}
              className="mt-5 text-base"
            />
          )}

          {tab === "login" && abgelaufen && (
            <div
              role="status"
              data-testid="login-expired"
              className="mt-5 rounded-lg border-2 border-border bg-surface-dim p-4 text-foreground"
            >
              <p className="text-sm font-semibold">{t("expiredTitle")}</p>
              <p className="mt-1 text-sm leading-relaxed text-foreground-soft">{t("expiredText")}</p>
              <a href="mailto:hamid.mergan@th-luebeck.de" className="mt-2 inline-block text-sm text-kb-dark hover:underline">
                hamid.mergan@th-luebeck.de
              </a>
            </div>
          )}

          {tab === "login" && (
          <form onSubmit={handleSubmit} aria-label={t("formAria")} className="mt-6 space-y-5">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-foreground-soft mb-1.5">
                {t("username")}
              </label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                autoFocus
                required
                disabled={loading}
                className={FIELD}
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-foreground-soft mb-1.5">
                {t("password")}
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  disabled={loading}
                  aria-describedby={error ? "login-error" : undefined}
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
            </div>

            {error && (
              <p id="login-error" className="text-sm text-error" role="alert">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !username.trim() || !password}
              className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
            >
              {loading ? t("submitting") : t("submit")}
            </button>
          </form>
          )}

          {tab === "code" && !fertig && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                redeem(code);
              }}
              data-testid="access-code-form"
              className="mt-6 space-y-5"
            >
              <p className="text-sm text-foreground-soft">{tc("intro")}</p>
              <div>
                <label htmlFor="access-code" className="block text-sm font-medium text-foreground-soft mb-1.5">
                  {tc("code")}
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
                  disabled={codeSending}
                  placeholder={tc("codeHint")}
                  className={`${FIELD} font-mono`}
                />
              </div>
              {codeError && (
                <p className="text-sm text-error" role="alert">
                  {codeError}
                </p>
              )}
              <button
                type="submit"
                disabled={codeSending || !code.trim()}
                className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
              >
                {codeSending ? tc("submitting") : tc("submit")}
              </button>
            </form>
          )}

          {fertig && (
            <div data-testid="access-code-done" className="mt-6 space-y-5">
              {(["user", "password"] as const).map((f) => {
                const value = f === "user" ? fertig.username : fertig.password;
                return (
                  <div key={f}>
                    <p className="text-sm font-medium text-foreground-soft mb-1.5">
                      {f === "user" ? tc("doneUser") : tc("donePassword")}
                    </p>
                    <div className="flex items-center justify-between gap-2 rounded-lg border-2 border-border px-3 py-2.5">
                      <span data-testid={f === "user" ? "access-code-username" : "access-code-password"} className="font-mono text-base break-all">
                        {value}
                      </span>
                      <IconButton
                        size="sm"
                        onClick={() => copy(f, value)}
                        aria-label={kopiert === f ? tc("copied") : f === "user" ? tc("copyUser") : tc("copyPassword")}
                      >
                        {kopiert === f ? <Check size={14} weight="bold" className="text-kb" /> : <Copy size={14} weight="bold" />}
                      </IconButton>
                    </div>
                  </div>
                );
              })}
              <p className="text-sm text-muted">{tc("doneOnce")}</p>
              <p className="text-sm text-foreground">
                {fertig.expiresAt ? tc("doneUntil", { date: untilDate }) : tc("doneUnlimited")}
              </p>
              <button
                type="button"
                data-testid="access-code-continue"
                onClick={() => window.location.assign("/services")}
                className="w-full px-4 py-3 text-base font-medium btn-primary rounded-lg"
              >
                {tc("doneGo")}
              </button>
            </div>
          )}
        </div>
      </section>
    </main>
    </div>
  );
}
