/** How long a code stays redeemable: presets in the dropdown, everything else goes into the free field. */
export const VALID_DAYS_PRESETS = [7, 14, 30, 60] as const;

/** Mirrors MAX_VALID_DAYS in the backend route. */
export const MAX_VALID_DAYS = 365;

/** Dropdown entry that reveals the free day field. */
export const VALID_DAYS_CUSTOM = "custom";

/** Splits a day count into the dropdown choice and the free field. */
export function daysToChoice(days: number): { choice: string; custom: string } {
  const preset = VALID_DAYS_PRESETS.find((n) => n === days);
  return preset ? { choice: String(preset), custom: "" } : { choice: VALID_DAYS_CUSTOM, custom: String(days) };
}

/** Reads the day count back, null when the free field holds nothing usable. */
export function choiceToDays(choice: string, custom: string): number | null {
  const roh = choice === VALID_DAYS_CUSTOM ? custom.trim() : choice;
  if (!/^\d+$/.test(roh)) return null;
  const zahl = Number(roh);
  return zahl >= 1 && zahl <= MAX_VALID_DAYS ? zahl : null;
}

/** Whole days left until the code runs out, at least one and never above the cap. */
export function remainingDays(validUntil: string, now: number = Date.now()): number {
  const tage = Math.ceil((new Date(validUntil).getTime() - now) / 86_400_000);
  return Math.min(MAX_VALID_DAYS, Math.max(1, tage));
}
