"use client";

import { useLocale } from "next-intl";
import type { Text2 } from "./types";

/** Picks the current language from an admin-written text pair, German as fallback. */
export function useText2(): (text: Text2) => string {
  const locale = useLocale();
  return (text) => (locale === "en" ? text.en || text.de : text.de || text.en);
}
