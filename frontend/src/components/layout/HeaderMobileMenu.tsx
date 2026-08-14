"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Globe, List, Moon, Sidebar, SignOut, Stack, Sun, UserCircleGear, X } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { useTheme } from "@/hooks/useTheme";

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
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const [open, setOpen] = useState(false);
  const { theme, toggle: toggleTheme } = useTheme();
  const ref = useRef<HTMLDivElement>(null);
  const isDark = theme === "dark";

  useEffect(() => {
    if (!open) return;
    const handler = (e: PointerEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", handler);
    return () => document.removeEventListener("pointerdown", handler);
  }, [open]);

  const toggleLocale = () => {
    const next: Locale = currentLocale === "de" ? "en" : "de";
    router.replace(pathname, { locale: next });
    router.refresh();
    void persistLocale(next);
  };

  const rowClass =
    "flex items-center gap-3 w-full px-4 py-2.5 text-sm font-medium hover:bg-[var(--surface-dim)] transition-colors no-underline text-left";

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
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-xl py-1 overflow-hidden"
          style={{
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
          }}
        >
          <button
            type="button"
            onClick={toggleLocale}
            className={rowClass}
            style={{ color: "var(--foreground)" }}
            aria-label={t("homeAria")}
          >
            <Globe size={20} weight="bold" />
            <span className="flex-1">{currentLocale === "de" ? "Deutsch" : "English"}</span>
            <span className="text-xs font-mono uppercase" style={{ color: "var(--muted)" }}>{currentLocale}</span>
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            className={rowClass}
            style={{ color: "var(--foreground)", borderBottom: "1px solid var(--border)" }}
            aria-label={isDark ? t("themeToLightAria") : t("themeToDarkAria")}
          >
            {isDark ? <Moon size={20} weight="bold" /> : <Sun size={20} weight="bold" />}
            <span className="flex-1">{isDark ? t("themeDark") : t("themeLight")}</span>
          </button>
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
              <span>{t("tools")}</span>
            </button>
          )}
          {hasSession && hasTools && (
            <Link
              href="/my-jobs"
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <Stack size={20} weight="bold" />
              <span>{t("jobs")}</span>
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
              style={{ color: "var(--foreground)", borderTop: "1px solid var(--border)" }}
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
