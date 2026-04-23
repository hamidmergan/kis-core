"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";


export interface DemoVoice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}

export type DemoTtsProvider = "elevenlabs" | "fish_speech" | "kokoro" | "mylab";


export function useDemoProviders() {
  const [voices, setVoices] = useState<DemoVoice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{ voice_id: string; name: string; accent: string; gender: string }>>([]);
  const [mylabVoices, setMylabVoices] = useState<Array<{ voice_id: string; name: string; description: string }>>([]);
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<DemoTtsProvider>("kokoro");
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(false);
  const [fishSpeechEnabled, setFishSpeechEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [providersLoaded, setProvidersLoaded] = useState(false);

  useEffect(() => {
    api.getJson<{ elevenlabs_enabled: boolean; fish_speech_enabled: boolean; kokoro_enabled: boolean; mylab_enabled: boolean }>("/api/tts/providers")
      .then((data) => {
        setElevenlabsEnabled(data.elevenlabs_enabled);
        setFishSpeechEnabled(data.fish_speech_enabled);
        setKokoroEnabled(data.kokoro_enabled ?? false);
        setMylabEnabled(data.mylab_enabled ?? false);
        if (data.kokoro_enabled) setTtsProvider("kokoro");
        else if (data.mylab_enabled) setTtsProvider("mylab");
        else if (data.fish_speech_enabled) setTtsProvider("fish_speech");
        else if (data.elevenlabs_enabled) setTtsProvider("elevenlabs");
        if (data.elevenlabs_enabled) {
          api.getJson<{ voices: DemoVoice[] }>("/api/voices").then((vData) => {
            setVoices(vData.voices);
            if (vData.voices.length > 0) setVoiceId(vData.voices[0].voice_id);
          }).catch(() => {});
        }
        if (data.kokoro_enabled) {
          api.getJson<{ voices: Array<{ voice_id: string; name: string; accent: string; gender: string }> }>("/api/kokoro/voices")
            .then((kData) => {
              setKokoroVoices(kData.voices ?? []);
              if (kData.voices?.length > 0) setVoiceId(kData.voices[0].voice_id);
            }).catch(() => {});
        }
        if (data.mylab_enabled) {
          api.getJson<{ voices: Array<{ voice_id: string; name: string; description: string }> }>("/api/mylab/voices")
            .then((mData) => {
              setMylabVoices(mData.voices ?? []);
              if (mData.voices?.length > 0 && !data.kokoro_enabled) setVoiceId(mData.voices[0].voice_id);
            }).catch(() => {});
        }
      })
      .catch(() => { setElevenlabsEnabled(true); })
      .finally(() => { setProvidersLoaded(true); });
  }, []);

  return {
    voices, kokoroVoices, mylabVoices, voiceId, setVoiceId,
    ttsProvider, setTtsProvider,
    elevenlabsEnabled, fishSpeechEnabled, kokoroEnabled, mylabEnabled,
    providersLoaded,
  };
}
