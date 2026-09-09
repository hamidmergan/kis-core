/** Whether the intro step has anything to say, otherwise the first question opens right away. */
export function hatAnfang(
  daten: { intro_text?: string; intro_link_url?: string } | null,
): boolean {
  return Boolean(daten?.intro_text?.trim() || daten?.intro_link_url?.trim());
}
