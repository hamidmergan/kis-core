const BASE = "/api/ai-assistant/popup-actions";

/** The URL of the selection bar actions with the reader's target language. */
export function popupActionsUrl(target?: string | null): string {
  const code = (target ?? "").trim();
  return code ? `${BASE}?target=${encodeURIComponent(code)}` : BASE;
}
