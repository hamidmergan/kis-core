/** The three cases of renaming as testable logic next to the field. */

export type RenameAction =
  /** Nothing to do, simply close the field, not an error but a cancel. */
  | { kind: "abort" }
  /** Save with exactly this name. */
  | { kind: "save"; title: string };

/** Empty or unchanged cancels, otherwise it saves. */
export function renameCommit(entwurf: string, aktuell: string): RenameAction {
  const naechster = entwurf.trim();
  if (!naechster || naechster === aktuell.trim()) return { kind: "abort" };
  return { kind: "save", title: naechster };
}

/** The reason from the server takes precedence, otherwise the general sentence appears. */
export function renameErrorText(fehler: unknown, allgemein: string): string {
  if (fehler instanceof Error && fehler.message) return fehler.message;
  return allgemein;
}
