"use client";

import { useEffect, useRef, useState } from "react";
import type { ProviderWithVoices } from "@/hooks/useVoices";
import { computeVoiceLabel } from "../_utils";
import type { GespeicherteEinstellungen } from "./useSchritt6Stand";

const SPEICHERN_NACH_MS = 600;

interface Optionen {
  jobUuid: string;
  /** Step 6 is open and its stored state has arrived, only then a change is saved. */
  speichern: boolean;
  gespeichert: GespeicherteEinstellungen | null;
  providers: ProviderWithVoices[];
  defaultProviderId: number | null;
  defaultVoiceId: string;
  targetLang: string;
  setTargetLang: (id: string) => void;
  speed: number;
  imScreencast: number[];
  neuVertonen: number[];
}

/** The voice and video settings of step 6: preset, restored from the job and saved on every change. */
export function useVertonungsEinstellungen(o: Optionen) {
  const { jobUuid, speichern, gespeichert, providers, defaultProviderId, defaultVoiceId,
          targetLang, setTargetLang, speed, imScreencast, neuVertonen } = o;
  const [voiceId, setVoiceId] = useState("");
  const [providerId, setProviderId] = useState<number>(0);
  const [slidePause, setSlidePause] = useState<number>(1.0);
  const [dpi, setDpi] = useState(96);
  const [subtitles, setSubtitles] = useState(false);

  useEffect(() => {
    if (defaultProviderId != null && providerId === 0) setProviderId(defaultProviderId);
  }, [defaultProviderId, providerId]);
  useEffect(() => {
    if (defaultVoiceId && !voiceId) setVoiceId(defaultVoiceId);
  }, [defaultVoiceId, voiceId]);

  // Whoever comes back tomorrow finds their state instead of the default.
  const eingestelltRef = useRef(false);
  useEffect(() => {
    const e = gespeichert;
    if (!e || eingestelltRef.current) return;
    eingestelltRef.current = true;
    if (e.provider_id) setProviderId(e.provider_id);
    if (e.voice_id) setVoiceId(e.voice_id);
    if (e.target_lang) setTargetLang(e.target_lang);
    setSlidePause(e.slide_pause);
    setDpi(e.dpi);
    setSubtitles(e.subtitles);
  }, [gespeichert, setTargetLang]);

  // Saved on change, not only at render time.
  useEffect(() => {
    if (!jobUuid || !speichern) return;
    const zeit = setTimeout(() => {
      fetch(`/api/screencast/${jobUuid}/einstellungen`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider_id: providerId,
          voice_id: voiceId,
          voice_label: computeVoiceLabel(providerId, voiceId, providers),
          target_lang: targetLang,
          speed,
          slide_pause: slidePause,
          dpi,
          subtitles,
          video_folien: imScreencast,
          neu_vertonen: neuVertonen,
        }),
        credentials: "include",
      }).catch(() => {});
    }, SPEICHERN_NACH_MS);
    return () => clearTimeout(zeit);
  }, [
    jobUuid, speichern, providerId, voiceId, providers, targetLang,
    speed, slidePause, dpi, subtitles, imScreencast, neuVertonen,
  ]);

  return { voiceId, setVoiceId, providerId, setProviderId, slidePause, setSlidePause, dpi, subtitles, setSubtitles };
}
