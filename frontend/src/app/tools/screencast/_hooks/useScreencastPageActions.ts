"use client";

import { useCallback, type Dispatch, type MutableRefObject, type RefObject, type SetStateAction } from "react";
import { notifyJobsChanged } from "@/lib/jobs-events";
import type { ScreencastState, ScreencastStep, SlideData } from "@/types";
import type { useAutoModeFlow } from "@/hooks/useAutoModeFlow";
import type { useFailedRender } from "@/hooks/useFailedRender";
import type { useRenderResult } from "@/hooks/useRenderResult";
import type { useScriptInputMode } from "@/hooks/useScriptInputMode";
import type { RegenApplyMode } from "../_components/RegenChatModal";
import type { FlowAction } from "../_reducer";
import { parseScriptJsonFile, triggerBlobDownload, triggerUrlDownload, checkJobFolderExists } from "../_utils";

const RENDER_SESSION_KEY = "kis_screencast_active_render";

interface Options {
  // Flow state
  step: ScreencastStep;
  slides: SlideData[];
  translateJobUuid: string;
  maxReachedIdx: number;
  mode: "auto" | "manual";
  dispatch: Dispatch<FlowAction>;

  // Local state setters
  resetFile: () => void;
  setSpeed: (v: number) => void;
  setSlidePause: (v: number) => void;
  setGlossaryIds: (v: string[]) => void;
  setSourceLang: (v: string) => void;
  setTargetLang: (v: string) => void;
  setTtsProvider: (v: "elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten") => void;
  setImportError: (v: string | null) => void;
  setImportedScripts: (v: string[] | null) => void;

  // Provider flags (for reset fallback)
  kokoroEnabled: boolean;
  fishSpeechEnabled: boolean;
  elevenlabsEnabled: boolean;

  // Sub-hooks / orchestrators
  auto: ReturnType<typeof useAutoModeFlow>;
  failedRender: ReturnType<typeof useFailedRender>;
  renderResult: ReturnType<typeof useRenderResult>;
  scriptInput: ReturnType<typeof useScriptInputMode>;

  // Script editing
  resetScriptEditing: () => void;
  autosaveScripts: (scripts: string[], finalSave?: boolean) => void;

  // Regen anchor
  regenAnchorText: string;
  closeRegen: () => void;

  // File download info
  file: File | null;
  downloadBlob: Blob | null;
  audioId: string | null;
  autoDownloadBlob: Blob | null;
  autoDownloadName: string;

  // Refs
  abortControllerRef: MutableRefObject<AbortController | null>;
  currentJobUuidRef: MutableRefObject<string | null>;
  fileRef: RefObject<HTMLInputElement | null>;

  // Error helper producer
  goError: (msg: string) => void;

  // Render-state setters for cancel-rendering handler
  setRenderProgressLabel: Dispatch<SetStateAction<string>>;
  setAutoState: Dispatch<SetStateAction<ScreencastState>>;
}

