import type { SlideData } from "@/types";


interface TranslationReviewStepProps {
  slides: SlideData[];
  fastMode: boolean;
  loading: boolean;
  lightboxIndex: number | null;
  onLightboxOpen: (idx: number | null) => void;
  onAcceptAndNext: () => void;
}


export function TranslationReviewStep({
  slides, fastMode, loading, lightboxIndex, onLightboxOpen, onAcceptAndNext,
}: TranslationReviewStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Übersetzung prüfen</h2>
      <p className="text-sm text-gray-500 mb-4">
        Die Präsentation wurde übersetzt. Sie können die übersetzte
        PPTX herunterladen, prüfen und optional eine korrigierte
        Version hochladen.
      </p>

      {!fastMode && (
        <div className="flex flex-wrap justify-center gap-2 mb-6">
          {slides.map((slide, i) => (
            <button key={i} onClick={() => onLightboxOpen(i)} style={{ width: "100px" }}
              className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-primary transition-colors focus-visible:outline-2 focus-visible:outline-primary group flex-shrink-0"
              aria-label={`Folie ${i + 1} vergrößern`}
            >
              {slide.imageBase64 ? (
                <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full object-cover" />
              ) : (
                <div className="aspect-video bg-gray-100 flex items-center justify-center text-xs text-gray-400">Wird geladen...</div>
              )}
              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-xs font-medium text-gray-700 px-2 py-1 rounded transition-opacity">Folie {i + 1}</span>
              </div>
            </button>
          ))}
        </div>
      )}

      {!fastMode && lightboxIndex !== null && (
        <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
          onClick={() => onLightboxOpen(null)} role="dialog" aria-modal="true" aria-label={`Folie ${lightboxIndex + 1}`}
        >
          <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => onLightboxOpen(null)} className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors" aria-label="Schließen">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            <p className="text-white text-sm text-center mb-2">Folie {lightboxIndex + 1} von {slides.length}</p>
            <img src={`data:image/png;base64,${slides[lightboxIndex].imageBase64}`} alt={`Folie ${lightboxIndex + 1}`} className="w-full rounded-lg shadow-2xl" />
            <div className="flex justify-center gap-4 mt-4">
              <button onClick={() => onLightboxOpen(Math.max(0, lightboxIndex - 1))} disabled={lightboxIndex === 0}
                className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30">← Zurück</button>
              <button onClick={() => onLightboxOpen(Math.min(slides.length - 1, lightboxIndex + 1))} disabled={lightboxIndex === slides.length - 1}
                className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30">Weiter →</button>
            </div>
          </div>
        </div>
      )}

      {/* Actions (Demo: decorative only) */}
      <div className="flex flex-col gap-3 mb-4">
        <button type="button" disabled title="Nicht in der Demo verfügbar"
          className="w-full px-4 py-2 text-sm text-primary border border-primary rounded-md hover:bg-primary/5 transition-colors flex items-center justify-center gap-2 cursor-not-allowed opacity-60"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          PPTX
        </button>

        <div className="relative">
          <div title="Nicht in der Demo verfügbar"
            className="block w-full px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md text-center cursor-not-allowed opacity-60"
          >
            Korrigierte PPTX hochladen (optional)
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        <button onClick={onAcceptAndNext} disabled={loading}
          className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Übersetzung übernehmen und weiter
        </button>
      </div>
    </section>
  );
}
