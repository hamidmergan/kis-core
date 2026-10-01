"use client";

import { useCallback, useRef, useState } from "react";

export type ScriptInputMode = "generate" | "manual" | "import" | "notes";

export function useScriptInputMode(start: ScriptInputMode = "generate") {
  const [mode, setMode] = useState<ScriptInputMode>(start);
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [jsonDragOver, setJsonDragOver] = useState(false);
  const jsonFileRef = useRef<HTMLInputElement>(null);

  const resetImport = useCallback(() => {
    setImportedScripts(null);
    setImportError(null);
  }, []);

  const reset = useCallback(() => {
    setMode(start);
    setImportedScripts(null);
    setImportError(null);
    setJsonDragOver(false);
  }, [start]);

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
