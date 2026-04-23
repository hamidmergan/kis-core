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

export interface MylabVoice {
  voice_id: string;
  name: string;
  description: string;
}

export interface ThorstenVoice {
  voice_id: string;
  name: string;
  language: string;
}

export type TtsProvider = "elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten";

export interface ProviderFlags {
  elevenlabs: boolean;
  fish_speech: boolean;
  kokoro: boolean;
  mylab: boolean;
  thorsten: boolean;
}

export interface UseVoicesResult {
  loaded: boolean;
  providers: ProviderFlags;
  defaultProvider: TtsProvider | null;
  defaultVoiceId: string;
  elevenlabs: ElevenLabsVoice[];
  kokoro: KokoroVoice[];
  mylab: MylabVoice[];
  thorsten: ThorstenVoice[];
}

const EMPTY_FLAGS: ProviderFlags = {
  elevenlabs: false,
  fish_speech: false,
  kokoro: false,
  mylab: false,
  thorsten: false,
};

const PRIORITY: TtsProvider[] = ["kokoro", "mylab", "thorsten", "fish_speech", "elevenlabs"];

function pickDefaultProvider(flags: ProviderFlags): TtsProvider | null {
  for (const p of PRIORITY) {
    if (flags[p]) return p;
  }
  return null;
}

export interface UseVoicesOptions {
  includeThorsten?: boolean;
}

export function useVoices(options: UseVoicesOptions = {}): UseVoicesResult {
  const { includeThorsten = true } = options;

  const [loaded, setLoaded] = useState(false);
  const [providers, setProviders] = useState<ProviderFlags>(EMPTY_FLAGS);
  const [defaultProvider, setDefaultProvider] = useState<TtsProvider | null>(null);
  const [defaultVoiceId, setDefaultVoiceId] = useState("");
  const [elevenlabs, setElevenlabs] = useState<ElevenLabsVoice[]>([]);
  const [kokoro, setKokoro] = useState<KokoroVoice[]>([]);
  const [mylab, setMylab] = useState<MylabVoice[]>([]);
  const [thorsten, setThorsten] = useState<ThorstenVoice[]>([]);

  useEffect(() => {
    let cancelled = false;

    api
      .getJson<{
        elevenlabs_enabled: boolean;
        fish_speech_enabled: boolean;
        kokoro_enabled: boolean;
        mylab_enabled: boolean;
        thorsten_enabled: boolean;
      }>("/api/tts/providers")
      .then(async (data) => {
        if (cancelled) return;

        const flags: ProviderFlags = {
          elevenlabs: data.elevenlabs_enabled,
          fish_speech: data.fish_speech_enabled,
          kokoro: data.kokoro_enabled ?? false,
          mylab: data.mylab_enabled ?? false,
          thorsten: includeThorsten ? (data.thorsten_enabled ?? false) : false,
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
              .getJson<{ voices: MylabVoice[] }>("/api/mylab/voices")
              .then((v) => {
                if (cancelled) return;
                setMylab(v.voices ?? []);
              })
              .catch(() => {}),
          );
        }
        if (flags.thorsten) {
          tasks.push(
            api
              .getJson<{ voices: ThorstenVoice[] }>("/api/thorsten/voices")
              .then((v) => {
                if (cancelled) return;
                setThorsten(v.voices ?? []);
              })
              .catch(() => {}),
          );
        }

        await Promise.allSettled(tasks);
      })
      .catch(() => {
        if (cancelled) return;
        setProviders({ ...EMPTY_FLAGS, elevenlabs: true });
        setDefaultProvider("elevenlabs");
      })
      .finally(() => {
        if (cancelled) return;
        setLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [includeThorsten]);

  useEffect(() => {
    if (!loaded || defaultVoiceId) return;
    if (defaultProvider === "kokoro" && kokoro.length > 0) {
      setDefaultVoiceId(kokoro[0].voice_id);
    } else if (defaultProvider === "mylab" && mylab.length > 0) {
      setDefaultVoiceId(mylab[0].voice_id);
    } else if (defaultProvider === "thorsten" && thorsten.length > 0) {
      setDefaultVoiceId(thorsten[0].voice_id);
    } else if (defaultProvider === "elevenlabs" && elevenlabs.length > 0) {
      setDefaultVoiceId(elevenlabs[0].voice_id);
    }
  }, [loaded, defaultProvider, defaultVoiceId, kokoro, mylab, thorsten, elevenlabs]);

  return {
    loaded,
    providers,
    defaultProvider,
    defaultVoiceId,
    elevenlabs,
    kokoro,
    mylab,
    thorsten,
  };
}
