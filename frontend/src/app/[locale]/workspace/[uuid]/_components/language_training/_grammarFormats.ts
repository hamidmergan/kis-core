/** The four formats and what of them is sent, as pure functions. */

export const GRAMMAR_FORMATS = [
  "transform",
  "cloze",
  "statement",
  "choice",
] as const;

export type GrammarFormat = (typeof GRAMMAR_FORMATS)[number];

/** All four is mixed and sends nothing. */
export function sentKinds(checked: GrammarFormat[]): string[] | undefined {
  const gewaehlt = GRAMMAR_FORMATS.filter((f) => checked.includes(f));
  if (gewaehlt.length === 0 || gewaehlt.length === GRAMMAR_FORMATS.length) {
    return undefined;
  }
  return gewaehlt;
}

/** Whether the format selection unlocks the create button, at least one must be on. */
export function formatChoiceReady(checked: GrammarFormat[]): boolean {
  return checked.length > 0;
}

/** Flip one checkbox, the order stays the catalogue's. */
export function toggleFormat(
  checked: GrammarFormat[],
  format: GrammarFormat,
): GrammarFormat[] {
  const drin = checked.includes(format);
  return GRAMMAR_FORMATS.filter((f) =>
    f === format ? !drin : checked.includes(f),
  );
}
