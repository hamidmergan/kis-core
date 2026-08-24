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
  geaendert: number[],
  hatTon: boolean[],
  scripts: string[],
): Startauswahl {
  const alle = Array.from({ length: anzahl }, (_, i) => i);
  const imScreencast = gespeichert?.video_folien
    ? gespeichert.video_folien.filter((i) => i >= 0 && i < anzahl)
    : alle;
  // Geaendertes kommt immer dazu, sonst spricht das Video den alten Text weiter.
  const bisher = [...(gespeichert ? gespeichert.neu_vertonen : []), ...geaendert];
  const gesperrt = new Set(ohneTonAberMitSkript(scripts, hatTon));
  return { imScreencast, neuVertonen: angleichen(imScreencast, bisher, gesperrt) };
}

/** Neu vertont wird nur, was im Screencast ist, und eine Folie ohne Ton immer. */
export function angleichen(
  imScreencast: number[],
  bisherNeu: number[],
  gesperrt: Set<number>,
): number[] {
  const dabei = new Set(imScreencast);
  const menge = new Set(bisherNeu.filter((i) => dabei.has(i)));
  gesperrt.forEach((i) => {
    if (dabei.has(i)) menge.add(i);
  });
  return [...menge].sort((a, b) => a - b);
}
