/**
 * Eigene und betreute Module untereinander, mit einer Zeile dazwischen.
 *
 * Ohne die Trennung standen vier Zeilen in einer Tabelle und die Rolle in einer
 * Spalte am Rand. Man las sie als eine Liste und musste jede Zeile einzeln
 * nachsehen, um zu wissen, was einem davon gehoert.
 */

/** Was jemand mit einem Modul zu tun hat. Ein Drittes gibt es hier nicht. */
export type Zugriff = "owner" | "tutor";

/** Eigene zuerst, betreute danach, innerhalb der Gruppe unveraendert. */
export function gruppiert<T extends { access: Zugriff }>(module: T[]): T[] {
  return [...module].sort(
    (a, b) => Number(b.access === "owner") - Number(a.access === "owner"),
  );
}

/**
 * Der Zugriff, wenn ueber dieser Zeile eine Ueberschrift stehen soll, sonst null.
 *
 * Anders als auf der Startseite steht sie auch dann da, wenn es nur eine Gruppe
 * gibt: dort heisst eine einzelne Gruppe immer "was ich betreue", hier waeren es
 * zwei verschiedene Dinge, und wer nur fremde Module betreut, wuesste sonst
 * nicht, dass keins davon ihm gehoert.
 */
export function kopfBei<T extends { access: Zugriff }>(
  sortiert: T[],
  i: number,
): Zugriff | null {
  if (i === 0) return sortiert[0]?.access ?? null;
  return sortiert[i].access === sortiert[i - 1].access ? null : sortiert[i].access;
}
