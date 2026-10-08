import type { LanguageChoice, Languages } from "../_lib/types";

/** The languages of what the owner can read and switch to, the page's own first. */
export function readableOf(l: Languages | null): LanguageChoice[] {
  if (!l) return [];
  return [l.own, ...l.languages.filter((x) => x.state === "done").map(({ key, label }) => ({ key, label }))];
}
