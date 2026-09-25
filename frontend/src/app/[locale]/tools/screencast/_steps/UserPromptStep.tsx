"use client";

import type { ReactNode, RefObject } from "react";
import { useTranslations } from "next-intl";
import StepFooter from "./StepFooter";

interface UserPromptStepProps {
  onBack: (() => void) | null;
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
  /** The demo offers no upload of an own file. */
  demo?: boolean;
  /** Extra documents for the generated scripts, shown with the AI option. */
  material?: ReactNode;
  nextBlocked?: boolean;
}

export default function UserPromptStep({
  onBack,
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
  demo = false,
  material,
  nextBlocked = false,
}: UserPromptStepProps) {
  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-2">{t("userPrompt.heading")}</h2>

      <div className="mt-6 space-y-3">
        <label
          className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-kb bg-kb/10" : "border-border hover:border-kb"}`}
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
            className="mt-0.5 accent-kb"
          />
          <div>
            <span className="text-sm font-medium text-foreground">{t("userPrompt.generate")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.generateDesc")}</p>
          </div>
        </label>

        <label
          className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-kb bg-kb/10" : "border-border hover:border-kb"}`}
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
            className="mt-0.5 accent-kb"
          />
          <div>
            <span className="text-sm font-medium text-foreground">{t("userPrompt.manual")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.manualDesc")}</p>
          </div>
        </label>

        <label
          className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-kb bg-kb/10" : "border-border hover:border-kb"}`}
        >
          <input
            type="radio"
            name="scriptInputMode"
            value="import"
            checked={scriptInputMode === "import"}
            onChange={() => onScriptInputModeChange("import")}
            className="mt-0.5 accent-kb"
          />
          <div className="flex-1 min-w-0">
            <span className="text-sm font-medium text-foreground">{t("userPrompt.import")}</span>
            <p className="text-xs text-muted mt-0.5">{t("userPrompt.importDesc")}</p>
            {scriptInputMode === "import" && demo && (
              <div className="mt-2 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-border-soft bg-surface px-4 py-5 opacity-60 cursor-not-allowed">
                <p className="text-xs text-muted">{tDemo("keinHochladen")}</p>
                <p className="text-xs text-muted-soft mt-0.5">{tDemo("importVorgegeben")}</p>
              </div>
            )}
            {scriptInputMode === "import" && !demo && (
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
                        ? "border-kb60 bg-kb20"
                        : jsonDragOver
                          ? "border-kb bg-kb/5"
                          : "border-border hover:border-kb"
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
                      <svg className="w-6 h-6 text-kb-dark mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <p className="text-xs font-medium text-kb-dark">
                        {t("userPrompt.scriptsLoaded", { n: importedScripts.length })}
                      </p>
                      <p className="text-xs text-muted-soft mt-0.5">{t("userPrompt.replaceHint")}</p>
                    </>
                  ) : (
                    <>
                      <svg className="w-6 h-6 text-muted-soft mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                        />
                      </svg>
                      <p className="text-xs text-foreground-soft">
                        {t("userPrompt.jsonDropPrefix")}
                        <span className="text-kb font-medium">{t("userPrompt.jsonDropBrowse")}</span>
                      </p>
                    </>
                  )}
                </div>
                {importError && (
                  <p className="mt-1.5 text-xs text-error flex items-center gap-1">
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

      {scriptInputMode === "generate" && material}

      <StepFooter onBack={onBack} nextLabel={t("common.next")} onNext={onNext} nextDisabled={loading || nextBlocked} />
    </section>
  );
}
