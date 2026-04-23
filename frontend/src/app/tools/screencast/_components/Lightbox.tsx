"use client";

import type { SlideData } from "@/types";

interface LightboxProps {
  index: number;
  slides: SlideData[];
  onClose: () => void;
  onIndexChange: (index: number) => void;
}

export default function Lightbox({ index, slides, onClose, onIndexChange }: LightboxProps) {
  const slide = slides[index];
  if (!slide?.imageBase64) return null;
  return (
    <div
      className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Folie ${index + 1}`}
    >
      <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={onClose}
          className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
          aria-label="Schließen"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <p className="text-white text-sm text-center mb-2">
          Folie {index + 1} von {slides.length}
        </p>
        <img
          src={`data:image/png;base64,${slide.imageBase64}`}
          alt={`Folie ${index + 1}`}
          className="w-full rounded-lg shadow-2xl"
        />
        <div className="flex justify-center gap-4 mt-4">
          <button
            onClick={() => onIndexChange(Math.max(0, index - 1))}
            disabled={index === 0}
            className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          >
            ← Zurück
          </button>
          <button
            onClick={() => onIndexChange(Math.min(slides.length - 1, index + 1))}
            disabled={index === slides.length - 1}
            className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
          >
            Weiter →
          </button>
        </div>
      </div>
    </div>
  );
}
