"use client";

import { useTranslations } from "next-intl";

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
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  const setMode = (mode: ScriptInputMode) => {
    onScriptInputModeChange(mode);
    if (mode !== "import") onClearImport();
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">{t("userPrompt.heading")}</h2>
      <div className="mt-3 space-y-2">
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-kb bg-kb/5" : "border-border-soft hover:border-border"}`}>
          <input type="radio" name="scriptInputMode" value="generate" checked={scriptInputMode === "generate"}
            onChange={() => setMode("generate")} className="mt-0.5 accent-kb" />
          <div>
            <span className="text-sm font-medium text-foreground">{t("userPrompt.generate")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.generateDesc")}</p>
          </div>
        </label>
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-kb bg-kb/5" : "border-border-soft hover:border-border"}`}>
          <input type="radio" name="scriptInputMode" value="manual" checked={scriptInputMode === "manual"}
            onChange={() => setMode("manual")} className="mt-0.5 accent-kb" />
          <div>
            <span className="text-sm font-medium text-foreground">{t("userPrompt.manual")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.manualDesc")}</p>
          </div>
        </label>
        <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-kb bg-kb/5" : "border-border-soft hover:border-border"}`}>
          <input type="radio" name="scriptInputMode" value="import" checked={scriptInputMode === "import"}
            onChange={() => onScriptInputModeChange("import")} className="mt-0.5 accent-kb" />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-foreground">{t("userPrompt.import")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.importDesc")}</p>
            {scriptInputMode === "import" && (
              <div className="mt-2">
                <label className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-kb border border-kb rounded-md hover:bg-kb/5 cursor-pointer transition-colors">
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                  {tDemo("selectJsonFile")}
                  <input type="file" accept=".json" className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) onJsonImport(f); }} />
                </label>
                {importedScripts && (
                  <p className="mt-1.5 text-xs text-success flex items-center gap-1">
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {t("userPrompt.scriptsLoaded", { n: importedScripts.length })}
                  </p>
                )}
                {importError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
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
          className="flex-1 px-4 py-2 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          {t("common.next")}
        </button>
      </div>
    </section>
  );
}
