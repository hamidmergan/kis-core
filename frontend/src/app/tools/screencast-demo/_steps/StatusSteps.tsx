import Spinner from "@/components/ui/Spinner";


export function TranslatingStep({ onCancel }: { onCancel: () => void }) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">Demo wird geladen...</p>
      <p className="text-xs text-muted-soft mt-2">Das kann je nach Dateigröße einige Sekunden dauern.</p>
      <button onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md hover:bg-error-bg transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Abbrechen
      </button>
    </section>
  );
}


export function GeneratingScriptsStep({ slideCount, onCancel }: { slideCount: number; onCancel: () => void }) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft animate-pulse">Sprechskripte werden generiert...</p>
      <p className="text-xs text-muted-soft mt-2">Die KI erstellt Skripte für {slideCount} Folien.</p>
      <button onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md hover:bg-error-bg transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Abbrechen
      </button>
    </section>
  );
}


export function RenderingStep({ renderProgressLabel, onCancel }: { renderProgressLabel: string; onCancel: () => void }) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
      <Spinner size="lg" className="justify-center mb-4" />
      <p className="text-sm text-foreground-soft">{renderProgressLabel || "Video wird erstellt..."}</p>
      {!renderProgressLabel && <p className="text-xs text-muted-soft mt-2">Vertonung und Videoproduktion, das kann ein paar Minuten dauern.</p>}
      <button onClick={onCancel}
        className="mt-6 px-4 py-2 text-sm text-error border border-error-border rounded-md hover:bg-error-bg transition-colors inline-flex items-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
        Abbrechen
      </button>
    </section>
  );
}


export function ErrorStep({ errorMessage, onReset }: { errorMessage: string; onReset: () => void }) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out] text-center py-12">
      <div className="flex justify-center mb-4">
        <div className="w-12 h-12 rounded-full bg-error-bg flex items-center justify-center">
          <svg className="w-6 h-6 text-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
      </div>
      <h2 className="text-lg font-bold text-error-strong mb-2">Fehler bei der Screencast-Erstellung</h2>
      {errorMessage && <p className="text-sm text-error mb-3">{errorMessage}</p>}
      <div className="flex gap-3 justify-center">
        <button onClick={onReset} aria-label="Neue Präsentation hochladen"
          className="px-6 py-2 text-sm text-foreground-soft border border-border rounded-md hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors">
          Neue Präsentation
        </button>
      </div>
    </section>
  );
}
