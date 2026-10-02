"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Check, Moon, Sun } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";
import { useTheme } from "@/hooks/useTheme";
import { persistLocale, rememberLocaleCookie } from "@/lib/switchLocale";

const LOCALES = UI_LOCALES as readonly Locale[];

/** Shows the current language only, the choice opens on hover with a mouse and on tap otherwise. */
function LanguageMenu() {
  const tLang = useTranslations("languageSwitch");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  // A click on the button right after the hover opened the menu must not close it again.
  const openedByHover = useRef(false);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent | TouchEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("touchstart", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("touchstart", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const chooseLocale = (next: Locale) => {
    setOpen(false);
    if (next === currentLocale) return;
    rememberLocaleCookie(next);
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };

  return (
    <div
      ref={rootRef}
      className="relative"
      // Touch devices send no pointer enter, so a tap falls through to the click below.
      onPointerEnter={(e) => { if (e.pointerType === "mouse") { openedByHover.current = true; setOpen(true); } }}
      onPointerLeave={(e) => { if (e.pointerType === "mouse") { openedByHover.current = false; setOpen(false); } }}
    >
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={tLang("ariaLabel")}
        title={tLang("title")}
        onClick={() => {
          if (openedByHover.current) { openedByHover.current = false; return; }
          setOpen((v) => !v);
        }}
        className="flex items-center justify-center h-9 px-2.5 rounded-full btn-on-dark text-sm font-medium uppercase"
      >
        {currentLocale}
      </button>
      {open && (
        // The wrapper has no gap to the button, so the pointer never leaves the hover area on the way down.
        <div className="absolute right-0 top-full z-50 pt-1" role="menu" aria-label={tLang("ariaLabel")}>
          <div
            className="w-40 rounded-xl py-1 overflow-hidden"
            style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", boxShadow: "0 8px 24px rgba(0,40,60,0.18)" }}
          >
            {LOCALES.map((loc) => {
              const isSelected = loc === currentLocale;
              return (
                <button
                  key={loc}
                  type="button"
                  role="menuitemradio"
                  aria-checked={isSelected}
                  onClick={() => chooseLocale(loc)}
                  className="flex items-center gap-3 w-full px-4 py-2.5 text-sm font-medium text-left cursor-pointer hover:bg-[var(--surface-dim)] focus:bg-[var(--surface-dim)] outline-none"
                  style={{ color: "var(--foreground)" }}
                >
                  <span className="text-xs uppercase font-mono w-5" style={{ color: "var(--muted)" }} aria-hidden="true">{loc}</span>
                  <span className="flex-1" style={{ fontWeight: isSelected ? 600 : 400 }}>{tLang(loc)}</span>
                  {isSelected && <Check size={14} weight="bold" style={{ color: "var(--kb-dark)" }} aria-hidden="true" />}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/** Language choice and theme toggle for visitors without a session, there is no settings menu to put them in. */
export default function HeaderPublicControls() {
  const t = useTranslations("header");
  const { theme, setTheme } = useTheme();
  const toDark = theme !== "dark";

  return (
    <div className="flex items-center gap-1" data-testid="header-public-controls">
      <LanguageMenu />
      <button
        type="button"
        aria-label={toDark ? t("themeToDarkAria") : t("themeToLightAria")}
        title={toDark ? t("themeDark") : t("themeLight")}
        onClick={() => setTheme(toDark ? "dark" : "light")}
        className="flex items-center justify-center w-9 h-9 rounded-full btn-on-dark"
      >
        {toDark ? <Moon size={18} weight="bold" aria-hidden="true" /> : <Sun size={18} weight="bold" aria-hidden="true" />}
      </button>
    </div>
  );
}
