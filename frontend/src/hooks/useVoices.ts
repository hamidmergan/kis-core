"use client";

import { useEffect, useState } from "react";
import { preselectedVoice } from "./_voiceDefault";

export interface Voice {
  voice_id: string;
  name: string;
  language: string;
  description?: string;
}

export interface ProviderWithVoices {
  id: number;
  name: string;
  voices: Voice[];
}

export interface UseVoicesResult {
  loaded: boolean;
  providers: ProviderWithVoices[];
  defaultProviderId: number | null;
  defaultVoiceId: string;
}

export function useVoices(): UseVoicesResult {
  const [loaded, setLoaded] = useState(false);
  const [providers, setProviders] = useState<ProviderWithVoices[]>([]);
  const [defaultProviderId, setDefaultProviderId] = useState<number | null>(null);
  const [defaultVoiceId, setDefaultVoiceId] = useState("");

  useEffect(() => {
    let cancelled = false;

    fetch("/api/tts/providers-with-voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const list: ProviderWithVoices[] = data.providers ?? [];
        setProviders(list);
        const vorauswahl = preselectedVoice(list, data.default);
        if (vorauswahl) {
          setDefaultProviderId(vorauswahl.providerId);
          if (vorauswahl.voiceId) setDefaultVoiceId(vorauswahl.voiceId);
        }
      })
      .catch(() => {
        // Provider fetch failed — leave empty, UI will show no-provider state
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { loaded, providers, defaultProviderId, defaultVoiceId };
}
