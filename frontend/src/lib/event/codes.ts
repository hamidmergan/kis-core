// No I, O, 0 or 1, so a code read off a poster cannot be mixed up.
export const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const CODE_LENGTH = 4;

export function newCode(): string {
  const bytes = new Uint32Array(CODE_LENGTH);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join("");
}

/** A fresh code that differs from every code in use. */
export function newUniqueCode(taken: string[]): string {
  const used = new Set(taken.map(normalizeCode));
  let code = newCode();
  while (used.has(code)) code = newCode();
  return code;
}

export function normalizeCode(input: string): string {
  return input.replace(/\s+/g, "").toUpperCase();
}
