"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** One audio file at a time, keepCache holds what was generated until unmount. */
export function useVoicePlayer({ keepCache = false }: { keepCache?: boolean } = {}) {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  // The id of the last failure, old callers do not read the field.
  const [failedId, setFailedId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const cacheRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const cache = cacheRef.current;
    return () => {
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      cache.forEach((url) => URL.revokeObjectURL(url));
      cache.clear();
    };
  }, []);

  const stopCurrent = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    // Release here too, because stopping midway fires no event.
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const playUrl = useCallback((voiceId: string, url: string) => {
    stopCurrent();
    if (playingId === voiceId) { setPlayingId(null); return; }
    const audio = new Audio(url);
    audioRef.current = audio;
    setPlayingId(voiceId);
    audio.play().catch(() => {});
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => setPlayingId(null);
  }, [playingId, stopCurrent]);

  const start = useCallback((key: string, url: string, cached: boolean) => {
    const audio = new Audio(url);
    audioRef.current = audio;
    if (!cached) objectUrlRef.current = url;
    setLoadingId(null);
    setPlayingId(key);
    audio.play().catch(() => {});
    const done = () => {
      setPlayingId(null);
      if (!cached) {
        URL.revokeObjectURL(url);
        objectUrlRef.current = null;
      }
    };
    audio.onended = done;
    audio.onerror = done;
  }, []);

  const playFromApi = useCallback(async (voiceId: string, endpoint: string, actualVoiceId?: string) => {
    stopCurrent();
    // A new attempt clears every old failure.
    setFailedId(null);
    if (playingId === voiceId || loadingId === voiceId) {
      setPlayingId(null);
      setLoadingId(null);
      return;
    }

    const cached = keepCache ? cacheRef.current.get(voiceId) : undefined;
    if (cached) { start(voiceId, cached, true); return; }

    setLoadingId(voiceId);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_id: actualVoiceId ?? voiceId }),
        signal: controller.signal,
      });
      if (!res.ok) { setLoadingId(null); setFailedId(voiceId); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (keepCache) cacheRef.current.set(voiceId, url);
      start(voiceId, url, keepCache);
    } catch (e) {
      // A cancellation by the user is not an error.
      if ((e as Error).name !== "AbortError") { setLoadingId(null); setFailedId(voiceId); }
    }
  }, [playingId, loadingId, stopCurrent, keepCache, start]);

  return { playingId, loadingId, failedId, playUrl, playFromApi };
}
