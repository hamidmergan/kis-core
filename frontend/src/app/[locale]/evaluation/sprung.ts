/** Whether picking an answer should open the next question by itself. */
export function springtWeiter(
  fragen: { type: string; skippable?: boolean }[] | undefined,
  index: number,
): boolean {
  if (!fragen || index + 1 >= fragen.length) return false;
  const frage = fragen[index];
  // A question with its own "haven't tried this" button waits for a deliberate click.
  if (frage?.skippable) return false;
  return frage?.type === "choice";
}
