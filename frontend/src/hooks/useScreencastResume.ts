"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { ScreencastStep, SlideData } from "@/types";

export interface ScreencastResumePayload {
  jobUuid: string;
  slides: SlideData[];
  step: ScreencastStep;
  stepIdx: number;
}

interface ResumeResponse {
  tool: string;
  step: string;
  slide_texts: string[];
  scripts: string[];
  slide_images: string[];
  unchanged_slides?: number[];
  original_filename: string;
  user_prompt: string;
}

function mapStep(step: string): { step: ScreencastStep; idx: number } {
  if (step === "tts-settings") return { step: "tts-settings", idx: 5 };
  if (step === "translation-review") return { step: "translation-review", idx: 2 };
  if (step === "user-prompt") return { step: "user-prompt", idx: 3 };
  if (step === "rendering") return { step: "rendering", idx: 6 };
  if (step === "done") return { step: "done", idx: 7 };
  return { step: "script-review", idx: 4 };
}

export function useScreencastResume(onResume: (payload: ScreencastResumePayload) => void) {
  const searchParams = useSearchParams();
  const [resumeLoading, setResumeLoading] = useState(false);
  const [resumeFailed, setResumeFailed] = useState(false);

  useEffect(() => {
    const resumeUuid = searchParams.get("resume");
    if (!resumeUuid) return;
    setResumeLoading(true);
    setResumeFailed(false);
    fetch(`/api/screencast/resume/${resumeUuid}`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json() as Promise<ResumeResponse>;
      })
      .then((data) => {
        const imgs = data.slide_images ?? [];
        const texts = data.slide_texts ?? [];
        const scripts = data.scripts ?? [];
        const unchanged = new Set(data.unchanged_slides ?? []);
        const slideCount = Math.max(texts.length, scripts.length, imgs.length);
        const slides: SlideData[] = slideCount === 0
          ? []
          : Array.from({ length: slideCount }, (_, i) => ({
              index: i,
              imageBase64: imgs[i] ?? "",
              extractedText: texts[i] ?? scripts[i] ?? "",
              // Without a script the field stays empty instead of reading the slide text aloud.
              script: scripts[i] ?? "",
              unchanged: unchanged.has(i),
            }));
        const { step, idx } = mapStep(data.step);
        onResume({ jobUuid: resumeUuid, slides, step, stepIdx: idx });
      })
      .catch(() => {
        // Job expired, deleted or still running, the page says so now.
        setResumeFailed(true);
      })
      .finally(() => setResumeLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { resumeLoading, resumeFailed };
}

export function useSlideImageBackfill(jobUuid: string, slides: SlideData[], onImages: (images: string[]) => void) {
  const hasAnyImage = slides.some((s) => s.imageBase64);
  useEffect(() => {
    if (!jobUuid || !slides.length || hasAnyImage) return;
    fetch(`/api/screencast/${jobUuid}/images`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!data?.slide_images?.length) return;
        onImages(data.slide_images);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobUuid, slides.length, hasAnyImage]);
}

export function useActiveJobCheck(tool: string) {
  const [hasActiveJob, setHasActiveJob] = useState<boolean | null>(null);
  useEffect(() => {
    fetch(`/api/jobs/check/${tool}`, { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setHasActiveJob(!!data.has_active_job))
      .catch(() => setHasActiveJob(false));
  }, [tool]);
  return [hasActiveJob, setHasActiveJob] as const;
}
