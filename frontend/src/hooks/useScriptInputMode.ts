"use client";

import { useCallback, useRef, useState } from "react";

export type ScriptInputMode = "generate" | "manual" | "import";

export function useScriptInputMode() {
  const [mode, setMode] = useState<ScriptInputMode>("generate");
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [jsonDragOver, setJsonDragOver] = useState(false);
  const jsonFileRef = useRef<HTMLInputElement>(null);

  const resetImport = useCallback(() => {
    setImportedScripts(null);
    setImportError(null);
  }, []);

  const reset = useCallback(() => {
    setMode("generate");
    setImportedScripts(null);
    setImportError(null);
    setJsonDragOver(false);
  }, []);

  return {
    mode,
    setMode,
    importedScripts,
    setImportedScripts,
    importError,
    setImportError,
    jsonDragOver,
    setJsonDragOver,
    jsonFileRef,
    resetImport,
    reset,
  };
}
