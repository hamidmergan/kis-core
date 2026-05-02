interface UploadStepProps {
  onStart: () => void;
}


export function UploadStep({ onStart }: UploadStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-xl font-bold">Screencast</h1>
        <span
          className="text-xs font-semibold px-3.5 py-1.5 rounded"
          style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
        >
          Demo
        </span>
      </div>
      <p className="text-sm text-muted mb-6">
        Aus PowerPoint-Folien ein vertontes Video erzeugen, wahlweise in einer anderen Sprache.
      </p>

      {/* Disabled file drop zone */}
      <div className="mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors border-border-soft bg-surface opacity-50 cursor-not-allowed">
        <svg className="w-8 h-8 text-muted-soft mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm text-muted">Datei hierher ziehen oder <span className="text-muted-soft font-medium">durchsuchen</span></p>
        <p className="text-xs text-muted-soft mt-1">Nur .pptx-Datei</p>
      </div>

      <div className="flex gap-3 mt-6">
        <button
          onClick={onStart}
          className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
        >
          Demo starten
        </button>
      </div>
    </section>
  );
}
