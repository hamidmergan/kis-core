/** Mirrors the backend rules so the dialog can show the user name while typing. */
const UMLAUTE: Record<string, string> = { "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss" };

export function uidPreview(text: string): string {
  let wert = (text ?? "").trim().toLowerCase();
  for (const [zeichen, ersatz] of Object.entries(UMLAUTE)) {
    wert = wert.split(zeichen).join(ersatz);
  }
  return wert.replace(/ /g, "-").replace(/[^a-z0-9_.-]/g, "").slice(0, 32);
}
