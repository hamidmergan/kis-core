"use client";

import type { SlideData } from "@/types";

interface TranslationReviewStepProps {
  slides: SlideData[];
  loading: boolean;
  correctedFileName: string | null;
  onLightboxOpen: (index: number) => void;
  onDownloadTranslatedPptx: () => void;
  onUploadCorrectedPptx: (f: File) => void;
  onAcceptAndNext: () => void;
}

export default function TranslationReviewStep({
  slides,
  loading,
  correctedFileName,
  onLightboxOpen,
  onDownloadTranslatedPptx,
  onUploadCorrectedPptx,
  onAcceptAndNext,
}: TranslationReviewStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Übersetzung prüfen</h2>
      <p className="text-sm text-gray-500 mb-4">
        Die Präsentation wurde übersetzt. Sie können die übersetzte PPTX herunterladen, prüfen und optional eine korrigierte Version hochladen.
      </p>

      <div className="flex flex-wrap justify-center gap-2 mb-6">
        {slides.map((slide, i) => (
          <button
            key={i}
            onClick={() => onLightboxOpen(i)}
            style={{ width: "100px" }}
            className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-primary transition-colors focus-visible:outline-2 focus-visible:outline-primary group flex-shrink-0"
            aria-label={`Folie ${i + 1} vergrößern`}
          >
            {slide.imageBase64 ? (
              <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full object-cover" />
            ) : (
              <div className="aspect-video bg-gray-100 flex items-center justify-center text-xs text-gray-400">Wird geladen...</div>
            )}
            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
              <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-xs font-medium text-gray-700 px-2 py-1 rounded transition-opacity">
                Folie {i + 1}
              </span>
            </div>
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-3 mb-4">
        <button
          onClick={onDownloadTranslatedPptx}
          className="w-full px-4 py-2 text-sm text-primary border border-primary rounded-md hover:bg-primary/5 transition-colors flex items-center justify-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
          PPTX
        </button>

        <div className="relative">
          <label className="block w-full px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 transition-colors text-center cursor-pointer">
            {loading ? "Wird verarbeitet..." : "Korrigierte PPTX hochladen (optional)"}
            <input
              type="file"
              accept=".pptx"
              className="hidden"
              disabled={loading}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onUploadCorrectedPptx(f);
              }}
            />
          </label>
          {correctedFileName && (
            <p className="mt-2 text-sm text-green-600 flex items-center gap-2">
              <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {correctedFileName} wurde hochgeladen
            </p>
          )}
        </div>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onAcceptAndNext}
          disabled={loading}
          className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Übersetzung übernehmen und weiter
        </button>
      </div>
    </section>
  );
}
