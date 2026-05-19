"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface ElevenLabsVoice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}

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

export type TtsProvider = "elevenlabs" | "kokoro" | "mylab";

export interface ProviderFlags {
  elevenlabs: boolean;
  kokoro: boolean;
  mylab: boolean;
}

export interface UseVoicesResult {
  loaded: boolean;
  providers: ProviderFlags;
  defaultProvider: TtsProvider | null;
  defaultVoiceId: string;
  elevenlabs: ElevenLabsVoice[];
  kokoro: KokoroVoice[];
  mylab: OpenAITtsVoice[];
}

const EMPTY_FLAGS: ProviderFlags = {
  elevenlabs: false,
  kokoro: false,
  mylab: false,
};

const PRIORITY: TtsProvider[] = ["kokoro", "mylab", "elevenlabs"];

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
  const [elevenlabs, setElevenlabs] = useState<ElevenLabsVoice[]>([]);
  const [kokoro, setKokoro] = useState<KokoroVoice[]>([]);
  const [mylab, setMylab] = useState<OpenAITtsVoice[]>([]);

  useEffect(() => {
    let cancelled = false;

    api
      .getJson<{
        elevenlabs_enabled: boolean;
        kokoro_enabled: boolean;
        mylab_enabled: boolean;
      }>("/api/tts/providers")
      .then(async (data) => {
        if (cancelled) return;

        const flags: ProviderFlags = {
          elevenlabs: data.elevenlabs_enabled,
          kokoro: data.kokoro_enabled ?? false,
          mylab: data.mylab_enabled ?? false,
        };

        setProviders(flags);
        setDefaultProvider(pickDefaultProvider(flags));

        const tasks: Promise<void>[] = [];

        if (flags.elevenlabs) {
          tasks.push(
            api
              .getJson<{ voices: ElevenLabsVoice[] }>("/api/voices")
              .then((v) => {
                if (cancelled) return;
                setElevenlabs(v.voices);
              })
              .catch(() => {}),
          );
        }
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
        // a no-provider state instead of pretending ElevenLabs works.
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
    } else if (defaultProvider === "elevenlabs" && elevenlabs.length > 0) {
      setDefaultVoiceId(elevenlabs[0].voice_id);
    }
  }, [loaded, defaultProvider, defaultVoiceId, kokoro, mylab, elevenlabs]);

  return {
    loaded,
    providers,
    defaultProvider,
    defaultVoiceId,
    elevenlabs,
    kokoro,
    mylab,
  };
}
