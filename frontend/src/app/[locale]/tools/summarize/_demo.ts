/** What the demo reads from the prepared runs. */
export type DemoSetup = {
  workspace: string;
  files: string[];
  instructions: string;
  templates: string[];
  sections: Record<string, number>;
};

/** One line of the simulated run, with the step names and numbers a real run reports. */
export type DemoSchritt = { step: string; part?: number; total?: number };

/** The steps a real run over this many files and sections reports, in order. */
export function demoSchritte(dateien: number, abschnitte: number): DemoSchritt[] {
  const gezaehlt = (step: string, total: number) =>
    Array.from({ length: total }, (_, i) => ({ step, part: i + 1, total }));
  return [{ step: "extract" }, ...gezaehlt("map", dateien), { step: "outline" }, ...gezaehlt("section", abschnitte)];
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
