type ScriptInputMode = "generate" | "manual" | "import";

interface UserPromptStepProps {
  scriptInputMode: ScriptInputMode;
  importedScripts: string[] | null;
  importError: string | null;
  loading: boolean;
  onScriptInputModeChange: (mode: ScriptInputMode) => void;
  onClearImport: () => void;
  onJsonImport: (file: File) => void;
  onNext: () => void;
}


export function UserPromptStep({
  scriptInputMode, importedScripts, importError, loading,
  onScriptInputModeChange, onClearImport, onJsonImport, onNext,
}: UserPromptStepProps) {
  const setMode = (mode: ScriptInputMode) => {
    onScriptInputModeChange(mode);
    if (mode !== "import") onClearImport();
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Wie sollen die Skripte erstellt werden?</h2>
      <div className="mt-3 space-y-2">
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
          <input type="radio" name="scriptInputMode" value="generate" checked={scriptInputMode === "generate"}
            onChange={() => setMode("generate")} className="mt-0.5 accent-primary" />
          <div>
            <span className="text-sm font-medium text-gray-900">KI-Generierung</span>
            <p className="text-xs text-gray-500 mt-0.5">KI erstellt Skripte automatisch basierend auf den Folieninhalten.</p>
          </div>
        </label>
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
          <input type="radio" name="scriptInputMode" value="manual" checked={scriptInputMode === "manual"}
            onChange={() => setMode("manual")} className="mt-0.5 accent-primary" />
          <div>
            <span className="text-sm font-medium text-gray-900">Manuell eingeben</span>
            <p className="text-xs text-gray-500 mt-0.5">Alle Textfelder bleiben leer – Sie tippen die Skripte selbst ein.</p>
          </div>
        </label>
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
          <input type="radio" name="scriptInputMode" value="import" checked={scriptInputMode === "import"}
            onChange={() => onScriptInputModeChange("import")} className="mt-0.5 accent-primary" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-gray-900">Skript importieren</span>
            <p className="text-xs text-gray-500 mt-0.5">JSON-Datei hochladen – Array von Strings, ein Eintrag pro Folie.</p>
            {scriptInputMode === "import" && (
              <div className="mt-2">
                <label className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-primary border border-primary rounded-md hover:bg-primary/5 cursor-pointer transition-colors">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  JSON-Datei auswählen
                  <input type="file" accept=".json" className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) onJsonImport(f); }} />
                </label>
                {importedScripts && (
                  <p className="mt-1.5 text-xs text-green-600 flex items-center gap-1">
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {importedScripts.length} Skript{importedScripts.length !== 1 ? "e" : ""} geladen
                  </p>
                )}
                {importError && (
                  <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {importError}
                  </p>
                )}
              </div>
            )}
          </div>
        </label>
      </div>
      {scriptInputMode === "generate" && <div className="mt-5 space-y-4" />}
      <div className="flex gap-3 mt-4">
        <button onClick={onNext} disabled={loading}
          className="flex-1 px-4 py-2 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Weiter
        </button>
      </div>
    </section>
  );
}
