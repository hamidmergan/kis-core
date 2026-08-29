/** Whether the chosen password may be submitted. */

export const MIN_PASSWORD_LENGTH = 8;

export type PasswordCheck = { ok: true } | { ok: false; reason: "tooShort" | "mismatch" };

/** Length first, then the comparison, so two messages never appear at once. */
export function checkPassword(password: string, repeat: string): PasswordCheck {
  if (password.length < MIN_PASSWORD_LENGTH) return { ok: false, reason: "tooShort" };
  if (password !== repeat) return { ok: false, reason: "mismatch" };
  return { ok: true };
}
