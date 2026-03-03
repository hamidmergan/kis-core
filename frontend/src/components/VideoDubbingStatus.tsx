"use client";

import type { VideoDubbingState } from "@/types";

interface VideoDubbingStatusProps {
  state: VideoDubbingState;
  fileName?: string;
  errorMessage?: string;
  onDownload?: () => void;
  onReset?: () => void;
}

export default function VideoDubbingStatus({
  state,
  fileName,
  errorMessage,
  onDownload,
  onReset,
}: VideoDubbingStatusProps) {
  if (state === "idle") return null;

  return (
    <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6" role="status" aria-live="polite">
      {(state === "uploading" || state === "processing") && (
        <div className="flex items-center gap-3">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[#0066cc]" />
          <div>
            <span className="text-sm text-gray-700">
              {state === "uploading" ? "Video wird hochgeladen..." : "Dubbing läuft..."}
            </span>
            {state === "processing" && (
              <p className="text-xs text-gray-400 mt-1">Das kann einige Minuten dauern.</p>
            )}
          </div>
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
              aria-label="MP4"
              className="px-4 py-2 bg-[#0066cc] text-white text-sm rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors flex items-center gap-2"
            >
              <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              MP4
            </button>
            <button
              onClick={onReset}
              aria-label="Neues Video hochladen"
              className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
            >
              Neues Video
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
            <span className="text-sm font-medium text-red-700">Fehler beim Video-Dubbing</span>
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
