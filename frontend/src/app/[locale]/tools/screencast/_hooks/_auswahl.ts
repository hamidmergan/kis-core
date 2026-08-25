/** Gespeicherter Teil der Auswahl, so wie ihn das Backend ablegt. */
export interface GespeicherteAuswahl {
  video_folien: number[] | null;
  neu_vertonen: number[];
}

export interface Startauswahl {
  imScreencast: number[];
  neuVertonen: number[];
}

/** Diese Folien muessen gesprochen werden, es gibt nichts zum Wiederverwenden. */
export function ohneTonAberMitSkript(scripts: string[], hatTon: boolean[]): number[] {
  if (!hatTon.length) return [];
  return scripts
    .map((s, i) => (s?.trim() && !hatTon[i] ? i : -1))
    .filter((i) => i >= 0);
}

/** Was Schritt 6 beim Betreten anhakt. */
export function startAuswahl(
  anzahl: number,
  gespeichert: GespeicherteAuswahl | null,
): Startauswahl {
  const alle = Array.from({ length: anzahl }, (_, i) => i);
  const imScreencast = gespeichert?.video_folien
    ? gespeichert.video_folien.filter((i) => i >= 0 && i < anzahl)
    : alle;
  // Was neu gesprochen wird, gilt nur fuer einen Lauf und faengt immer leer an.
  return { imScreencast, neuVertonen: [] };
}

/** Neu vertont wird nur, was ueberhaupt im Screencast ist. */
export function angleichen(imScreencast: number[], bisherNeu: number[]): number[] {
  const dabei = new Set(imScreencast);
  return [...new Set(bisherNeu.filter((i) => dabei.has(i)))].sort((a, b) => a - b);
}
