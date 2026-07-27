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
  /** Folien, an denen die Übersetzung nichts geändert hat (0-basiert). */
  unchanged_slides?: number[];
}

interface GenerateScriptsResponse {
  scripts: string[];
}

export interface TranslateFlowMessages {
  unknownError: string;
  errorWithCode: (code: number) => string;
  uploadError: string;
  downloadFailed: string;
  jobInOtherTab: string;
  jobDeleted: string;
}

interface UseScreencastTranslateFlowOptions {
  translateJobUuid: string;
  slides: SlideData[];
  dispatch: Dispatch<FlowAction>;

  // Upload/Translate config
  file: File | null;
  skipTranslation: boolean;
  targetLang: string;
  glossaryIds: string[];
  translationProviderId: number | null;
  mergeToApiJson: (ids: string[]) => string | null;

  // Callbacks from other hooks
  checkBeforeSubmit: () => Promise<boolean>;
  checkJobStillValid: (uuid: string) => Promise<"ok" | "running" | "deleted">;
  checkJobFolder: () => Promise<boolean>;
  goError: (msg: string) => void;
  newSignal: () => AbortSignal;

  // Translated messages from the component
  messages: TranslateFlowMessages;

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
    skipTranslation,
    targetLang,
    glossaryIds,
    translationProviderId,
    mergeToApiJson,
    checkBeforeSubmit,
    checkJobStillValid,
    checkJobFolder,
    goError,
    newSignal,
    messages,
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

    // ── Skip-translation path: skip DeepL, upload as-is, go directly to user-prompt ──
    if (skipTranslation) {
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
          const error = await response.json().catch(() => ({ detail: messages.unknownError }));
          throw new Error(parseDetail(error.detail, messages.errorWithCode(response.status)));
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
        goError(err instanceof Error ? err.message : messages.unknownError);
      }
      return;
    }

    // ── Different-language path: translate via DeepL ──
    try {
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
      if (translationProviderId != null) formData.append("provider_id", String(translationProviderId));
      // Source language is always auto-detected (empty source_lang).
      formData.append("source_lang", "");
      formData.append("target_lang", targetLang);

      const uploadRes = await fetch("/api/screencast/translate", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const error = await uploadRes.json().catch(() => ({ detail: messages.unknownError }));
        throw new Error(parseDetail(error.detail, messages.errorWithCode(uploadRes.status)));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      dispatch({ type: "SET_JOB_UUID", uuid: job_uuid });
      notifyJobsChanged();

      const jobResult = await pollJob(job_uuid, undefined, 3000, signal);
      currentJobUuidRef.current = null;
      const data = (jobResult.result ?? {}) as unknown as TranslateResponse;

      const unchanged = new Set(data.unchanged_slides ?? []);
      dispatch({
        type: "SET_SLIDES",
        slides: (data.slide_texts || []).map((text, i) => ({
          index: i,
          imageBase64: (data.slide_images || [])[i] || "",
          extractedText: text,
          script: "",
          unchanged: unchanged.has(i),
        })),
      });
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "translation-review" });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : messages.unknownError);
    }
  }, [
    file, skipTranslation, targetLang, glossaryIds, translationProviderId, mergeToApiJson,
    checkBeforeSubmit, goError,
    newSignal, dispatch, currentJobUuidRef,
  ]);

  // ── Download translated PPTX ──
  // Gibt zurück, ob es geklappt hat. Vorher landete ein Fehlschlag nur in der
  // Konsole und der Nutzer stand vor einem Knopf, der scheinbar nichts tut.
  const handleDownloadTranslatedPptx = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return false;
    try {
      const res = await fetch(`/api/screencast/pptx/${translateJobUuid}`, { credentials: "include" });
      if (!res.ok) throw new Error(messages.downloadFailed);
      const blob = await res.blob();
      const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
      triggerBlobDownload(blob, `${stem}.pptx`);
      return true;
    } catch (err) {
      console.error("PPTX download failed:", err);
      return false;
    }
  }, [translateJobUuid, file, messages]);

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
          const err = await response.json().catch(() => ({ detail: messages.uploadError }));
          throw new Error(parseDetail(err.detail, messages.errorWithCode(response.status)));
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
        goError(err instanceof Error ? err.message : messages.unknownError);
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
        goError(messages.jobInOtherTab);
        return;
      }
      if (validity === "deleted") {
        goError(messages.jobDeleted);
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
          source_lang: "",
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
      goError(err instanceof Error ? err.message : messages.unknownError);
    }
  }, [
    slides, glossaryIds, mergeToApiJson, targetLang,
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
