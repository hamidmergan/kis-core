"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Ein Ton nach dem anderen, aus einer Datei oder frisch vom Server geholt.
 *
 * ``keepCache`` behält die erzeugten Töne, solange die Ansicht steht: die
 * Lernkarte soll beim zweiten Klick auf denselben Satz sofort spielen und nicht
 * noch einmal vier Sekunden erzeugen. Gespeichert wird trotzdem nichts, beim
 * Aushängen ist alles weg. Ohne den Schalter bleibt es beim alten Verhalten,
 * jeder Ton wird nach dem Abspielen freigegeben; die Stimmenvorschau im
 * Admin-Bereich hört denselben Satz selten zweimal.
 */
export function useVoicePlayer({ keepCache = false }: { keepCache?: boolean } = {}) {
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);
  // Traegt die Kennung, bei der die Erzeugung zuletzt fehlschlug. Bestehende
  // Aufrufer (Admin-Stimmenvorschau) lesen das Feld einfach nicht und bleiben
  // unveraendert stumm; wer neu draufschaut, kann jetzt einen Hinweis zeigen.
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
    // Auch hier freigeben: onended/onerror feuern nur, wenn der Ton von selbst
    // endet, nicht wenn jemand mittendrin stoppt oder umschaltet. Was im
    // Zwischenspeicher liegt, bleibt dagegen liegen.
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
    // Ein neuer Versuch raeumt einen alten Fehlschlag weg, egal ob er derselben
    // oder einer anderen Kennung galt.
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
      // Ein Abbruch durch den Nutzer (neuer Klick, Aushaengen) ist kein Fehler
      // und bekommt keinen Hinweis.
      if ((e as Error).name !== "AbortError") { setLoadingId(null); setFailedId(voiceId); }
    }
  }, [playingId, loadingId, stopCurrent, keepCache, start]);

  return { playingId, loadingId, failedId, playUrl, playFromApi };
}
