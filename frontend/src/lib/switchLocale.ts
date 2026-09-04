import type { Locale } from "@/i18n/routing";

/** Remembers the wish on the server, cookie and URL keep working without it. */
export async function persistLocale(locale: Locale): Promise<void> {
  try {
    await fetch("/api/me/locale", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
  } catch {
    // Backend offline or not logged in, cookie and URL still work.
  }
}

/** next-intl sets the language cookie only after startup, so it is written here first. */
export function rememberLocaleCookie(locale: Locale): void {
  document.cookie = `NEXT_LOCALE=${locale}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
}
