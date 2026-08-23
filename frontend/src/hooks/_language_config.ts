import type { Language } from "./useLanguageConfig";

/** Nur erlaubte Sprachen behalten und eine gesperrte Zielsprache zurueckholen. */
export function pickAllowed(
  languages: Language[],
  allowed: readonly string[] | undefined,
  target: string,
): { languages: Language[]; target: string } {
  if (!allowed) return { languages, target };
  const erlaubt = languages.filter((l) => allowed.includes(l.id));
  if (!erlaubt.length) return { languages: erlaubt, target };
  const gueltig = erlaubt.some((l) => l.id === target);
  return { languages: erlaubt, target: gueltig ? target : erlaubt[0].id };
}
