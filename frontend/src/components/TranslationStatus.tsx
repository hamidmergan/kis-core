"use client";

import type { TranslationState } from "@/types";

interface TranslationStatusProps {
  state: TranslationState;
  fileName?: string;
  errorMessage?: string;
  onDownload?: () => void;
  onReset?: () => void;
}

export default function TranslationStatus({
  state,
  fileName,
  errorMessage,
  onDownload,
  onReset,
}: TranslationStatusProps) {
  if (state === "idle") return null;

  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6" role="status" aria-live="polite">
      {(state === "uploading" || state === "translating") && (
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[#0066cc]" />
          <span className="text-sm text-gray-700">
            {state === "uploading" ? "Datei wird hochgeladen..." : "Übersetzung läuft..."}
          </span>
        </div>
      )}

      {state === "done" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="text-sm font-medium text-gray-900">Fertig! Download bereit</span>
          </div>
          {fileName && <p className="text-xs text-gray-500">{fileName}</p>}
          <div className="flex gap-3">
            <button
              onClick={onDownload}
              aria-label="Übersetzte Datei herunterladen"
              className="px-4 py-2 bg-[#0066cc] text-white text-sm rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
            >
              Herunterladen
            </button>
            <button
              onClick={onReset}
              aria-label="Neue Datei hochladen"
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
            >
              Neue Datei
            </button>
          </div>
        </div>
      )}

      {state === "error" && (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            <span className="text-sm font-medium text-red-700">Fehler bei der Übersetzung</span>
          </div>
          {errorMessage && <p className="text-xs text-red-600">{errorMessage}</p>}
          <button
            onClick={onReset}
            aria-label="Erneut versuchen"
            className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
          >
            Erneut versuchen
          </button>
        </div>
      )}
    </div>
  );
}
