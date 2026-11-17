/** Helpers for the commands of the PDF selection menu. */

type Slices = Record<string, { count?: number }>;
export type SelectionState = { state?: { plugins?: { selection?: { documents?: Record<string, { slices?: Slices }> } } }; documentId: string };

/** Selected characters, null while the viewer cannot tell yet. */
export function selectedCharCount({ state, documentId }: SelectionState): number | null {
  const doc = state?.plugins?.selection?.documents?.[documentId];
  if (!doc?.slices) return null;
  return Object.values(doc.slices).reduce((sum, s) => sum + (s.count || 0), 0);
}

/** True while text is selected, and while the viewer cannot tell yet. */
export function selectionHasText(selection: SelectionState): boolean {
  const totalChars = selectedCharCount(selection);
  return totalChars === null || totalChars > 0;
}

/** Hands the selected text as one line to the callback, the page is only looked up on demand. */
export function withSelectedText(
  registry: unknown,
  documentId: string,
  onText: (text: string, page: () => number) => void,
): void {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sel = (registry as any).getPlugin?.("selection")?.provides?.();
  if (!sel) return;
  const textTask = sel.getSelectedText?.(documentId);
  const promise: Promise<string[]> = textTask?.toPromise?.() ?? Promise.resolve([]);
  promise.then((lines: string[]) => {
    const text = (Array.isArray(lines) ? lines : [lines]).join(" ").trim();
    onText(text, () => {
      const formatted: Array<{ pageIndex: number }> = sel.forDocument?.(documentId)?.getFormattedSelection?.() ?? [];
      return formatted.length > 0 ? formatted[0].pageIndex + 1 : 1;
    });
  }).catch(() => { /* ignore */ });
}
