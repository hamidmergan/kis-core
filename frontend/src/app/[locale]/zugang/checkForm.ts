/** What has to be filled in before the form goes to the server. */

export const MIN_PASSWORD_LENGTH = 8;

type Eingabe = {
  code: string;
  givenName: string;
  surname: string;
  password: string;
  repeat: string;
};

export type Ergebnis =
  | { ok: true }
  | { ok: false; reason: "codeMissing" | "nameMissing" | "tooShort" | "mismatch" };

export function checkForm(eingabe: Eingabe): Ergebnis {
  if (!eingabe.code.trim()) return { ok: false, reason: "codeMissing" };
  if (!eingabe.givenName.trim() || !eingabe.surname.trim()) {
    return { ok: false, reason: "nameMissing" };
  }
  if (eingabe.password.length < MIN_PASSWORD_LENGTH) return { ok: false, reason: "tooShort" };
  if (eingabe.password !== eingabe.repeat) return { ok: false, reason: "mismatch" };
  return { ok: true };
}
