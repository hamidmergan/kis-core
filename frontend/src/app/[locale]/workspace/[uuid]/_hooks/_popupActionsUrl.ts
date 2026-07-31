const BASE = "/api/ai-assistant/popup-actions";

/**
 * Adresse für die Aktionen der Auswahlleiste, mit der Zielsprache der
 * lesenden Person. Solange die Einstellung noch nicht geladen ist, bleibt der
 * Parameter weg und das Backend nimmt seinen eigenen Standard (Englisch).
 */
export function popupActionsUrl(target?: string | null): string {
  const code = (target ?? "").trim();
  return code ? `${BASE}?target=${encodeURIComponent(code)}` : BASE;
}
