import { defineRouting } from "next-intl/routing";
import { DEFAULT_UI_LOCALE, UI_LOCALES } from "@/lib/constants";

export const routing = defineRouting({
  locales: UI_LOCALES,
  defaultLocale: DEFAULT_UI_LOCALE,
  localePrefix: "as-needed",
});

export type Locale = (typeof routing.locales)[number];
