"use client";

import { Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail, type JobStatus } from "@/lib/api";
import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import type {
  ScreencastState,
  ScreencastStep,
  SlideData,
} from "@/types";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { stepToIndex } from "@/components/screencast/steps";
import UploadStep from "./_steps/UploadStep";
import {
  TranslatingStep,
  GeneratingScriptsStep,
  RenderingStep,
  DoneStep,
  ErrorStep,
} from "./_steps/StatusSteps";
import UserPromptStep from "./_steps/UserPromptStep";
import TranslationReviewStep from "./_steps/TranslationReviewStep";
import ScriptReviewStep from "./_steps/ScriptReviewStep";
import TtsSettingsStep from "./_steps/TtsSettingsStep";
import Lightbox from "./_components/Lightbox";
import RegenChatModal, { type RegenApplyMode } from "./_components/RegenChatModal";
import { parseScriptJsonFile, renderProgressLabel as renderProgressLabelFn, computeVoiceLabel, triggerBlobDownload, triggerUrlDownload, checkHasActiveJob, checkJobValidity, checkJobFolderExists } from "./_utils";
import { flowReducer, INITIAL_FLOW_STATE } from "./_reducer";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { wordCount, estimateDuration } from "@/lib/text";
import { useFileDropzone } from "@/hooks/useFileDropzone";
import { useVoices } from "@/hooks/useVoices";
import { useScriptEditing, useScriptAutosave } from "@/hooks/useScriptEditing";
import { useScreencastResume, useSlideImageBackfill, useActiveJobCheck } from "@/hooks/useScreencastResume";
import { useLanguageConfig } from "@/hooks/useLanguageConfig";
import { useEnabledTools } from "@/hooks/useEnabledTools";
import { useIsAdmin } from "@/hooks/useIsAdmin";
import { useRenderResult } from "@/hooks/useRenderResult";
import { useFailedRender } from "@/hooks/useFailedRender";
import { useAutoModeFlow } from "@/hooks/useAutoModeFlow";
import { useScriptInputMode } from "@/hooks/useScriptInputMode";
import { useRegenAnchor } from "@/hooks/useRegenAnchor";

const ACCEPTED_EXTENSIONS = [".pptx"];

interface TranslateResponse {
  slide_count: number;
  slide_texts: string[];
  slide_images: string[];
  translate_job_uuid?: string;
  user_prompt?: string;
}

interface GenerateScriptsResponse {
  scripts: string[];
}


const RENDER_SESSION_KEY = "kis_screencast_active_render";
const SCREENCAST_MAX_CHARS = 100_000;

