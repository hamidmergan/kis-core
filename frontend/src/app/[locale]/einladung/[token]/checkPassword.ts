/**
 * Ob das gesetzte Passwort abgeschickt werden darf.
 *
 * Eigene Datei neben der Seite, wie ``canDeleteUser``: die Entscheidung ist
 * pruefbare Logik, das Formular drumherum ist nur Darstellung.
 */

export const MIN_PASSWORD_LENGTH = 8;

export type PasswordCheck = { ok: true } | { ok: false; reason: "tooShort" | "mismatch" };

/** Erst die Laenge, dann der Vergleich, damit nie zwei Meldungen gleichzeitig stehen. */
export function checkPassword(password: string, repeat: string): PasswordCheck {
  if (password.length < MIN_PASSWORD_LENGTH) return { ok: false, reason: "tooShort" };
  if (password !== repeat) return { ok: false, reason: "mismatch" };
  return { ok: true };
}
