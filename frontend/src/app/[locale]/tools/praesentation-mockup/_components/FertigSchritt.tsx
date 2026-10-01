"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { MOCK_SLIDE_COUNT, VORLAGEN } from "../_data";

interface Props {
  onBack: () => void;
  onRestart: () => void;
}

const NEBENKNOPF =
  "w-full lg:w-auto px-6 py-2.5 lg:py-2 text-sm text-foreground-soft border-2 border-border rounded-lg lg:rounded-md hover:border-kb focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors";

// Line widths per thumbnail, so the strip does not look like five copies.
const MINIATUREN = [["70%", "45%"], ["55%", "65%", "40%"], ["60%", "70%", "55%"], ["50%", "60%"], ["65%", "50%", "35%"]];

/** Step 3: finished state, the download button is pinned at the bottom on the phone. */
export default function FertigSchritt({ onBack, onRestart }: Props) {
  return (
    <section className="pt-3 lg:pt-0">
      <div className="flex justify-center mb-3.5 lg:mb-4">
        <div className="w-11 h-11 lg:w-12 lg:h-12 rounded-full flex items-center justify-center" style={{ backgroundColor: "var(--kb)" }}>
          <svg className="w-6 h-6" style={{ color: "#fff" }} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-center">Fertig</h2>
      <p className="text-sm text-muted mt-1 mb-5 lg:mb-8 text-center">{MOCK_SLIDE_COUNT} Folien erstellt</p>

      <div className="flex gap-2.5 lg:gap-4 overflow-x-auto scrollbar-hide pb-1.5 lg:justify-center lg:flex-wrap">
        {MINIATUREN.slice(0, MOCK_SLIDE_COUNT).map((zeilen, i) => (
          <div key={i} className="shrink-0 w-32 lg:w-40 aspect-video rounded-md overflow-hidden border border-border-soft bg-background shadow-sm flex flex-col">
            <span className="block h-1 w-full" style={{ backgroundColor: VORLAGEN[0].accent }} />
            <div className="flex-1 min-h-0 flex flex-col justify-center gap-1.5 p-2.5">
              {zeilen.map((breite, j) => (
                <span key={j} className={`block rounded-sm ${j === 0 ? "h-1 bg-foreground opacity-80" : "h-0.5 bg-border"}`} style={{ width: breite }} />
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="hidden lg:flex justify-center mt-9 mb-6">
        <button type="button" className="px-6 py-2 btn-primary text-sm font-medium rounded-md transition-colors flex items-center gap-2">
          <DownloadSimple size={14} weight="bold" />
          Herunterladen
        </button>
      </div>

      <div className="flex flex-col lg:flex-row lg:justify-center gap-2 lg:gap-3 mt-6 lg:mt-0">
        <button type="button" onClick={onBack} className={NEBENKNOPF}>Zurück zu den Folien</button>
        <button type="button" onClick={onRestart} className={NEBENKNOPF}>Neue erstellen</button>
      </div>

      <div className="lg:hidden h-20" aria-hidden="true" />
      <div className="lg:hidden fixed inset-x-0 bottom-0 border-t border-border-soft bg-background px-4 py-3">
        <button type="button" className="w-full px-5 py-3 btn-primary text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2">
          <DownloadSimple size={14} weight="bold" />
          Herunterladen
        </button>
      </div>
    </section>
  );
}
