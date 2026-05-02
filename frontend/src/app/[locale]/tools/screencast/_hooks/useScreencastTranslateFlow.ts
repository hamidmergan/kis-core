"use client";

import { useCallback, type Dispatch, type MutableRefObject } from "react";
import { api, parseDetail, pollJob } from "@/lib/api";
import { notifyJobsChanged } from "@/lib/jobs-events";
import type { SlideData } from "@/types";
import { triggerBlobDownload } from "../_utils";
import type { FlowAction } from "../_reducer";

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

interface UseScreencastTranslateFlowOptions {
  translateJobUuid: string;
  slides: SlideData[];
  dispatch: Dispatch<FlowAction>;

  // Upload/Translate config
  file: File | null;
  sourceLang: string;
  targetLang: string;
  glossaryIds: string[];
  mergeToApiJson: (ids: string[]) => string | null;

  // Callbacks from other hooks
  checkBeforeSubmit: () => Promise<boolean>;
  checkJobStillValid: (uuid: string) => Promise<"ok" | "running" | "deleted">;
  checkJobFolder: () => Promise<boolean>;
  goError: (msg: string) => void;
  newSignal: () => AbortSignal;

  // Refs
  currentJobUuidRef: MutableRefObject<string | null>;
  isGeneratingScriptsRef: MutableRefObject<boolean>;
}

export function useScreencastTranslateFlow(opts: UseScreencastTranslateFlowOptions) {
  const {
    translateJobUuid,
    slides,
    dispatch,
    file,
    sourceLang,
    targetLang,
    glossaryIds,
    mergeToApiJson,
    checkBeforeSubmit,
    checkJobStillValid,
    checkJobFolder,
    goError,
    newSignal,
    currentJobUuidRef,
    isGeneratingScriptsRef,
  } = opts;

  // ── Step: Upload → Translating ──
  const handleUploadNext = useCallback(async () => {
    if (!file) return;

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

    // ── Different-language path: translate via DeepL ──
    try {
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
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

      const jobResult = await pollJob(job_uuid, undefined, 3000, signal);
      currentJobUuidRef.current = null;
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
  }, [
    file, sourceLang, targetLang, glossaryIds, mergeToApiJson,
    checkBeforeSubmit, goError,
    newSignal, dispatch, currentJobUuidRef,
  ]);

  // ── Download translated PPTX ──
  const handleDownloadTranslatedPptx = useCallback(async () => {
    if (!translateJobUuid) return;
    try {
      const res = await fetch(`/api/screencast/pptx/${translateJobUuid}`, { credentials: "include" });
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
      triggerBlobDownload(blob, `${stem}.pptx`);
    } catch (err) {
      console.error("PPTX download failed:", err);
    }
  }, [translateJobUuid, file]);

  // ── Upload corrected PPTX (re-extract from fixed slides) ──
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
        const data: { slide_texts: string[]; slide_images: string[] } = await response.json();
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
    [translateJobUuid, goError, newSignal, dispatch],
  );

  // ── Translation review → Generate scripts ──
  const handleAcceptTranslation = useCallback(async () => {
    if (isGeneratingScriptsRef.current) return;
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
  }, [
    slides, glossaryIds, mergeToApiJson, sourceLang, targetLang,
    translateJobUuid,
    checkJobStillValid, checkJobFolder, checkBeforeSubmit, goError,
    newSignal, dispatch, currentJobUuidRef, isGeneratingScriptsRef,
  ]);

  return {
    handleUploadNext,
    handleDownloadTranslatedPptx,
    handleUploadCorrectedPptx,
    handleAcceptTranslation,
  };
}
