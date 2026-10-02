"use client";

import { useLocale, useTranslations } from "next-intl";
import { Moon, Sun } from "@phosphor-icons/react";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";
import { useTheme } from "@/hooks/useTheme";
import { persistLocale, rememberLocaleCookie } from "@/lib/switchLocale";

const LOCALES = UI_LOCALES as readonly Locale[];

/** Language switch and theme toggle for visitors without a session, there is no settings menu to put them in. */
export default function HeaderPublicControls() {
  const t = useTranslations("header");
  const tLang = useTranslations("languageSwitch");
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const { theme, setTheme } = useTheme();
  const toDark = theme !== "dark";

  const chooseLocale = (next: Locale) => {
    if (next === currentLocale) return;
    rememberLocaleCookie(next);
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };

  return (
    <div className="flex items-center gap-1" data-testid="header-public-controls">
      <div role="group" aria-label={tLang("ariaLabel")} className="flex items-center">
        {LOCALES.map((loc) => (
          <button
            key={loc}
            type="button"
            aria-pressed={loc === currentLocale}
            title={tLang(loc)}
            onClick={() => chooseLocale(loc)}
            className={`flex items-center justify-center h-9 px-2 rounded-full btn-on-dark text-sm font-medium uppercase${loc === currentLocale ? " is-active" : ""}`}
          >
            {loc}
          </button>
        ))}
      </div>
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
