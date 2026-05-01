"use client";

import { useCallback, useEffect, type Dispatch, type MutableRefObject } from "react";
import { downloadJobAsBlob, parseDetail, pollJob, type JobStatus } from "@/lib/api";
import { notifyJobsChanged } from "@/lib/jobs-events";
import type { SlideData } from "@/types";
import type { ElevenLabsVoice, KokoroVoice, TtsProvider } from "@/hooks/useVoices";
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
  speed: number;
  slidePause: number;
  dpi: number;
  voiceId: string;
  ttsProvider: TtsProvider;
  kokoroVoices: KokoroVoice[];
  voices: ElevenLabsVoice[];

  // Sub-hooks
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
    speed,
    slidePause,
    dpi,
    voiceId,
    ttsProvider,
    kokoroVoices,
    voices,
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
        resultStem: meta.result_stem as string | undefined,
      });
      dispatch({ type: "SET_LOADING", loading: false });
      dispatch({ type: "SET_STEP", step: "done" });
    },
    [dispatch, renderResult],
  );

  // ── Render from accepted scripts ──
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
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid }));
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
      failedRender.mark(currentJobUuidRef.current);
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
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid }));
      notifyJobsChanged();
      dispatch({ type: "SET_STEP", step: "rendering" });
      dispatch({ type: "SET_ERROR_MESSAGE", message: "" });
      dispatch({ type: "SET_LOADING", loading: true });
      const signal = newSignal();
      const jobResult = await pollJob(
        uuid, onRenderProgress, 3000, signal,
        () => setRenderProgressLabel(STUCK_LABEL), 60_000,
      );
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      failedRender.clear();
      notifyJobsChanged();
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const msg = err instanceof Error ? err.message : "Retry fehlgeschlagen";
      failedRender.mark(uuid);
      goError(msg);
    }
  }, [
    failedRender,
    newSignal, onRenderProgress, setRenderProgressLabel,
    processRenderResultFromJob, goError, dispatch, currentJobUuidRef,
  ]);

  // ── Resume after page refresh (sessionStorage-backed) ──
  useEffect(() => {
    const saved = sessionStorage.getItem(RENDER_SESSION_KEY);
    if (!saved) return;
    let parsed: { uuid: string };
    try {
      parsed = JSON.parse(saved);
    } catch {
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      return;
    }
    const { uuid } = parsed;

    fetch(`/api/jobs/${uuid}`, { credentials: "include" })
      .then((r) => r.json())
      .then((job) => {
        if (job.status === "success") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          return;
        }
        if (job.status === "failed") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          failedRender.mark(uuid);
          goError(job.error || "Job fehlgeschlagen");
          return;
        }
        currentJobUuidRef.current = uuid;
        setRenderProgressLabel("Verbindung wiederhergestellt…");
        dispatch({ type: "SET_STEP", step: "rendering" });
        dispatch({ type: "SET_LOADING", loading: true });
        const ctrl = new AbortController();
        abortControllerRef.current = ctrl;
        pollJob(uuid, onRenderProgress, 3000, ctrl.signal,
          () => setRenderProgressLabel(STUCK_LABEL), 60_000)
          .then((jobResult) => {
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            currentJobUuidRef.current = null;
            failedRender.clear();
            notifyJobsChanged();
            processRenderResultFromJob(jobResult);
          })
          .catch((err) => {
            if (err instanceof Error && err.name === "AbortError") return;
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            failedRender.mark(uuid);
            goError(err.message);
          });
      })
      .catch(() => sessionStorage.removeItem(RENDER_SESSION_KEY));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    onRenderProgress,
    handleStartRender,
    handleRetryRender,
    newSignal,
  };
}
