"use client";

import Spinner from "@/components/ui/Spinner";

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

export function TranslatingStep({
  sourceLang,
  targetLang,
  onCancel,
}: {
  sourceLang: string;
  targetLang: string;
  onCancel: () => void;
}) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-gray-700 animate-pulse">
        {sourceLang === targetLang ? "Präsentation wird vorbereitet..." : "Präsentation wird übersetzt..."}
      </p>
      <p className="text-xs text-gray-400 mt-2">Das kann je nach Dateigröße einige Sekunden dauern.</p>
      <button
        onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        Abbrechen
      </button>
    </section>
  );
}

export function GeneratingScriptsStep({
  slideCount,
  onCancel,
}: {
  slideCount: number;
  onCancel: () => void;
}) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-gray-700 animate-pulse">Sprechskripte werden generiert...</p>
      <p className="text-xs text-gray-400 mt-2">Die KI erstellt Skripte für {slideCount} Folien.</p>
      <button
        onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        Abbrechen
      </button>
    </section>
  );
}

export function RenderingStep({
  renderProgressLabel,
  onCancel,
}: {
  renderProgressLabel: string;
  onCancel: () => void;
}) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-gray-700">{renderProgressLabel || "Video wird erstellt..."}</p>
      {!renderProgressLabel && (
        <p className="text-xs text-gray-400 mt-2">Vertonung und Videoproduktion, das kann ein paar Minuten dauern.</p>
      )}
      <button
        onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
      >
        {cancelIcon}
        Abbrechen
      </button>
    </section>
  );
}

export function DoneStep({
  videoUrl,
  audioId,
  onDownloadMp4,
  onReset,
}: {
  videoUrl: string | null;
  audioId: string;
  onDownloadMp4: () => void;
  onReset: () => void;
}) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] py-8">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
          <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold mb-2 text-center">Fertig! Ihr Screencast ist bereit.</h2>

      {videoUrl && (
        <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
          <video key={videoUrl} controls className="w-full">
            <source src={videoUrl} type="video/mp4" />
            Ihr Browser unterstützt kein HTML5-Video.
          </video>
        </div>
      )}

      <div className="flex justify-center gap-3 mb-4">
        <button
          onClick={onDownloadMp4}
          aria-label="MP4"
          className="px-6 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors flex items-center gap-2"
        >
          <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          MP4
        </button>
        {audioId && (
          <a
            href={`/api/jobs/${audioId}/bundle`}
            download
            aria-label="Alles herunterladen (ZIP)"
            className="px-6 py-2 bg-white text-primary border border-primary text-sm font-medium rounded-md hover:bg-primary/5 transition-colors flex items-center gap-2"
          >
            <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Alles herunterladen (ZIP)
          </a>
        )}
      </div>

      <div className="flex justify-center">
        <button
          onClick={onReset}
          aria-label="Neue Präsentation hochladen"
          className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
        >
          Neue Präsentation
        </button>
      </div>
    </section>
  );
}

export function ErrorStep({
  errorMessage,
  failedRenderJobUuid,
  onRetry,
  onReset,
}: {
  errorMessage: string;
  failedRenderJobUuid: string | null;
  onRetry: () => void;
  onReset: () => void;
}) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-12">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
          <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-red-700 mb-2">Fehler bei der Screencast-Erstellung</h2>
      {errorMessage && <p className="text-sm text-red-600 mb-3">{errorMessage}</p>}
      {failedRenderJobUuid && (
        <p className="text-xs text-gray-500 mb-5">
          Klicke auf <strong>Wiederholen</strong> — bereits fertige Clips und Audio werden nicht wiederholt.
        </p>
      )}
      <div className="flex gap-3 justify-center">
        {failedRenderJobUuid && (
          <button
            onClick={onRetry}
            aria-label="Job wiederholen"
            className="px-6 py-2 text-sm text-white bg-primary rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
          >
            Wiederholen
          </button>
        )}
        <button
          onClick={onReset}
          aria-label="Neue Präsentation hochladen"
          className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
        >
          Neue Präsentation
        </button>
      </div>
    </section>
  );
}
