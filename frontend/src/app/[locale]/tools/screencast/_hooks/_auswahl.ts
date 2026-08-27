/** The stored part of the selection, the way the backend saves it. */
export interface GespeicherteAuswahl {
  video_folien: number[] | null;
  neu_vertonen: number[];
}

export interface Startauswahl {
  imScreencast: number[];
  neuVertonen: number[];
}

/** These slides have to be spoken, there is nothing to reuse. */
export function ohneTonAberMitSkript(scripts: string[], hatTon: boolean[]): number[] {
  if (!hatTon.length) return [];
  return scripts
    .map((s, i) => (s?.trim() && !hatTon[i] ? i : -1))
    .filter((i) => i >= 0);
}

/** What step 6 ticks on entry. */
export function startAuswahl(
  anzahl: number,
  gespeichert: GespeicherteAuswahl | null,
): Startauswahl {
  const alle = Array.from({ length: anzahl }, (_, i) => i);
  const imScreencast = gespeichert?.video_folien
    ? gespeichert.video_folien.filter((i) => i >= 0 && i < anzahl)
    : alle;
  // What gets spoken again applies to one run only and always starts empty.
  return { imScreencast, neuVertonen: [] };
}

/** Only what is in the screencast at all gets voiced again. */
export function angleichen(imScreencast: number[], bisherNeu: number[]): number[] {
  const dabei = new Set(imScreencast);
  return [...new Set(bisherNeu.filter((i) => dabei.has(i)))].sort((a, b) => a - b);
}
