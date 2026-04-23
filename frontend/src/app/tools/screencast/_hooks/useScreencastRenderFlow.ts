"use client";

import { useCallback, useEffect, type Dispatch, type MutableRefObject } from "react";
import { downloadJobAsBlob, parseDetail, pollJob, type JobStatus } from "@/lib/api";
import { notifyJobsChanged } from "@/lib/jobs-events";
import type { SlideData } from "@/types";
import type { ElevenLabsVoice, KokoroVoice, TtsProvider } from "@/hooks/useVoices";
import type { useAutoModeFlow } from "@/hooks/useAutoModeFlow";
import type { useFailedRender } from "@/hooks/useFailedRender";
import type { useRenderResult } from "@/hooks/useRenderResult";
import { computeVoiceLabel, renderProgressLabel as renderProgressLabelFn } from "../_utils";
import type { FlowAction } from "../_reducer";

const RENDER_SESSION_KEY = "kis_screencast_active_render";
const STUCK_LABEL = "Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…";

interface UseScreencastRenderFlowOptions {
  // Flow state
  translateJobUuid: string;
  slides: SlideData[];
  dispatch: Dispatch<FlowAction>;

  // Render config
  file: File | null;
  speed: number;
  slidePause: number;
  dpi: number;
  voiceId: string;
  ttsProvider: TtsProvider;
  kokoroVoices: KokoroVoice[];
  voices: ElevenLabsVoice[];

  // Translate config (auto-flow)
  sourceLang: string;
  targetLang: string;
  glossaryIds: string[];
  mergeToApiJson: (ids: string[]) => string | null;

  // Sub-hooks
  auto: ReturnType<typeof useAutoModeFlow>;
  failedRender: ReturnType<typeof useFailedRender>;
  renderResult: ReturnType<typeof useRenderResult>;

  // External callbacks
  checkBeforeSubmit: () => Promise<boolean>;
  goError: (msg: string) => void;
  setTtsSettingsError: (msg: string) => void;
  setRenderProgressLabel: (label: string) => void;

  // Refs
  abortControllerRef: MutableRefObject<AbortController | null>;
  currentJobUuidRef: MutableRefObject<string | null>;
}

