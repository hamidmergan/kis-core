export type RegenApplyMode = "replace-selection" | "insert-before" | "insert-after" | "replace-all";

/** Where the suggestion lands in the text it was written for. */
export function applyRegen(current: string, anchor: string, mode: RegenApplyMode, content: string): string {
  if (mode === "replace-all" || !anchor) return content;
  // A function as replacement, a "$" in the suggestion would otherwise be read as a pattern.
  if (mode === "replace-selection") return current.replace(anchor, () => content);
  if (mode === "insert-before") return current.replace(anchor, () => content + " " + anchor);
  return current.replace(anchor, () => anchor + " " + content);
}
