/**
 * Die Adresse einer Einladung.
 *
 * Ohne Sprachpraefix: die Adressen laufen mit "as-needed", Deutsch steht ohne
 * Praefix, und Englisch findet die Seite ueber die Weiterleitung genauso.
 */
export function inviteUrl(origin: string, token: string): string {
  return `${origin.replace(/\/+$/, "")}/einladung/${token}`;
}
