/** Whether picking an answer should open the next question by itself. */
export function springtWeiter(
  fragen: { type: string }[] | undefined,
  index: number,
): boolean {
  if (!fragen || index + 1 >= fragen.length) return false;
  return fragen[index]?.type === "choice";
}
