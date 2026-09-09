/** Seat counts an access code offers in the dropdown, everything else goes into the free field. */
export const SEAT_PRESETS = [1, 10, 25, 50, 100, 200, 500] as const;

/** Mirrors MAX_SEATS in the backend route. */
export const MAX_SEATS = 500;

/** Dropdown entry that reveals the free number field. */
export const SEATS_CUSTOM = "custom";

/** Splits a stored seat count into the dropdown choice and the free field. */
export function seatsToChoice(seats: number): { choice: string; custom: string } {
  const preset = SEAT_PRESETS.find((n) => n === seats);
  return preset ? { choice: String(preset), custom: "" } : { choice: SEATS_CUSTOM, custom: String(seats) };
}

/** Reads the seat count back, null when the free field holds nothing usable. */
export function choiceToSeats(choice: string, custom: string): number | null {
  const roh = choice === SEATS_CUSTOM ? custom.trim() : choice;
  if (!/^\d+$/.test(roh)) return null;
  const zahl = Number(roh);
  return zahl >= 1 && zahl <= MAX_SEATS ? zahl : null;
}
