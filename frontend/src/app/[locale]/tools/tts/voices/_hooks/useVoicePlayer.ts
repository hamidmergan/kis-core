"use client";

import { useCallback, useEffect, useRef, useState } from "react";


export function useVoicePlayer() {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      audioRef.current?.pause();
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
  }, []);

  const stopCurrent = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    // Revoke here too: onended/onerror only fire when playback finishes on its
    // own, not when the user stops or switches voice mid-play.
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

  const playFromApi = useCallback(async (voiceId: string, endpoint: string, actualVoiceId?: string) => {
    stopCurrent();
    if (playingId === voiceId || loadingId === voiceId) {
      setPlayingId(null);
      setLoadingId(null);
      return;
    }

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
      if (!res.ok) { setLoadingId(null); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      setLoadingId(null);
      setPlayingId(voiceId);
      audio.play().catch(() => {});
      audio.onended = () => { setPlayingId(null); URL.revokeObjectURL(url); objectUrlRef.current = null; };
      audio.onerror = () => { setPlayingId(null); URL.revokeObjectURL(url); objectUrlRef.current = null; };
    } catch (e) {
      if ((e as Error).name !== "AbortError") setLoadingId(null);
    }
  }, [playingId, loadingId, stopCurrent]);

  return { playingId, loadingId, playUrl, playFromApi };
}
