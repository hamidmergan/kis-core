"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface KokoroVoice {
  voice_id: string;
  name: string;
  accent: string;
  gender: string;
}

export interface OpenAITtsVoice {
  voice_id: string;
  name: string;
  description: string;
  language?: string;
}

export type TtsProvider = "kokoro" | "mylab";

export interface ProviderFlags {
  kokoro: boolean;
  mylab: boolean;
}

export interface UseVoicesResult {
  loaded: boolean;
  providers: ProviderFlags;
  defaultProvider: TtsProvider | null;
  defaultVoiceId: string;
  kokoro: KokoroVoice[];
  mylab: OpenAITtsVoice[];
}

const EMPTY_FLAGS: ProviderFlags = {
  kokoro: false,
  mylab: false,
};

const PRIORITY: TtsProvider[] = ["kokoro", "mylab"];

function pickDefaultProvider(flags: ProviderFlags): TtsProvider | null {
  for (const p of PRIORITY) {
    if (flags[p]) return p;
  }
  return null;
}

export function useVoices(): UseVoicesResult {
  const [loaded, setLoaded] = useState(false);
  const [providers, setProviders] = useState<ProviderFlags>(EMPTY_FLAGS);
  const [defaultProvider, setDefaultProvider] = useState<TtsProvider | null>(null);
  const [defaultVoiceId, setDefaultVoiceId] = useState("");
  const [kokoro, setKokoro] = useState<KokoroVoice[]>([]);
  const [mylab, setMylab] = useState<OpenAITtsVoice[]>([]);

  useEffect(() => {
    let cancelled = false;

    api
      .getJson<{
        kokoro_enabled: boolean;
        mylab_enabled: boolean;
      }>("/api/tts/providers")
      .then(async (data) => {
        if (cancelled) return;

        const flags: ProviderFlags = {
          kokoro: data.kokoro_enabled ?? false,
          mylab: data.mylab_enabled ?? false,
        };

        setProviders(flags);
        setDefaultProvider(pickDefaultProvider(flags));

        const tasks: Promise<void>[] = [];

        if (flags.kokoro) {
          tasks.push(
            api
              .getJson<{ voices: KokoroVoice[] }>("/api/kokoro/voices")
              .then((v) => {
                if (cancelled) return;
                setKokoro(v.voices ?? []);
              })
              .catch(() => {}),
          );
        }
        if (flags.mylab) {
          tasks.push(
            api
              .getJson<{ voices: OpenAITtsVoice[] }>("/api/mylab/voices")
              .then((v) => {
                if (cancelled) return;
                setMylab(v.voices ?? []);
              })
              .catch(() => {}),
          );
        }

        await Promise.allSettled(tasks);
      })
      .catch(() => {
        // Provider check failed — leave all flags empty so the UI can show
        // a no-provider state.
      })
      .finally(() => {
        if (cancelled) return;
        setLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!loaded || defaultVoiceId) return;
    if (defaultProvider === "kokoro" && kokoro.length > 0) {
      setDefaultVoiceId(kokoro[0].voice_id);
    } else if (defaultProvider === "mylab" && mylab.length > 0) {
      setDefaultVoiceId(mylab[0].voice_id);
    }
  }, [loaded, defaultProvider, defaultVoiceId, kokoro, mylab]);

  return {
    loaded,
    providers,
    defaultProvider,
    defaultVoiceId,
    kokoro,
    mylab,
  };
}
