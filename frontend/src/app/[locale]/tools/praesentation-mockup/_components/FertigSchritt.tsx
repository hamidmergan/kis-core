"use client";

import { MOCK_SLIDES, MOCK_SLIDE_COUNT, VORLAGEN } from "../_data";

interface Props {
  onBack: () => void;
  onRestart: () => void;
}

const NEBENKNOPF =
  "px-6 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors";

/** Schritt 3: fertiger Zustand, am Handy nur der Download-Knopf fixiert, der Rest bleibt wie am Bildschirm. */
export default function FertigSchritt({ onBack, onRestart }: Props) {
  return (
    <section className="py-4">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--kb)" }}>
          <svg className="w-6 h-6" style={{ color: "#fff" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-center">Fertig</h2>
      <p className="text-sm text-muted mt-1 mb-6 text-center">{MOCK_SLIDE_COUNT} Folien erstellt</p>

      <div className="flex gap-3 overflow-x-auto scrollbar-hide pb-1 justify-center">
        {[...MOCK_SLIDES, ...MOCK_SLIDES.slice(0, 1)].map((s, i) => (
          <div key={`${s.id}-${i}`} className="shrink-0 w-32 aspect-video rounded-md overflow-hidden border-2 border-transparent hover:border-kb transition-colors bg-background flex flex-col">
            <span className="block h-1 w-full" style={{ backgroundColor: VORLAGEN[0].accent }} />
            <div className="flex-1 min-h-0 flex flex-col justify-center gap-1 p-2.5">
              <span className="block h-1 w-3/5 rounded-sm bg-foreground-soft opacity-70" />
              <span className="block h-1 w-2/5 rounded-sm bg-border" />
            </div>
          </div>
        ))}
      </div>

      {/* Download bleibt am Bildschirm hier in der Mitte, am Handy wandert der gleiche Knopf unten fest. */}
      <div className="hidden lg:flex justify-center mt-8 mb-6">
        <button type="button" className="px-6 py-2 btn-primary text-sm font-medium rounded-md transition-colors flex items-center gap-2">
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Herunterladen
        </button>
      </div>

      <div className="flex flex-wrap justify-center gap-3 mt-8 lg:mt-0">
        <button type="button" onClick={onBack} className={NEBENKNOPF}>Zurück zu den Folien</button>
        <button type="button" onClick={onRestart} className={NEBENKNOPF}>Neue erstellen</button>
      </div>

      <div className="lg:hidden h-20" aria-hidden="true" />
      <div className="lg:hidden fixed inset-x-0 bottom-0 border-t border-border-soft bg-background p-4">
        <button type="button" className="w-full px-5 py-2.5 btn-primary text-sm font-medium rounded-md transition-colors flex items-center justify-center gap-2">
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Herunterladen
        </button>
      </div>
    </section>
  );
}
