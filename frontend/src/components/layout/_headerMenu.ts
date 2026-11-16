"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { UI_LOCALES } from "@/lib/constants";
import type { Theme } from "@/hooks/useTheme";
import { persistLocale, rememberLocaleCookie } from "@/lib/switchLocale";

export const LOCALES = UI_LOCALES as readonly Locale[];
export const THEMES: readonly Theme[] = ["light", "dark"];
// Row groups below the appearance section, in the order they are rendered.
const BLOCKS: readonly (readonly string[])[] = [["level", "interfaces", "tour", "evaluation", "manual", "faq"], ["admin"], ["logout"]];

/** The first visible row of every block, the one that carries the divider above it. */
export function blockStartRows(shown: Record<string, boolean>): Set<string | undefined> {
  return new Set(BLOCKS.map((block) => block.find((row) => shown[row])).filter(Boolean));
}

/** The current language and the switch to another one, kept in cookie, URL and account. */
export function useLocaleSwitch(): { currentLocale: Locale; switchLocale: (next: Locale) => void } {
  const router = useRouter();
  const pathname = usePathname();
  const currentLocale = useLocale() as Locale;
  const switchLocale = (next: Locale) => {
    if (next === currentLocale) return;
    rememberLocaleCookie(next);
    router.replace(pathname, { locale: next });
    void persistLocale(next);
  };
  return { currentLocale, switchLocale };
}
