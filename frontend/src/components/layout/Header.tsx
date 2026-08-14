"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { SignOut, UserCircleGear } from "@phosphor-icons/react";
import { checkAuthStatus, logout } from "@/lib/auth";
import { areaLabelKey } from "@/lib/permissions";
import JobsPanel from "@/components/jobs/JobsPanel";
import HeaderMobileMenu from "@/components/layout/HeaderMobileMenu";
import HeaderLanguageSwitch from "@/components/layout/HeaderLanguageSwitch";
import HeaderThemeToggle from "@/components/layout/HeaderThemeToggle";

interface HeaderProps {
  hasSession?: boolean;
  showLogout?: boolean;
  showToolsToggle?: boolean;
}

export default function Header({ hasSession = true, showLogout = false, showToolsToggle = false }: HeaderProps) {
  const t = useTranslations("header");
  const [isAdmin, setIsAdmin] = useState(false);
  // "Admin" nur fuer den, der wirklich alles darf. Wer nur eine Seite
  // pflegt, geht in seine "Einstellungen".
  const [areaKey, setAreaKey] = useState<"admin" | "settings">("admin");
  const [isLocalMode, setIsLocalMode] = useState(false);
  const [hasTools, setHasTools] = useState(false);

  useEffect(() => {
    if (!showLogout || !hasSession) return;
    checkAuthStatus().then((s) => {
      setIsAdmin(s.is_admin ?? false);
      setAreaKey(areaLabelKey(s.permissions));
      setIsLocalMode(s.local_mode ?? false);
      // Jobs entstehen nur aus Werkzeugen, ohne Werkzeug-Recht bleibt die Liste leer.
      setHasTools((s.permissions?.tools?.length ?? 0) > 0);
    });
  }, [showLogout, hasSession]);

  const handleLogout = async () => {
    await logout();
    // Hard nav so the server layout re-reads the cleared session cookie.
    window.location.assign("/login");
  };

  return (
    <header style={{ backgroundColor: "var(--header-bg)", borderBottom: "1px solid var(--border)" }} className="py-3 hide-on-short">
      <div className="px-4 sm:px-6 flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight flex items-center gap-2">
          <Link
            href="/"
            aria-label={t("homeAria")}
            className="text-white logo-link"
          >
            KIS
          </Link>
          {process.env.NODE_ENV === "development" && (
            <span className="text-xs font-bold px-1.5 py-0.5 rounded" style={{ backgroundColor: "#532bdd", color: "#fff" }}>
              DEV
            </span>
          )}
        </h1>

        {showLogout && (
          <div className="flex items-center gap-1.5">
            <div className="hidden sm:flex items-center gap-1.5">
              {hasSession && hasTools && <JobsPanel />}
              <HeaderLanguageSwitch />
              <HeaderThemeToggle />

              {hasSession && isAdmin && (
                <Link
                  href="/admin"
                  aria-label={t(areaKey)}
                  title={t(areaKey)}
                  className="flex items-center justify-center h-9 px-3 gap-1.5 rounded-full btn-on-dark"
                >
                  <UserCircleGear size={17} weight="bold" />
                  <span className="text-sm font-medium">{t(areaKey)}</span>
                </Link>
              )}

              {hasSession && !isLocalMode && (
                <button
                  onClick={handleLogout}
                  aria-label={t("logout")}
                  title={t("logout")}
                  className="flex items-center justify-center h-9 px-3 gap-1.5 ml-1 rounded-full border border-white/25 btn-on-dark"
                >
                  <SignOut size={17} weight="bold" />
                  <span className="text-sm font-medium">{t("logout")}</span>
                </button>
              )}
            </div>

            <HeaderMobileMenu
              hasSession={hasSession}
              isAdmin={isAdmin}
              areaKey={areaKey}
              hasTools={hasTools}
              isLocalMode={isLocalMode}
              showToolsToggle={showToolsToggle}
              onLogout={handleLogout}
            />
          </div>
        )}
      </div>
    </header>
  );
}