export function useScreencastRenderFlow(opts: UseScreencastRenderFlowOptions) {
  const {
    translateJobUuid,
    slides,
    dispatch,
    file,
    speed,
    slidePause,
    dpi,
    voiceId,
    ttsProvider,
    kokoroVoices,
    voices,
    sourceLang,
    targetLang,
    glossaryIds,
    mergeToApiJson,
    auto,
    failedRender,
    renderResult,
    checkBeforeSubmit,
    goError,
    setTtsSettingsError,
    setRenderProgressLabel,
    abortControllerRef,
    currentJobUuidRef,
  } = opts;

  const newSignal = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current.signal;
  }, [abortControllerRef]);

  const onRenderProgress = useCallback(
    (status: JobStatus) => {
      setRenderProgressLabel(renderProgressLabelFn(status));
    },
    [setRenderProgressLabel],
  );

  const processRenderResultFromJob = useCallback(
    async (jobResult: JobStatus) => {
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");
      const meta = jobResult.meta ?? {};
      renderResult.apply(blob, {
        audioId: meta.audio_id as string | undefined,
        audioCount: meta.audio_count as number | undefined,
      });
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "done" });
    },
    [dispatch, renderResult],
  );

  // ── Auto mode: end-to-end PPTX → MP4 ──
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

      const uploadRes = await fetch("/api/screencast", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid, isAuto: true }));
      notifyJobsChanged();

      const jobResult = await pollJob(
        job_uuid,
        onRenderProgress,
        5000,
        signal,
        () => setRenderProgressLabel(STUCK_LABEL),
        60_000,
      );
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");
      const meta = jobResult.meta ?? {};
      renderResult.apply(blob, {
        audioId: meta.audio_id as string | undefined,
        audioCount: meta.audio_count as number | undefined,
      });
      const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
      auto.succeed(blob, `${stem}_screencast.mp4`);
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "upload" });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.mark(currentJobUuidRef.current, true);
      auto.setState("error");
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [
    file, speed, dpi, voiceId, ttsProvider, kokoroVoices, voices,
    sourceLang, targetLang, glossaryIds, mergeToApiJson,
    newSignal, onRenderProgress, setRenderProgressLabel,
    auto, failedRender, renderResult,
    checkBeforeSubmit, goError, dispatch, currentJobUuidRef,
  ]);

  // ── Manual mode: render from accepted scripts ──
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

      if (signal.aborted) {
        await fetch(`/api/jobs/${job_uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
        currentJobUuidRef.current = null;
        return;
      }

      const jobResult = await pollJob(
        job_uuid,
        onRenderProgress,
        5000,
        signal,
        () => setRenderProgressLabel(STUCK_LABEL),
        60_000,
      );
      currentJobUuidRef.current = null;
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.mark(currentJobUuidRef.current, false);
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [
    slides, translateJobUuid, voiceId, ttsProvider, kokoroVoices, voices,
    speed, slidePause, dpi,
    newSignal, onRenderProgress, setRenderProgressLabel, setTtsSettingsError,
    failedRender, processRenderResultFromJob,
    checkBeforeSubmit, goError, dispatch, currentJobUuidRef,
  ]);

  // ── Retry a failed render ──
  const handleRetryRender = useCallback(async () => {
    const uuid = failedRender.jobUuid;
    const isAuto = failedRender.isAuto;
    if (!uuid) return;
    try {
      const res = await fetch(`/api/jobs/${uuid}/retry`, { method: "POST", credentials: "include" });

      if (res.status === 409) {
        const jobRes = await fetch(`/api/jobs/${uuid}`, { credentials: "include" });
        const jobData = await jobRes.json();
        if (jobData.status === "failed") {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseDetail(err.detail, "Zu viele laufende Jobs. Bitte warten bis ein Job abgeschlossen ist."));
        }
        if (jobData.status === "success") {
          failedRender.clear();
          if (isAuto) auto.setState("done");
          await processRenderResultFromJob(jobData);
          return;
        }
        // Job is running — fall through to polling
      } else if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Retry fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, "Retry fehlgeschlagen"));
      }

      setRenderProgressLabel("In der Warteschlange…");
      currentJobUuidRef.current = uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid, isAuto }));
      notifyJobsChanged();
      dispatch({ type: "SET_STEP", step: "rendering" });
      dispatch({ type: "SET_ERROR_MESSAGE", message: "" });
      dispatch({ type: "SET_LOADING", loading: true });
      if (isAuto) { auto.setState("processing"); auto.setError(""); }
      const signal = newSignal();
      const jobResult = await pollJob(
        uuid, onRenderProgress, 3000, signal,
        () => setRenderProgressLabel(STUCK_LABEL), 60_000,
      );
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.clear();
      notifyJobsChanged();
      if (isAuto) auto.setState("done");
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const msg = err instanceof Error ? err.message : "Retry fehlgeschlagen";
      failedRender.mark(uuid, isAuto);
      if (isAuto) { auto.setState("error"); auto.setError(msg); }
      goError(msg);
    }
  }, [
    failedRender, auto,
    newSignal, onRenderProgress, setRenderProgressLabel,
    processRenderResultFromJob, goError, dispatch, currentJobUuidRef,
  ]);

  // ── Resume after page refresh (sessionStorage-backed) ──
  useEffect(() => {
    const saved = sessionStorage.getItem(RENDER_SESSION_KEY);
    if (!saved) return;
    let parsed: { uuid: string; isAuto: boolean };
    try {
      parsed = JSON.parse(saved);
    } catch {
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      return;
    }
    const { uuid, isAuto } = parsed;

    fetch(`/api/jobs/${uuid}`, { credentials: "include" })
      .then((r) => r.json())
      .then((job) => {
        if (job.status === "success") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          return;
        }
        if (job.status === "failed") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          failedRender.mark(uuid, isAuto);
          if (isAuto) {
            auto.setError(job.error || "Job fehlgeschlagen");
            auto.setState("error");
          } else {
            goError(job.error || "Job fehlgeschlagen");
          }
          return;
        }
        currentJobUuidRef.current = uuid;
        failedRender.setIsAuto(isAuto);
        setRenderProgressLabel("Verbindung wiederhergestellt…");
        dispatch({ type: "SET_STEP", step: "rendering" });
        dispatch({ type: "SET_LOADING", loading: true });
        if (isAuto) auto.setState("processing");
        const ctrl = new AbortController();
        abortControllerRef.current = ctrl;
        pollJob(uuid, onRenderProgress, 3000, ctrl.signal,
          () => setRenderProgressLabel(STUCK_LABEL), 60_000)
          .then((jobResult) => {
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            currentJobUuidRef.current = null;
            failedRender.clear();
            notifyJobsChanged();
            if (isAuto) auto.setState("done");
            processRenderResultFromJob(jobResult);
          })
          .catch((err) => {
            if (err instanceof Error && err.name === "AbortError") return;
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            failedRender.mark(uuid, isAuto);
            if (isAuto) auto.setState("error");
            goError(err.message);
          });
      })
      .catch(() => sessionStorage.removeItem(RENDER_SESSION_KEY));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    onRenderProgress,
    handleAutoSubmit,
    handleStartRender,
    handleRetryRender,
    newSignal,
  };
}
