/** Lifetimes an access code offers in the dropdown, everything else goes into the free field. */
export const ACCESS_HOURS_PRESETS = [12, 24, 168, 336, 720] as const;

/** Mirrors MAX_ACCESS_HOURS in the backend route. */
export const MAX_ACCESS_HOURS = 720;

/** Dropdown entry that reveals the free hours field. */
export const ACCESS_HOURS_CUSTOM = "custom";

/** Dropdown entry for accounts that never expire. */
export const ACCESS_HOURS_UNLIMITED = "unlimited";

/** Splits a stored hour count into the dropdown choice and the free field, null means unlimited. */
export function hoursToChoice(hours: number | null): { choice: string; custom: string } {
  if (hours == null) return { choice: ACCESS_HOURS_UNLIMITED, custom: "" };
  const preset = ACCESS_HOURS_PRESETS.find((n) => n === hours);
  return preset ? { choice: String(preset), custom: "" } : { choice: ACCESS_HOURS_CUSTOM, custom: String(hours) };
}

/** Reads the hour count back: undefined when unusable, null when unlimited. */
export function choiceToHours(choice: string, custom: string): number | null | undefined {
  if (choice === ACCESS_HOURS_UNLIMITED) return null;
  const roh = choice === ACCESS_HOURS_CUSTOM ? custom.trim() : choice;
  if (!/^\d+$/.test(roh)) return undefined;
  const zahl = Number(roh);
  return zahl >= 1 && zahl <= MAX_ACCESS_HOURS ? zahl : undefined;
}
