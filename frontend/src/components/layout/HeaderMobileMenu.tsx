"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CalendarBlank, CaretRight, Check, List, Moon, Question, Sidebar, SignOut, Stack, Sun, UserCircleGear, X } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";
import { useTheme, type Theme } from "@/hooks/useTheme";

const LOCALES = UI_LOCALES as readonly Locale[];
const THEMES: readonly Theme[] = ["light", "dark"];

interface HeaderMobileMenuProps {
  hasSession: boolean;
  isAdmin: boolean;
  areaKey?: "admin" | "settings";
  hasTools?: boolean;
  isLocalMode?: boolean;
  showToolsToggle?: boolean;
  onLogout: () => void;
}

async function persistLocale(locale: Locale) {
  try {
    await fetch("/api/me/locale", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
  } catch {
    // Silently fall back to cookie/URL when backend is unavailable.
  }
}

export default function HeaderMobileMenu({ hasSession, isAdmin, areaKey = "admin", hasTools = false, isLocalMode = false, showToolsToggle = false, onLogout }: HeaderMobileMenuProps) {
  const t = useTranslations("header");
  const tLang = useTranslations("languageSwitch");
  const tManual = useTranslations("manual");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const [open, setOpen] = useState(false);
  const [sheetTop, setSheetTop] = useState(0);
  const { theme, setTheme } = useTheme();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    // The sheet hangs below the header, whose height is only known in the browser.
    const header = ref.current?.closest("header");
    setSheetTop(header ? Math.round(header.getBoundingClientRect().bottom) : 0);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const chooseLocale = (next: Locale) => {
    setOpen(false);
    if (next === currentLocale) return;
    // next-intl sets the language cookie only after startup, then the middleware bounces the first request.
    document.cookie = `NEXT_LOCALE=${next}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };

  const chooseTheme = (next: Theme) => {
    setOpen(false);
    if (next !== theme) setTheme(next);
  };

  const rowClass =
    "flex items-center gap-3 w-full px-4 py-3 text-sm font-medium hover:bg-[var(--surface-dim)] transition-colors no-underline text-left";
  // The row of the page you are currently on stays highlighted.
  const activeRowStyle = { backgroundColor: "var(--surface-dim)", fontWeight: 600 };
  const onCalendar = pathname === "/calendar" || pathname.startsWith("/calendar/");
  const onJobsPage = pathname.startsWith("/my-jobs");
  const headingClass = "px-4 pt-2.5 pb-1 text-2xs font-semibold uppercase tracking-wide";
  // Without a session no navigation rows sit above the language, then the divider is dropped.

  return (
    <div className="sm:hidden relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? t("menuClose") : t("menuOpen")}
        aria-expanded={open}
        className="flex items-center justify-center w-10 h-10 rounded-full btn-on-dark"
      >
        {open ? <X size={20} weight="bold" /> : <List size={20} weight="bold" />}
      </button>

      {open && (
        <div
          className="fixed left-0 right-0 bottom-0 z-50 py-1 overflow-y-auto"
          style={{
            top: sheetTop,
            backgroundColor: "var(--surface)",
            borderTop: "1px solid var(--border)",
          }}
        >
          {hasSession && showToolsToggle && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                window.dispatchEvent(new Event("tools-sidebar:open"));
              }}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <Sidebar size={20} weight="bold" />
              <span className="flex-1">{t("tools")}</span>
              {/* Der Pfeil zeigt, dass hinter der Zeile die Werkzeugleiste aufgeht. */}
              <CaretRight size={14} weight="bold" style={{ color: "var(--muted)" }} aria-hidden="true" />
            </button>
          )}
          {hasSession && (
            <Link
              href="/calendar"
              onClick={() => setOpen(false)}
              aria-current={onCalendar ? "page" : undefined}
              className={rowClass}
              style={{ color: "var(--foreground)", ...(onCalendar ? activeRowStyle : {}) }}
            >
              <CalendarBlank size={20} weight="bold" />
              <span>{t("calendar")}</span>
            </Link>
          )}
          {hasSession && hasTools && (
            <Link
              href="/my-jobs"
              onClick={() => setOpen(false)}
              aria-current={onJobsPage ? "page" : undefined}
              className={rowClass}
              style={{ color: "var(--foreground)", ...(onJobsPage ? activeRowStyle : {}) }}
            >
              <Stack size={20} weight="bold" />
              <span>{t("jobs")}</span>
            </Link>
          )}
          <div
            className={headingClass}
            style={{
              color: "var(--muted)",
              ...(hasSession ? { borderTop: "1px solid var(--border)", marginTop: 4 } : {}),
            }}
          >
            {tLang("title")}
          </div>
          {LOCALES.map((loc) => {
            const isSelected = loc === currentLocale;
            return (
              <button
                key={loc}
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                onClick={() => chooseLocale(loc)}
                className={rowClass}
                style={{ color: "var(--foreground)" }}
              >
                <span className="text-xs uppercase font-mono w-5" style={{ color: "var(--muted)" }} aria-hidden="true">{loc}</span>
                <span className="flex-1" style={{ fontWeight: isSelected ? 600 : 400 }}>{tLang(loc)}</span>
                {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb-dark)" }} aria-hidden="true" />}
              </button>
            );
          })}

          <div className={headingClass} style={{ color: "var(--muted)", borderTop: "1px solid var(--border)", marginTop: 4 }}>
            {t("sectionAppearance")}
          </div>
          {THEMES.map((th) => {
            const isSelected = th === theme;
            return (
              <button
                key={th}
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                onClick={() => chooseTheme(th)}
                className={rowClass}
                style={{ color: "var(--foreground)" }}
              >
                {th === "dark"
                  ? <Moon size={20} weight="bold" aria-hidden="true" />
                  : <Sun size={20} weight="bold" aria-hidden="true" />}
                <span className="flex-1" style={{ fontWeight: isSelected ? 600 : 400 }}>
                  {th === "dark" ? t("themeDark") : t("themeLight")}
                </span>
                {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb-dark)" }} aria-hidden="true" />}
              </button>
            );
          })}

          {hasSession && (
            <Link
              href="/manual"
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--foreground)", borderTop: "1px solid var(--border)", marginTop: 4 }}
            >
              <Question size={20} weight="bold" />
              <span>{tManual("title")}</span>
            </Link>
          )}
          {hasSession && isAdmin && (
            <Link
              href="/admin"
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <UserCircleGear size={20} weight="bold" />
              <span>{t(areaKey)}</span>
            </Link>
          )}
          {hasSession && !isLocalMode && (
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
              className={rowClass}
              // Help, admin and log out are one block, the divider sits above help.
              style={{ color: "var(--foreground)" }}
            >
              <SignOut size={20} weight="bold" />
              <span>{t("logout")}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
