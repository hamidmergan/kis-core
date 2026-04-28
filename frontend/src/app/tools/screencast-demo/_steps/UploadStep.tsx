interface UploadStepProps {
  showSteps: boolean;
  isAdmin: boolean;
  fastMode: boolean;
  onShowStepsChange: (v: boolean) => void;
  onFastModeChange: (v: boolean) => void;
  onStart: () => void;
  onStartDirect: () => void;
}


export function UploadStep({
  showSteps, isAdmin, fastMode, onShowStepsChange, onFastModeChange, onStart, onStartDirect,
}: UploadStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-center gap-3 mb-1">
        <h1 className="text-xl font-bold">Screencast erstellen</h1>
        <span
          className="text-xs font-semibold px-3.5 py-1.5 rounded"
          style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
        >
          Demo
        </span>
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Laden Sie eine PowerPoint-Präsentation hoch. Die Präsentation wird
        per DeepL übersetzt und als vertontes Video exportiert.
      </p>

      {/* Disabled file drop zone */}
      <div className="mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed">
        <svg className="w-8 h-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
        <p className="text-sm text-gray-500">Datei hierher ziehen oder <span className="text-gray-400 font-medium">durchsuchen</span></p>
        <p className="text-xs text-gray-400 mt-1">Nur .pptx-Datei</p>
      </div>

      <label className="flex items-start gap-3 mb-4 select-none cursor-pointer">
        <input
          type="checkbox"
          checked={showSteps}
          onChange={(e) => onShowStepsChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
        />
        <div>
          <span className="text-sm font-medium text-gray-700">Zwischenschritte anzeigen und bearbeiten</span>
          <p className="text-xs text-gray-400 mt-0.5">Empfohlen für beste Ergebnisse</p>
        </div>
      </label>

      {isAdmin && (
        <label className="flex items-center gap-2 cursor-pointer select-none mt-4 mb-6">
          <input
            type="checkbox"
            checked={fastMode}
            onChange={(e) => onFastModeChange(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
          />
          <div>
            <span className="text-sm font-medium text-gray-700">Schnellmodus</span>
            <p className="text-xs text-gray-400 mt-0.5">Folienvorschau wird übersprungen, schnellere Verarbeitung.</p>
          </div>
        </label>
      )}

      <div className="flex gap-3 mt-6">
        <button
          onClick={showSteps ? onStart : onStartDirect}
          className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
        >
          Demo starten
        </button>
      </div>
    </section>
  );
}
