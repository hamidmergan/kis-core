"use client";

import Link from "next/link";
import LinkBusy from "@/components/ui/LinkBusy";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CalendarBlank, Toolbox } from "@phosphor-icons/react";
import { usePathname } from "@/i18n/navigation";
import { checkAuthStatus, logout } from "@/lib/auth";
import { api } from "@/lib/api";
import { areaLabelKey, hasPerm, PERM, type AreaKey } from "@/lib/permissions";
import JobsPanel from "@/components/jobs/JobsPanel";
import HeaderMobileMenu from "@/components/layout/HeaderMobileMenu";
import HeaderSettingsMenu from "@/components/layout/HeaderSettingsMenu";
import { useTourStart } from "@/app/[locale]/workspace/_components/useTourStart";

interface HeaderProps {
  hasSession?: boolean;
  showLogout?: boolean;
}

export default function Header({ hasSession = true, showLogout = false }: HeaderProps) {
  const t = useTranslations("header");
  const pathname = usePathname();
  // The URL says where you are, the button in the header shows it.
  const onCalendar = pathname === "/calendar" || pathname.startsWith("/calendar/");
  const onTools = pathname.startsWith("/tools/");
  const [isAdmin, setIsAdmin] = useState(false);
  const [canViewManual, setCanViewManual] = useState(false);
  // Admin only for whoever may do everything, everyone else goes to their settings.
  const [areaKey, setAreaKey] = useState<AreaKey>("admin");
  const [isLocalMode, setIsLocalMode] = useState(false);
  const [hasTools, setHasTools] = useState(false);
  // A missing modules field means an older server, which always has both.
  const [hasAia, setHasAia] = useState(true);
  // The language level page hangs off its own permission, not off the role.
  const [mayLanguageLevel, setMayLanguageLevel] = useState(false);
  // Only true with an admin-enabled, non-empty text — otherwise the menu row would be a dead click.
  const [hasHomeNotice, setHasHomeNotice] = useState(false);
  // The start-page card can be dismissed for good, the menu row is the way back to it.
  const [evaluationActive, setEvaluationActive] = useState(false);
  // The tour lives in the demo course, the menu only offers it while one exists.
  const tour = useTourStart(showLogout && hasSession);

  useEffect(() => {
    if (!showLogout || !hasSession) return;
    checkAuthStatus().then((s) => {
      setIsAdmin(s.is_admin ?? false);
      setCanViewManual(hasPerm(s.permissions, PERM.manual));
      setAreaKey(areaLabelKey(s.permissions));
      setIsLocalMode(s.local_mode ?? false);
      // Jobs only come from tools, without a tool permission the list stays empty.
      setHasTools((s.permissions?.tools?.length ?? 0) > 0);
      setHasAia((s.modules ?? ["aia", "tools"]).includes("aia"));
      setMayLanguageLevel(hasPerm(s.permissions, PERM.aiaLanguageLevel));
    });
  }, [showLogout, hasSession]);

  useEffect(() => {
    if (!showLogout) return;
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        const text = typeof data.home_notice_text === "string" ? data.home_notice_text : "";
        setHasHomeNotice(data.home_notice_enabled === true && text.trim().length > 0);
      })
      .catch(() => {
        /* ignore - menu row just stays hidden */
      });
    return () => {
      cancelled = true;
    };
  }, [showLogout]);

  useEffect(() => {
    if (!showLogout || !hasSession) return;
    let cancelled = false;
    api
      .fetch("/api/evaluation/active", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setEvaluationActive(data.active === true);
      })
      .catch(() => {
        /* ignore - menu row just stays hidden */
      });
    return () => {
      cancelled = true;
    };
  }, [showLogout, hasSession]);

  const handleLogout = async () => {
    await logout();
    // Hard nav so the server layout re-reads the cleared session cookie.
    window.location.assign("/login");
  };

  return (
    <header style={{ backgroundColor: "var(--header-bg)", borderBottom: "1px solid var(--border)" }} className="py-3 compact-on-short">
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
              {hasSession && hasTools && (
                <Link
                  href="/"
                  aria-label={t("tools")}
                  title={t("tools")}
                  aria-current={onTools ? "page" : undefined}
                  className={`flex items-center justify-center h-9 px-3 gap-1.5 rounded-full btn-on-dark${onTools ? " is-active" : ""}`}
                >
                  <LinkBusy size="sm">
                    <Toolbox size={17} weight="bold" />
                  </LinkBusy>
                  <span className="text-sm font-medium">{t("tools")}</span>
                </Link>
              )}
              {hasSession && hasAia && (
                <Link
                  href="/calendar"
                  aria-label={t("calendar")}
                  title={t("calendar")}
                  aria-current={onCalendar ? "page" : undefined}
                  className={`flex items-center justify-center h-9 px-3 gap-1.5 rounded-full btn-on-dark${onCalendar ? " is-active" : ""}`}
                >
                  <LinkBusy size="sm">
                    <CalendarBlank size={17} weight="bold" />
                  </LinkBusy>
                  <span className="text-sm font-medium">{t("calendar")}</span>
                </Link>
              )}
              {hasSession && hasTools && <JobsPanel />}
              <HeaderSettingsMenu
                isAdmin={hasSession && isAdmin}
                canViewManual={hasSession && canViewManual}
                showLanguageLevel={hasSession && mayLanguageLevel}
                showTour={hasSession && hasAia && tour.available}
                onStartTour={tour.start}
                showEvaluation={hasSession && evaluationActive}
                areaKey={areaKey}
                showLogout={hasSession && !isLocalMode}
                hasHomeNotice={hasHomeNotice}
                onLogout={handleLogout}
              />
            </div>

            <HeaderMobileMenu
              hasSession={hasSession}
              isAdmin={isAdmin}
              canViewManual={canViewManual}
              showLanguageLevel={mayLanguageLevel}
              showTour={hasAia && tour.available}
              onStartTour={tour.start}
              showEvaluation={evaluationActive}
              areaKey={areaKey}
              hasTools={hasTools}
              hasAia={hasAia}
              isLocalMode={isLocalMode}
              hasHomeNotice={hasHomeNotice}
              onLogout={handleLogout}
            />
          </div>
        )}
      </div>
    </header>
  );
}
