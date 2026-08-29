/** What has to be filled in before the form goes to the server. */

type Eingabe = { code: string };

export type Ergebnis = { ok: true } | { ok: false; reason: "codeMissing" };

export function checkForm(eingabe: Eingabe): Ergebnis {
  if (!eingabe.code.trim()) return { ok: false, reason: "codeMissing" };
  return { ok: true };
}