function ScreencastPageInner() {
  const { mergeToApiJson } = useGlossaries();

  // ── Auto mode state ──
  const auto = useAutoModeFlow();
  const {
    state: autoState,
    setState: setAutoState,
    downloadBlob: autoDownloadBlob,
    downloadName: autoDownloadName,
    error: autoError,
    setError: setAutoError,
  } = auto;
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const failedRender = useFailedRender();
  const { jobUuid: failedRenderJobUuid, isAuto: failedRenderIsAuto } = failedRender;
  const [ttsSettingsError, setTtsSettingsError] = useState("");

  // ── Job-Flow-State via Reducer ──
  const [flow, dispatch] = useReducer(flowReducer, INITIAL_FLOW_STATE);
  const { step, loading, errorMessage, slides, translateJobUuid, maxReachedIdx, correctedFileName, lightboxIndex, isResumedJob } = flow;

  const [mode, setMode] = useState<"auto" | "manual">("manual");
  const {
    file,
    fileError,
    dragOver,
    selectFile: handleFileSelect,
    onDragOver: handleDragOver,
    onDragLeave: handleDragLeave,
    onDrop: handleDrop,
    reset: resetFile,
  } = useFileDropzone({ acceptedExtensions: ACCEPTED_EXTENSIONS });
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  const regen = useRegenAnchor();
  const { regeneratingSlide, anchorText: regenAnchorText, anchorSlide: regenAnchorSlide } = regen;


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const renderResult = useRenderResult();
  const { downloadBlob, videoUrl, audioId, audioCount, apply: applyRenderResult, clear: clearRenderResult } = renderResult;

  const autosaveScripts = useScriptAutosave({ jobUuid: translateJobUuid });
  const {
    openAccordion,
    editingSlide,
    editBuffer,
    setEditBuffer,
    startEdit: startEditHook,
    cancelEdit,
    saveEdit,
    toggleAccordion,
    reset: resetScriptEditing,
  } = useScriptEditing({
    onSave: (index, newScript) => {
      dispatch({ type: "UPDATE_SLIDE_SCRIPT", index, script: newScript });
      const updated = slides.map((s, i) => (i === index ? { ...s, script: newScript } : s));
      autosaveScripts(updated.map((s) => s.script));
    },
  });
  const startEdit = (index: number) => startEditHook(index, slides[index]?.script ?? "");

  const voicesResult = useVoices();
  const {
    loaded: providersLoaded,
    providers,
    defaultProvider,
    defaultVoiceId,
    elevenlabs: voices,
    kokoro: kokoroVoices,
    mylab: mylabVoices,
    thorsten: thorstenVoices,
  } = voicesResult;
  const elevenlabsEnabled = providers.elevenlabs;
  const fishSpeechEnabled = providers.fish_speech;
  const kokoroEnabled = providers.kokoro;
  const mylabEnabled = providers.mylab;
  const thorstenEnabled = providers.thorsten;
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<"elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten">("kokoro");
  useEffect(() => {
    if (defaultProvider) setTtsProvider(defaultProvider);
  }, [defaultProvider]);
  useEffect(() => {
    if (defaultVoiceId && !voiceId) setVoiceId(defaultVoiceId);
  }, [defaultVoiceId, voiceId]);
  const { languages, sourceLang, setSourceLang, targetLang, setTargetLang } = useLanguageConfig();
  const [fastMode, setFastMode] = useState(false);
  const { isAdmin } = useIsAdmin();
  const { isToolEnabled } = useEnabledTools();
  const showDemoLink = isToolEnabled("screencast-demo");

  const [hasActiveJob, setHasActiveJob] = useActiveJobCheck("screencast");

  const scriptInput = useScriptInputMode();
  const {
    mode: scriptInputMode,
    setMode: setScriptInputMode,
    importedScripts,
    setImportedScripts,
    importError,
    setImportError,
    jsonDragOver,
    setJsonDragOver,
    jsonFileRef,
    resetImport,
  } = scriptInput;

  const fileRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);
  const isGeneratingScriptsRef = useRef(false);

  // ── Abort on unmount ──
  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
  }, []);


  const { resumeLoading } = useScreencastResume((payload) => {
    dispatch({ type: "RESUME", jobUuid: payload.jobUuid, slides: payload.slides, step: payload.step, stepIdx: payload.stepIdx });
  });

  useSlideImageBackfill(translateJobUuid, slides, (images) => {
    dispatch({ type: "BACKFILL_IMAGES", images });
  });

  const checkBeforeSubmit = useCallback(async (): Promise<boolean> => {
    const result = await checkHasActiveJob("screencast");
    if (!result.ok) return true;
    setHasActiveJob(result.hasActive);
    return !result.hasActive;
  }, [setHasActiveJob]);

  const checkJobStillValid = useCallback(checkJobValidity, []);

  // ── Helpers ──

  const resetAll = useCallback((deleteJob = true) => {
    // Abort any in-flight request and optionally delete the current job (DB + MinIO)
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
    clearRenderResult();
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

  const newSignal = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current.signal;
  };

  const goError = useCallback((msg: string) => {
    dispatch({ type: "GO_ERROR", message: msg });
  }, []);

  const checkJobFolder = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return true;
    const exists = await checkJobFolderExists(translateJobUuid);
    if (!exists) {
      goError("Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten");
      return false;
    }
    return true;
  }, [translateJobUuid, goError]);

  const onRenderProgress = useCallback((status: JobStatus) => {
    setRenderProgressLabel(renderProgressLabelFn(status));
  }, []);

  // ── Auto mode submit ──
  const handleAutoSubmit = useCallback(async () => {
    if (!file) return;
    const ok = await checkBeforeSubmit();
    if (!ok) return;
    const signal = newSignal();
    auto.start();
    dispatch({ type: "SET_STEP", step: "rendering" });
    dispatch({ type: "SET_LOADING", loading: true });

    try {
      const glossaryJson = mergeToApiJson(glossaryIds);
      const formData = new FormData();
      const voiceLabel = computeVoiceLabel(ttsProvider, voiceId, kokoroVoices, voices);

      formData.append("file", file);
      formData.append("speed", String(speed));
      formData.append("dpi", String(dpi));
      formData.append("voice_id", voiceId);
      formData.append("voice_label", voiceLabel);
      formData.append("provider", ttsProvider);
      formData.append("source_lang", sourceLang);
      formData.append("target_lang", targetLang);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);

      const uploadRes = await fetch("/api/screencast", { method: "POST", body: formData, credentials: "include", signal });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid, isAuto: true }));
      notifyJobsChanged();

      const jobResult = await pollJob(job_uuid, onRenderProgress, 5000, signal, () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000);
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");
      const meta = jobResult.meta ?? {};
      applyRenderResult(blob, { audioId: meta.audio_id as string | undefined, audioCount: meta.audio_count as number | undefined });
      const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
      auto.succeed(blob, `${stem}_screencast.mp4`);
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "upload" });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.mark(currentJobUuidRef.current, true);
      setAutoState("error");
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, speed, dpi, voiceId, sourceLang, targetLang, glossaryIds, mergeToApiJson, checkBeforeSubmit, onRenderProgress, goError]);

  const handleAutoDownload = () => {
    if (!autoDownloadBlob) return;
    triggerBlobDownload(autoDownloadBlob, autoDownloadName);
  };

  const handleAutoZipDownload = useCallback(() => {
    if (!audioId) return;
    triggerUrlDownload(`/api/jobs/${audioId}/bundle`);
  }, [audioId]);

  // ── Step: Upload → Translating (or auto) ──
  const handleUploadNext = useCallback(async () => {
    if (!file) return;
    if (mode === "auto") {
      handleAutoSubmit();
      return;
    }

    const ok = await checkBeforeSubmit();
    if (!ok) return;

    dispatch({ type: "SET_STEP", step: "translating" });
    dispatch({ type: "SET_LOADING", loading: true });
    const signal = newSignal();

    // ── Same-language path: skip DeepL, upload as-is, go directly to user-prompt ──
    if (sourceLang === targetLang) {
      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/api/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          credentials: "include",
          signal,
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
          throw new Error(parseDetail(error.detail, `Fehler: ${response.status}`));
        }

        const data: { translate_job_uuid: string; slide_texts: string[]; slide_images: string[] } =
          await response.json();

        if (data.translate_job_uuid) {
          dispatch({ type: "SET_JOB_UUID", uuid: data.translate_job_uuid });
          notifyJobsChanged();
        }

        dispatch({
          type: "SET_SLIDES",
          slides: data.slide_texts.map((text, i) => ({
            index: i,
            imageBase64: data.slide_images[i] || "",
            extractedText: text,
            script: "",
          })),
        });

        dispatch({ type: "SET_LOADING", loading: false });
        dispatch({ type: "SET_STEP", step: "user-prompt" });
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        goError(err instanceof Error ? err.message : "Unbekannter Fehler");
      }
      return;
    }

    // ── DE path: translate via DeepL → queue job, poll, then show review ──
    try {
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
      formData.append("fast_mode", String(fastMode));
      formData.append("source_lang", sourceLang);
      formData.append("target_lang", targetLang);

      const uploadRes = await fetch("/api/screencast/translate", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });

      if (!uploadRes.ok) {
        const error = await uploadRes.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(error.detail, `Fehler: ${uploadRes.status}`));
      }

      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      dispatch({ type: "SET_JOB_UUID", uuid: job_uuid });
      notifyJobsChanged();

      // Poll until translation job completes (stops at awaiting_user)
      const jobResult = await pollJob(job_uuid, undefined, 3000, signal);
      currentJobUuidRef.current = null;

      // Result comes inline from the jobs endpoint for JSON-result jobs
      const data = (jobResult.result ?? {}) as unknown as TranslateResponse;

      dispatch({
        type: "SET_SLIDES",
        slides: (data.slide_texts || []).map((text, i) => ({
          index: i,
          imageBase64: (data.slide_images || [])[i] || "",
          extractedText: text,
          script: "",
        })),
      });

      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "translation-review" });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [file, mode, sourceLang, targetLang, fastMode, handleAutoSubmit, checkBeforeSubmit, goError, glossaryIds, mergeToApiJson]);

  // ── Download translated PPTX ──
  const handleDownloadTranslatedPptx = useCallback(async () => {
    if (!translateJobUuid) return;
    try {
      const res = await fetch(`/api/screencast/pptx/${translateJobUuid}`, { credentials: "include" });
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
      a.download = `${stem}.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PPTX download failed:", err);
    }
  }, [translateJobUuid, file]);

  // ── Upload corrected PPTX ──
  const handleUploadCorrectedPptx = useCallback(
    async (correctedFile: File) => {
      dispatch({ type: "SET_LOADING", loading: true });
      const signal = newSignal();

      try {
        const formData = new FormData();
        formData.append("file", correctedFile);
        if (translateJobUuid) formData.append("translate_job_uuid", translateJobUuid);

        const response = await fetch("/api/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          credentials: "include",
          signal,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: "Fehler beim Hochladen" }));
          throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
        }

        const data: { slide_texts: string[]; slide_images: string[] } =
          await response.json();

        dispatch({
          type: "SET_SLIDES",
          slides: data.slide_texts.map((text, i) => ({
            index: i,
            imageBase64: data.slide_images[i] || "",
            extractedText: text,
            script: "",
          })),
        });

        dispatch({ type: "SET_CORRECTED_FILENAME", name: correctedFile.name });
        dispatch({ type: "SET_LOADING", loading: false });
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        goError(err instanceof Error ? err.message : "Unbekannter Fehler");
      }
    },
    [goError, translateJobUuid],
  );

  const handleJsonImport = useCallback(async (file: File) => {
    setImportError(null);
    const result = await parseScriptJsonFile(file);
    if ("error" in result && result.error) setImportError(result.error);
    else if (result.scripts) setImportedScripts(result.scripts);
  }, []);

  // ── Translation review → Generate scripts ──
  const handleAcceptTranslation = useCallback(async () => {
    if (isGeneratingScriptsRef.current) return;
    // If we have a specific job to continue, check its current status directly.
    // checkBeforeSubmit would block here because awaiting_user now counts as active.
    if (translateJobUuid) {
      const validity = await checkJobStillValid(translateJobUuid);
      if (validity === "running") {
        goError("Dieser Job wird bereits in einem anderen Tab verarbeitet. Bitte wechseln Sie zur Jobliste.");
        return;
      }
      if (validity === "deleted") {
        goError("Der Job wurde gelöscht oder abgebrochen. Bitte starten Sie einen neuen Screencast.");
        return;
      }
    } else {
      const ok = await checkBeforeSubmit();
      if (!ok) { window.location.href = "/my-jobs"; return; }
    }
    if (!await checkJobFolder()) return;
    isGeneratingScriptsRef.current = true;
    if (translateJobUuid) currentJobUuidRef.current = translateJobUuid;
    dispatch({ type: "SET_STEP", step: "generating-scripts" });
    dispatch({ type: "SET_LOADING", loading: true });
    notifyJobsChanged();
    const signal = newSignal();

    try {
      const scriptsData = await api.postJson<GenerateScriptsResponse>(
        "/api/screencast/generate-scripts",
        {
          slide_texts: slides.map((s) => s.extractedText),
          glossary_json: mergeToApiJson(glossaryIds),
          translate_job_uuid: translateJobUuid || null,
          add_greeting: true,
          add_closing: true,
          min_chars: 1500,
          max_chars: 2000,
          source_lang: sourceLang,
          target_lang: targetLang,
        },
        signal,
      );

      const updatedSlides = slides.map((s, i) => ({
        ...s,
        script: scriptsData.scripts[i] || "",
      }));
      dispatch({ type: "SET_SLIDES", slides: updatedSlides });

      currentJobUuidRef.current = null;
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "script-review" });
      isGeneratingScriptsRef.current = false;
      notifyJobsChanged();
    } catch (err) {
      isGeneratingScriptsRef.current = false;
      notifyJobsChanged();
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, glossaryIds, mergeToApiJson, goError, checkJobFolder, checkBeforeSubmit, checkJobStillValid, translateJobUuid]);


  // ── Accept scripts → TTS settings + fire-and-forget prerender + save ──
  const handleAcceptScripts = useCallback(() => {
    autosaveScripts(slides.map((s) => s.script), true); // save accepted_scripts.json
    dispatch({ type: "SET_STEP", step: "tts-settings" });
    if (translateJobUuid) {
      fetch("/api/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translate_job_uuid: translateJobUuid }),
        credentials: "include",
      }).catch(() => {}); // fire and forget
    }
  }, [translateJobUuid, slides, autosaveScripts]);

  // ── Shared: process render response (binary video + subtitles in header) ──
  const processRenderResponse = useCallback(async (response: Response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Render-Fehler" }));
      throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
    }

    const blob = await response.blob();
    const aId = response.headers.get("X-Audio-Id") ?? undefined;
    const aCountRaw = response.headers.get("X-Audio-Count");
    applyRenderResult(blob, { audioId: aId, audioCount: aCountRaw ? (parseInt(aCountRaw, 10) || 0) : undefined });
    dispatch({ type: "SET_LOADING", loading: false });
    dispatch({ type: "SET_STEP", step: "done" });
  }, [applyRenderResult]);

  const processRenderResultFromJob = useCallback(async (jobResult: JobStatus) => {
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");
    const meta = jobResult.meta ?? {};
    applyRenderResult(blob, { audioId: meta.audio_id as string | undefined, audioCount: meta.audio_count as number | undefined });
    dispatch({ type: "SET_LOADING", loading: false });
    dispatch({ type: "SET_STEP", step: "done" });
  }, [applyRenderResult]);

  // ── Start rendering ──
  const handleStartRender = useCallback(async () => {
    setTtsSettingsError("");
    if (!translateJobUuid) {
      const ok = await checkBeforeSubmit();
      if (!ok) return;
    }
    dispatch({ type: "SET_STEP", step: "rendering" });
    dispatch({ type: "SET_LOADING", loading: true });
    const signal = newSignal();
    try {
      // No signal on the POST — ensures we always get job_uuid before checking abort.
      // If signal fires during the POST, the job still starts on the backend.
      // We catch that case below and cancel immediately.
      const uploadRes = await fetch("/api/screencast/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scripts: slides.map((s) => s.script),
          translate_job_uuid: translateJobUuid,
          voice_id: voiceId,
          voice_label: computeVoiceLabel(ttsProvider, voiceId, kokoroVoices, voices),
          speed,
          slide_pause: slidePause,
          dpi,
          provider: ttsProvider,
        }),
        credentials: "include",
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Render-Fehler" }));
        // 409 = previous render still stopping — stay on settings, show inline message
        if (uploadRes.status === 409) {
          dispatch({ type: "SET_STEP", step: "tts-settings" });
          dispatch({ type: "SET_LOADING", loading: false });
          setTtsSettingsError("Der vorherige Render wird noch beendet. Bitte einen Moment warten und erneut versuchen.");
          return;
        }
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid, isAuto: false }));
      notifyJobsChanged();

      // If user clicked cancel while POST was in flight, cancel the job now
      if (signal.aborted) {
        await fetch(`/api/jobs/${job_uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
        currentJobUuidRef.current = null;
        return;
      }

      const jobResult = await pollJob(job_uuid, onRenderProgress, 5000, signal, () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000);
      currentJobUuidRef.current = null;
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.mark(currentJobUuidRef.current, false);
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, translateJobUuid, voiceId, speed, slidePause, dpi, goError, processRenderResultFromJob, checkBeforeSubmit, onRenderProgress]);

  // ── Retry failed render job ──
  const handleRetryRender = useCallback(async () => {
    const uuid = failedRenderJobUuid;
    if (!uuid) return;
    try {
      const res = await fetch(`/api/jobs/${uuid}/retry`, { method: "POST", credentials: "include" });

      if (res.status === 409) {
        // Job already running or succeeded — check actual status and continue accordingly
        const jobRes = await fetch(`/api/jobs/${uuid}`, { credentials: "include" });
        const jobData = await jobRes.json();
        if (jobData.status === "failed") {
          // Still failed → blocked by concurrent job limit
          const err = await res.json().catch(() => ({}));
          throw new Error(parseDetail(err.detail, "Zu viele laufende Jobs. Bitte warten bis ein Job abgeschlossen ist."));
        }
        if (jobData.status === "success") {
          failedRender.clear();
          if (failedRenderIsAuto) setAutoState("done");
          await processRenderResultFromJob(jobData);
          return;
        }
        // Job is running — fall through to polling below
      } else if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Retry fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, "Retry fehlgeschlagen"));
      }

      setRenderProgressLabel("In der Warteschlange…");
      currentJobUuidRef.current = uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid, isAuto: failedRenderIsAuto }));
      notifyJobsChanged();
      dispatch({ type: "SET_STEP", step: "rendering" });
      dispatch({ type: "SET_ERROR_MESSAGE", message: "" });
      dispatch({ type: "SET_LOADING", loading: true });
      if (failedRenderIsAuto) { setAutoState("processing"); setAutoError(""); }
      const signal = newSignal();
      const jobResult = await pollJob(
        uuid, onRenderProgress, 3000, signal,
        () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000,
      );
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.clear();
      notifyJobsChanged();
      if (failedRenderIsAuto) setAutoState("done");
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const msg = err instanceof Error ? err.message : "Retry fehlgeschlagen";
      failedRender.mark(uuid, failedRenderIsAuto);
      if (failedRenderIsAuto) { setAutoState("error"); setAutoError(msg); }
      goError(msg);
    }
  }, [failedRenderJobUuid, failedRenderIsAuto, file, onRenderProgress, processRenderResultFromJob, newSignal, goError]);

  // ── Resume active render job after page refresh ──
  useEffect(() => {
    const saved = sessionStorage.getItem(RENDER_SESSION_KEY);
    if (!saved) return;
    let parsed: { uuid: string; isAuto: boolean };
    try { parsed = JSON.parse(saved); } catch { sessionStorage.removeItem(RENDER_SESSION_KEY); return; }
    const { uuid, isAuto } = parsed;

    fetch(`/api/jobs/${uuid}`, { credentials: "include" })
      .then(r => r.json())
      .then(job => {
        if (job.status === "success") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          return; // job already done, show upload form — result in Jobs Panel
        }
        if (job.status === "failed") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          failedRender.mark(uuid, isAuto);
          if (isAuto) { setAutoError(job.error || "Job fehlgeschlagen"); setAutoState("error"); }
          else { goError(job.error || "Job fehlgeschlagen"); }
          return;
        }
        // Still running/pending — resume polling
        currentJobUuidRef.current = uuid;
        failedRender.setIsAuto(isAuto);
        setRenderProgressLabel("Verbindung wiederhergestellt…");
        dispatch({ type: "SET_STEP", step: "rendering" });
        dispatch({ type: "SET_LOADING", loading: true });
        if (isAuto) setAutoState("processing");
        const ctrl = new AbortController();
        abortControllerRef.current = ctrl;
        pollJob(uuid, onRenderProgress, 3000, ctrl.signal,
          () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000)
          .then(jobResult => {
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            currentJobUuidRef.current = null;
            failedRender.clear();
            notifyJobsChanged();
            if (isAuto) setAutoState("done");
            processRenderResultFromJob(jobResult);
          })
          .catch(err => {
            if (err instanceof Error && err.name === "AbortError") return;
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            failedRender.mark(uuid, isAuto);
            if (isAuto) { setAutoState("error"); }
            goError(err.message);
          });
      })
      .catch(() => sessionStorage.removeItem(RENDER_SESSION_KEY));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownload = () => {
    if (!downloadBlob) return;
    const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
    triggerBlobDownload(downloadBlob, `${stem}_screencast_EN.mp4`);
  };

  const openRegen = regen.open;
  const closeRegen = regen.close;

  const applyRegen = (index: number, mode: RegenApplyMode, content: string) => {
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
  };

  // ── Back to script review (from tts-settings) ──
  const handleBackToScripts = () => {
    if (step === "rendering") return;
    dispatch({ type: "SET_STEP", step: "script-review" });
  };

  // ── Track max reached step ──
  useEffect(() => {
    dispatch({ type: "ADVANCE_REACHED", idx: stepToIndex(step) });
  }, [step]);

  const isAutoMode =
    mode === "auto" && step === "upload" && autoState !== "idle";
  const showStepIndicator = step !== "upload" && step !== "error";

  const totalWords = slides.reduce(
    (sum, s) => sum + wordCount(s.script),
    0,
  );
  const totalDuration = estimateDuration(totalWords);
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;


  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        {/* Step indicator */}
        {showStepIndicator && (
          <>
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              sourceLang={sourceLang}
              onStepClick={handleStepClick}
            />
            <div className="flex justify-between mb-6">
              <button
                onClick={() => resetAll(step !== "done")}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
              <button
                onClick={() => resetAll(step !== "done")}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-red-400 hover:text-red-600 border border-red-200 hover:border-red-400 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Screencast abbrechen
              </button>
            </div>
          </>
        )}

        {/* ── Resume loading ── */}
        {resumeLoading && (
          <section className="animate-[fadeIn_0.2s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700">Screencast wird wiederhergestellt…</p>
          </section>
        )}

        {/* ── Step: Upload ── */}
        {!resumeLoading && step === "upload" && (
          <UploadStep
            showDemoLink={showDemoLink}
            hasActiveJob={hasActiveJob}
            file={file}
            fileError={fileError}
            dragOver={dragOver}
            autoState={autoState}
            mode={mode}
            isAdmin={isAdmin}
            fastMode={fastMode}
            sourceLang={sourceLang}
            targetLang={targetLang}
            languages={languages}
            glossaryIds={glossaryIds}
            isAutoMode={isAutoMode}
            autoDownloadName={autoDownloadName}
            autoError={autoError}
            renderProgressLabel={renderProgressLabel}
            failedRenderJobUuid={failedRenderJobUuid}
            audioId={audioId}
            fileRef={fileRef}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onFileSelect={handleFileSelect}
            onSourceLangChange={setSourceLang}
            onTargetLangChange={setTargetLang}
            onGlossaryIdsChange={setGlossaryIds}
            onModeChange={setMode}
            onFastModeChange={setFastMode}
            onUploadNext={handleUploadNext}
            onAutoDownload={handleAutoDownload}
            onReset={resetAll}
            onRetryRender={failedRenderJobUuid ? handleRetryRender : undefined}
            onZipDownload={handleAutoZipDownload}
          />
        )}

        {/* ── Step: Translating (loading) ── */}
        {!resumeLoading && step === "translating" && (
          <TranslatingStep
            sourceLang={sourceLang}
            targetLang={targetLang}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {});
                notifyJobsChanged();
              }
              dispatch({ type: "SET_STEP", step: "upload" });
              dispatch({ type: "SET_LOADING", loading: false });
            }}
          />
        )}

        {/* ── Step: User Prompt ── */}
        {!resumeLoading && step === "user-prompt" && (
          <UserPromptStep
            scriptInputMode={scriptInputMode}
            importedScripts={importedScripts}
            importError={importError}
            jsonDragOver={jsonDragOver}
            jsonFileRef={jsonFileRef}
            loading={loading}
            onScriptInputModeChange={setScriptInputMode}
            onResetImport={resetImport}
            onJsonDragOverChange={setJsonDragOver}
            onJsonImport={handleJsonImport}
            onNext={() => {
              if (scriptInputMode === "manual") {
                dispatch({ type: "CLEAR_SCRIPTS" });
                dispatch({ type: "SET_STEP", step: "script-review" });
              } else if (scriptInputMode === "import") {
                if (!importedScripts) {
                  setImportError("Bitte zuerst eine JSON-Datei auswählen.");
                  return;
                }
                dispatch({ type: "IMPORT_SCRIPTS", scripts: importedScripts });
                dispatch({ type: "SET_STEP", step: "script-review" });
              } else {
                handleAcceptTranslation();
              }
            }}
          />
        )}

        {/* ── Step: Translation Review ── */}
        {!resumeLoading && step === "translation-review" && (
          <TranslationReviewStep
            slides={slides}
            fastMode={fastMode}
            loading={loading}
            correctedFileName={correctedFileName}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onDownloadTranslatedPptx={handleDownloadTranslatedPptx}
            onUploadCorrectedPptx={handleUploadCorrectedPptx}
            onAcceptAndNext={() => {
              dispatch({ type: "ADVANCE_REACHED", idx: 3 });
              dispatch({ type: "SET_STEP", step: "user-prompt" });
            }}
          />
        )}

        {/* ── Step: Generating Scripts (loading) ── */}
        {!resumeLoading && step === "generating-scripts" && (
          <GeneratingScriptsStep
            slideCount={slides.length}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
                notifyJobsChanged();
              }
              dispatch({ type: "SET_STEP", step: "translation-review" });
              dispatch({ type: "SET_LOADING", loading: false });
            }}
          />
        )}

        {/* ── Step: Script Review ── */}
        {!resumeLoading && step === "script-review" && (
          <ScriptReviewStep
            slides={slides}
            openAccordion={openAccordion}
            editingSlide={editingSlide}
            editBuffer={editBuffer}
            fastMode={fastMode}
            regenAnchorSlide={regenAnchorSlide}
            regenAnchorText={regenAnchorText}
            onEditBufferChange={setEditBuffer}
            onLightboxOpen={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
            onAccordionToggle={toggleAccordion}
            onRegenAnchor={regen.setAnchor}
            onOpenRegen={openRegen}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSaveEdit={saveEdit}
            onAcceptScripts={handleAcceptScripts}
          />
        )}

        {/* ── Step: TTS Settings ── */}
        {!resumeLoading && step === "tts-settings" && (
          <TtsSettingsStep
            providersLoaded={providersLoaded}
            elevenlabsEnabled={elevenlabsEnabled}
            fishSpeechEnabled={fishSpeechEnabled}
            kokoroEnabled={kokoroEnabled}
            mylabEnabled={mylabEnabled}
            thorstenEnabled={thorstenEnabled}
            ttsProvider={ttsProvider}
            voices={voices}
            kokoroVoices={kokoroVoices}
            mylabVoices={mylabVoices}
            thorstenVoices={thorstenVoices}
            voiceId={voiceId}
            speed={speed}
            slidePause={slidePause}
            dpi={dpi}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={ttsSettingsError}
            onTtsProviderChange={setTtsProvider}
            onVoiceIdChange={setVoiceId}
            onSpeedChange={setSpeed}
            onSlidePauseChange={setSlidePause}
            onDpiChange={setDpi}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
          />
        )}

        {/* ── Step: Rendering (loading) ── */}
        {!resumeLoading && step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderProgressLabel}
            onCancel={async () => {
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
            }}
          />
        )}

        {/* ── Step: Done ── */}
        {!resumeLoading && step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId={audioId}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll(false)}
          />
        )}

        {/* ── Error state ── */}
        {!resumeLoading && step === "error" && (
          <ErrorStep
            errorMessage={errorMessage}
            failedRenderJobUuid={failedRenderJobUuid}
            onRetry={handleRetryRender}
            onReset={() => resetAll()}
          />
        )}
        {!fastMode && lightboxIndex !== null && (
          <Lightbox
            index={lightboxIndex}
            slides={slides}
            onClose={() => dispatch({ type: "SET_LIGHTBOX", index: null })}
            onIndexChange={(idx) => dispatch({ type: "SET_LIGHTBOX", index: idx })}
          />
        )}


        {regeneratingSlide !== null && slides[regeneratingSlide] && (
          <RegenChatModal
            slideIndex={regeneratingSlide}
            slideExtractedText={slides[regeneratingSlide].extractedText}
            currentScript={slides[regeneratingSlide].script || ""}
            anchorText={regenAnchorText}
            targetLang={targetLang}
            onApply={(mode, content) => applyRegen(regeneratingSlide, mode, content)}
            onClose={closeRegen}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastPage() {
  return (
    <Suspense>
      <ScreencastPageInner />
    </Suspense>
  );
}