export function useScreencastPageActions(opts: Options) {
  const {
    step, slides, translateJobUuid, maxReachedIdx, mode, dispatch,
    resetFile, setSpeed, setSlidePause, setGlossaryIds,
    setSourceLang, setTargetLang, setTtsProvider,
    setImportError, setImportedScripts,
    kokoroEnabled, fishSpeechEnabled, elevenlabsEnabled,
    auto, failedRender, renderResult, scriptInput,
    resetScriptEditing, autosaveScripts,
    regenAnchorText, closeRegen,
    file, downloadBlob, audioId, autoDownloadBlob, autoDownloadName,
    abortControllerRef, currentJobUuidRef, fileRef,
    goError,
    setRenderProgressLabel, setAutoState,
  } = opts;

  const resetAll = useCallback((deleteJob = true) => {
    abortControllerRef.current?.abort();
    if (deleteJob) {
      const uuidToDelete = translateJobUuid || currentJobUuidRef.current;
      if (uuidToDelete) {
        fetch(`/api/jobs/${uuidToDelete}`, { method: "DELETE", credentials: "include" }).catch(() => {});
        notifyJobsChanged();
      }
    }
    currentJobUuidRef.current = null;

    dispatch({ type: "RESET" });
    resetFile();
    setSpeed(0.9);
    setSlidePause(0.5);
    setGlossaryIds(["", "", ""]);
    renderResult.clear();
    resetScriptEditing();
    auto.reset();
    failedRender.clear();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setSourceLang("DE");
    setTargetLang("EN-US");
    scriptInput.reset();
    setTtsProvider(kokoroEnabled ? "kokoro" : fishSpeechEnabled ? "fish_speech" : elevenlabsEnabled ? "elevenlabs" : "kokoro");
    if (fileRef.current) fileRef.current.value = "";
  }, [translateJobUuid]);

  const handleStepClick = useCallback((index: number) => {
    if (step === "rendering" || step === "generating-scripts") return;
    if (index > maxReachedIdx) return;
    const targets: Record<number, ScreencastStep | null> = {
      0: null,
      1: null,
      2: "translation-review",
      3: "user-prompt",
      4: "script-review",
      5: "tts-settings",
      6: null,
      7: "done",
    };
    const target = targets[index];
    if (!target) return;
    dispatch({ type: "SET_STEP", step: target });
  }, [maxReachedIdx, step]);

  const checkJobFolder = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return true;
    const exists = await checkJobFolderExists(translateJobUuid);
    if (!exists) {
      goError("Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten");
      return false;
    }
    return true;
  }, [translateJobUuid, goError]);

  const handleAutoDownload = useCallback(() => {
    if (!autoDownloadBlob) return;
    triggerBlobDownload(autoDownloadBlob, autoDownloadName);
  }, [autoDownloadBlob, autoDownloadName]);

  const handleAutoZipDownload = useCallback(() => {
    if (!audioId) return;
    triggerUrlDownload(`/api/jobs/${audioId}/bundle`);
  }, [audioId]);

  const handleJsonImport = useCallback(async (file: File) => {
    setImportError(null);
    const result = await parseScriptJsonFile(file);
    if ("error" in result && result.error) setImportError(result.error);
    else if (result.scripts) setImportedScripts(result.scripts);
  }, [setImportError, setImportedScripts]);

  const handleAcceptScripts = useCallback(() => {
    autosaveScripts(slides.map((s) => s.script), true);
    dispatch({ type: "SET_STEP", step: "tts-settings" });
    if (translateJobUuid) {
      fetch("/api/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translate_job_uuid: translateJobUuid }),
        credentials: "include",
      }).catch(() => {});
    }
  }, [translateJobUuid, slides, autosaveScripts]);

  const handleDownload = useCallback(() => {
    if (!downloadBlob) return;
    const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
    triggerBlobDownload(downloadBlob, `${stem}_screencast_EN.mp4`);
  }, [downloadBlob, file]);

  const applyRegen = useCallback((index: number, mode: RegenApplyMode, content: string) => {
    const current = slides[index].script || "";
    let newScript = current;
    if (mode === "replace-all" || !regenAnchorText) {
      newScript = content;
    } else if (mode === "replace-selection") {
      newScript = current.replace(regenAnchorText, content);
    } else if (mode === "insert-before") {
      newScript = current.replace(regenAnchorText, content + " " + regenAnchorText);
    } else if (mode === "insert-after") {
      newScript = current.replace(regenAnchorText, regenAnchorText + " " + content);
    }
    dispatch({ type: "UPDATE_SLIDE_SCRIPT", index, script: newScript });
    const updated = slides.map((s, i) => i === index ? { ...s, script: newScript } : s);
    autosaveScripts(updated.map((s) => s.script));
    closeRegen();
  }, [slides, regenAnchorText, autosaveScripts, closeRegen]);

  const handleBackToScripts = useCallback(() => {
    if (step === "rendering") return;
    dispatch({ type: "SET_STEP", step: "script-review" });
  }, [step]);

  const handleCancelTranslating = useCallback(() => {
    const uuid = currentJobUuidRef.current;
    currentJobUuidRef.current = null;
    abortControllerRef.current?.abort();
    if (uuid) {
      fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {});
      notifyJobsChanged();
    }
    dispatch({ type: "SET_STEP", step: "upload" });
    dispatch({ type: "SET_LOADING", loading: false });
  }, []);

  const handleCancelGeneratingScripts = useCallback(() => {
    const uuid = currentJobUuidRef.current;
    currentJobUuidRef.current = null;
    abortControllerRef.current?.abort();
    if (uuid) {
      fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
      notifyJobsChanged();
    }
    dispatch({ type: "SET_STEP", step: "translation-review" });
    dispatch({ type: "SET_LOADING", loading: false });
  }, []);

  const handleCancelRendering = useCallback(async () => {
    const uuid = currentJobUuidRef.current;
    currentJobUuidRef.current = null;
    abortControllerRef.current?.abort();
    if (uuid) {
      await fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
      notifyJobsChanged();
    }
    setRenderProgressLabel("");
    setAutoState("idle");
    dispatch({ type: "SET_STEP", step: mode === "auto" ? "upload" : "tts-settings" });
    dispatch({ type: "SET_LOADING", loading: false });
  }, [mode, setRenderProgressLabel, setAutoState]);

  return {
    resetAll,
    handleStepClick,
    checkJobFolder,
    handleAutoDownload,
    handleAutoZipDownload,
    handleJsonImport,
    handleAcceptScripts,
    handleDownload,
    applyRegen,
    handleBackToScripts,
    handleCancelTranslating,
    handleCancelGeneratingScripts,
    handleCancelRendering,
  };
}
