"use client";

import type { RefObject } from "react";

interface UserPromptStepProps {
  scriptInputMode: "generate" | "manual" | "import";
  importedScripts: string[] | null;
  importError: string | null;
  jsonDragOver: boolean;
  jsonFileRef: RefObject<HTMLInputElement | null>;
  loading: boolean;
  onScriptInputModeChange: (mode: "generate" | "manual" | "import") => void;
  onResetImport: () => void;
  onJsonDragOverChange: (v: boolean) => void;
  onJsonImport: (file: File) => void;
  onNext: () => void;
}

export default function UserPromptStep({
  scriptInputMode,
  importedScripts,
  importError,
  jsonDragOver,
  jsonFileRef,
  loading,
  onScriptInputModeChange,
  onResetImport,
  onJsonDragOverChange,
  onJsonImport,
  onNext,
}: UserPromptStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Wie sollen die Skripte erstellt werden?</h2>

      <div className="mt-3 space-y-2">
        <label
          className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}
        >
          <input
            type="radio"
            name="scriptInputMode"
            value="generate"
            checked={scriptInputMode === "generate"}
            onChange={() => {
              onScriptInputModeChange("generate");
              onResetImport();
            }}
            className="mt-0.5 accent-primary"
          />
          <div>
            <span className="text-sm font-medium text-gray-900">KI-Generierung</span>
            <p className="text-xs text-gray-500 mt-0.5">KI erstellt Skripte automatisch basierend auf den Folieninhalten.</p>
          </div>
        </label>

        <label
          className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}
        >
          <input
            type="radio"
            name="scriptInputMode"
            value="manual"
            checked={scriptInputMode === "manual"}
            onChange={() => {
              onScriptInputModeChange("manual");
              onResetImport();
            }}
            className="mt-0.5 accent-primary"
          />
          <div>
            <span className="text-sm font-medium text-gray-900">Manuell eingeben</span>
            <p className="text-xs text-gray-500 mt-0.5">Alle Textfelder bleiben leer – Sie tippen die Skripte selbst ein.</p>
          </div>
        </label>

        <label
          className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}
        >
          <input
            type="radio"
            name="scriptInputMode"
            value="import"
            checked={scriptInputMode === "import"}
            onChange={() => onScriptInputModeChange("import")}
            className="mt-0.5 accent-primary"
          />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-gray-900">Skript importieren</span>
            <p className="text-xs text-gray-500 mt-0.5">JSON-Datei hochladen – Array von Strings, ein Eintrag pro Folie.</p>
            {scriptInputMode === "import" && (
              <div className="mt-2">
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    onJsonDragOverChange(true);
                  }}
                  onDragLeave={() => onJsonDragOverChange(false)}
                  onDrop={(e) => {
                    e.preventDefault();
                    onJsonDragOverChange(false);
                    const f = e.dataTransfer.files?.[0];
                    if (f) onJsonImport(f);
                  }}
                  onClick={() => jsonFileRef.current?.click()}
                  className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-5 cursor-pointer transition-colors
                    ${
                      importedScripts
                        ? "border-green-400 bg-green-50"
                        : jsonDragOver
                          ? "border-primary bg-primary/5"
                          : "border-gray-300 hover:border-primary"
                    }`}
                >
                  <input
                    ref={jsonFileRef}
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) onJsonImport(f);
                      e.target.value = "";
                    }}
                  />
                  {importedScripts ? (
                    <>
                      <svg className="w-6 h-6 text-green-500 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <p className="text-xs font-medium text-green-700">
                        {importedScripts.length} Skript{importedScripts.length !== 1 ? "e" : ""} geladen
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">Klicken oder ziehen zum Ersetzen</p>
                    </>
                  ) : (
                    <>
                      <svg className="w-6 h-6 text-gray-400 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                        />
                      </svg>
                      <p className="text-xs text-gray-600">
                        JSON-Datei hierher ziehen oder <span className="text-primary font-medium">auswählen</span>
                      </p>
                    </>
                  )}
                </div>
                {importError && (
                  <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      />
                    </svg>
                    {importError}
                  </p>
                )}
              </div>
            )}
          </div>
        </label>
      </div>

      <div className="flex gap-3 mt-4">
        <button
          onClick={onNext}
          disabled={loading}
          className="flex-1 px-4 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Weiter
        </button>
      </div>
    </section>
  );
}
