import type { PraesentationView } from "./_api";
import type { JobProgress, JobStatus, Outline, Slide } from "./_types";

/** The fixed material of the demo run, shown in the first step instead of a choice. */
export interface DemoMaterial {
  workspace: string;
  files: string[];
}

export type DemoView = PraesentationView & DemoMaterial;

/** What the page holds at one moment of a run. */
export interface DemoStand {
  outline: Outline | null;
  slides: Slide[];
  images: Record<string, string[]>;
  previews: string[];
  hasDeck: boolean;
}

/** One moment of the simulated run: what the job reports, what the page holds, and how long it stays. */
export interface DemoMoment {
  status: JobStatus;
  progress: JobProgress | null;
  stand: DemoStand;
  ms: number;
}

// Milliseconds each kind of moment stays up, short enough to watch the whole run.
const DAUER = { material: 900, outline: 1200, text: 350, bild: 600, vorschau: 900 };

/** The moments of a real run in order, from reading the material to the finished previews. */
export function demoAblauf(view: PraesentationView): DemoMoment[] {
  const leer: DemoStand = { outline: null, slides: [], images: {}, previews: [], hasDeck: false };
  const laeuft = (progress: JobProgress, stand: DemoStand, ms: number): DemoMoment =>
    ({ status: "running", progress, stand, ms });
  const momente = [laeuft({ step: "material" }, leer, DAUER.material), laeuft({ step: "outline" }, leer, DAUER.outline)];

  const n = view.slides.length;
  for (let k = 1; k <= n; k++) {
    momente.push(laeuft({ step: "texte", current: k, total: n },
                        { ...leer, outline: view.outline, slides: view.slides.slice(0, k) }, DAUER.text));
  }

  const geschrieben: DemoStand = { ...leer, outline: view.outline, slides: view.slides };
  const plaetze = view.slides.flatMap((s) => (view.images[s.id] ?? []).map((slot) => ({ id: s.id, slot })));
  for (let j = 1; j <= plaetze.length; j++) {
    const images: Record<string, string[]> = {};
    for (const { id, slot } of plaetze.slice(0, j)) images[id] = [...(images[id] ?? []), slot];
    momente.push(laeuft({ step: "bilder", current: j, total: plaetze.length }, { ...geschrieben, images }, DAUER.bild));
  }

  momente.push(laeuft({ step: "vorschau" }, { ...geschrieben, images: view.images }, DAUER.vorschau));
  momente.push({ status: "awaiting_user", progress: null, ms: 0,
                 stand: { ...geschrieben, images: view.images, previews: view.previews, hasDeck: view.has_deck } });
  return momente;
}

export function warte(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const zeit = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(zeit);
      reject(new DOMException("aborted", "AbortError"));
    });
  });
}
