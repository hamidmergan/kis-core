"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Check, Gear, Info, Moon, Question, SignOut, Sun, UserCircleGear } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { HOME_NOTICE_DISMISS_KEY, HOME_NOTICE_SHOW_EVENT, UI_LOCALES } from "@/lib/constants";
import { useTheme, type Theme } from "@/hooks/useTheme";

const LOCALES = UI_LOCALES as readonly Locale[];
const THEMES: readonly Theme[] = ["light", "dark"];

interface HeaderSettingsMenuProps {
  isAdmin?: boolean;
  areaKey?: "admin" | "settings";
  showLogout?: boolean;
  hasHomeNotice?: boolean;
  onLogout?: () => void;
}

async function persistLocale(locale: Locale) {
  try {
    await fetch("/api/me/locale", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
  } catch {
    // Backend offline / not logged in — cookie + URL still work.
  }
}

export default function HeaderSettingsMenu({ isAdmin = false, areaKey = "admin", showLogout = false, hasHomeNotice = false, onLogout }: HeaderSettingsMenuProps) {
  const t = useTranslations("header");
  const tLang = useTranslations("languageSwitch");
  const tManual = useTranslations("manual");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const { theme, setTheme } = useTheme();

  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  // Remembers which row gets the focus by keyboard after opening.
  const focusOnOpen = useRef<"first" | "last" | null>(null);

  const rows = () => Array.from(menuRef.current?.querySelectorAll<HTMLElement>("[data-row]") ?? []);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (!open || !focusOnOpen.current) return;
    const where = focusOnOpen.current;
    focusOnOpen.current = null;
    (where === "last" ? rows().at(-1) : rows()[0])?.focus();
  }, [open]);

  const close = () => {
    setOpen(false);
    buttonRef.current?.focus();
  };

  const chooseLocale = (next: Locale) => {
    setOpen(false);
    buttonRef.current?.focus();
    if (next === currentLocale) return;
    // next-intl sets the language cookie only after startup, then the middleware bounces the first request.
    document.cookie = `NEXT_LOCALE=${next}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };

  const chooseTheme = (next: Theme) => {
    setOpen(false);
    buttonRef.current?.focus();
    if (next !== theme) setTheme(next);
  };

  const showHomeNotice = () => {
    setOpen(false);
    buttonRef.current?.focus();
    try {
      localStorage.removeItem(HOME_NOTICE_DISMISS_KEY);
    } catch {
      /* ignore - private browsing etc. */
    }
    window.dispatchEvent(new Event(HOME_NOTICE_SHOW_EVENT));
    router.push("/");
  };

  const moveFocus = (step: number) => {
    const list = rows();
    if (list.length === 0) return;
    const at = list.indexOf(document.activeElement as HTMLElement);
    const next = at < 0 ? (step > 0 ? 0 : list.length - 1) : (at + step + list.length) % list.length;
    list[next]?.focus();
  };

  // The browser triggers Enter and Space on the focused row itself.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        focusOnOpen.current = e.key === "ArrowUp" ? "last" : "first";
        setOpen(true);
      }
      return;
    }
    if (e.key === "Escape") { e.preventDefault(); close(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); moveFocus(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); moveFocus(-1); }
    else if (e.key === "Home") { e.preventDefault(); rows()[0]?.focus(); }
    else if (e.key === "End") { e.preventDefault(); rows().at(-1)?.focus(); }
    else if (e.key === "Tab") { setOpen(false); }
  };

  const rowClass =
    "flex items-center gap-3 w-full px-4 py-2.5 text-sm font-medium text-left no-underline cursor-pointer outline-none hover:bg-[var(--surface-dim)] focus:bg-[var(--surface-dim)]";
  const headingClass = "px-4 pt-2.5 pb-1 text-2xs font-semibold uppercase tracking-wide";

  return (
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("settingsMenu")}
        title={t("settingsMenu")}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-9 h-9 rounded-full btn-on-dark"
      >
        <Gear size={18} weight="bold" aria-hidden="true" />
      </button>

      {open && (
        <div
          ref={menuRef}
          role="menu"
          aria-label={t("settingsMenu")}
          className="absolute right-0 top-full mt-2 z-50 w-56 rounded-xl py-1 overflow-hidden"
          style={{
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "0 8px 24px rgba(0,40,60,0.18)",
          }}
        >
          <div className={headingClass} style={{ color: "var(--muted)" }}>{tLang("title")}</div>
          {LOCALES.map((loc) => {
            const isSelected = loc === currentLocale;
            return (
              <button
                key={loc}
                data-row
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                tabIndex={-1}
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
                data-row
                type="button"
                role="menuitemradio"
                aria-checked={isSelected}
                tabIndex={-1}
                onClick={() => chooseTheme(th)}
                className={rowClass}
                style={{ color: "var(--foreground)" }}
              >
                {th === "dark"
                  ? <Moon size={18} weight="bold" aria-hidden="true" />
                  : <Sun size={18} weight="bold" aria-hidden="true" />}
                <span className="flex-1" style={{ fontWeight: isSelected ? 600 : 400 }}>
                  {th === "dark" ? t("themeDark") : t("themeLight")}
                </span>
                {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb-dark)" }} aria-hidden="true" />}
              </button>
            );
          })}

          {hasHomeNotice && (
            <button
              data-row
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={showHomeNotice}
              className={rowClass}
              style={{ color: "var(--foreground)", borderTop: "1px solid var(--border)", marginTop: 4 }}
            >
              <Info size={18} weight="bold" aria-hidden="true" />
              <span className="flex-1">{t("homeNoticeShow")}</span>
            </button>
          )}

          <Link
            data-row
            href="/manual"
            role="menuitem"
            tabIndex={-1}
            onClick={() => setOpen(false)}
            className={rowClass}
            style={{ color: "var(--foreground)", ...(!hasHomeNotice ? { borderTop: "1px solid var(--border)", marginTop: 4 } : {}) }}
          >
            <Question size={18} weight="bold" aria-hidden="true" />
            <span className="flex-1">{tManual("title")}</span>
          </Link>

          {isAdmin && (
            <Link
              data-row
              href="/admin"
              role="menuitem"
              tabIndex={-1}
              onClick={() => setOpen(false)}
              className={rowClass}
              style={{ color: "var(--foreground)" }}
            >
              <UserCircleGear size={18} weight="bold" aria-hidden="true" />
              <span className="flex-1">{t(areaKey)}</span>
            </Link>
          )}

          {showLogout && (
            <button
              data-row
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => {
                setOpen(false);
                onLogout?.();
              }}
              className={rowClass}
              // Help, admin and log out are one block, the divider sits above help.
              style={{ color: "var(--foreground)" }}
            >
              <SignOut size={18} weight="bold" aria-hidden="true" />
              <span className="flex-1">{t("logout")}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
