/** Own and tutored modules one below the other, with a row in between. */

/** What someone has to do with a module, there is no third option here. */
export type Zugriff = "owner" | "tutor";

/** Own first, tutored after, unchanged inside the group. */
export function gruppiert<T extends { access: Zugriff }>(module: T[]): T[] {
  return [...module].sort(
    (a, b) => Number(b.access === "owner") - Number(a.access === "owner"),
  );
}

/** The accessor for when a heading should sit above this row. */
export function kopfBei<T extends { access: Zugriff }>(
  sortiert: T[],
  i: number,
): Zugriff | null {
  if (i === 0) return sortiert[0]?.access ?? null;
  return sortiert[i].access === sortiert[i - 1].access ? null : sortiert[i].access;
}
