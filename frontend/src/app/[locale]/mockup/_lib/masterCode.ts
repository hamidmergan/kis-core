import type { MockupCard } from "./types";

// No I, O, 0 or 1, so a code read off a poster cannot be mixed up.
export const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const CODE_LENGTH = 4;
export const MAX_ATTEMPTS = 5;
export const LOCK_MS = 30_000;

export function newMasterCode(): string {
  const bytes = new Uint32Array(CODE_LENGTH);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join("");
}

export function normalizeCode(input: string): string {
  return input.replace(/\s+/g, "").toUpperCase();
}

export function isValidMasterCode(code: string): boolean {
  const c = normalizeCode(code);
  return c.length === CODE_LENGTH && [...c].every((ch) => CODE_ALPHABET.includes(ch));
}

export function codeMatches(input: string, master: string): boolean {
  return normalizeCode(input) === normalizeCode(master);
}

/** Counts a failed try and starts the lock once the limit is hit. */
export function afterWrongCode(card: MockupCard, now: number): MockupCard {
  const failed = card.failedAttempts + 1;
  if (failed >= MAX_ATTEMPTS) return { ...card, failedAttempts: 0, lockUntil: now + LOCK_MS };
  return { ...card, failedAttempts: failed };
}

export function lockRemainingMs(card: MockupCard, now: number): number {
  return card.lockUntil ? Math.max(0, card.lockUntil - now) : 0;
}
