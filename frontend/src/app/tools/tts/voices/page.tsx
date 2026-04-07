"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import BackLink from "@/components/BackLink";
import Spinner from "@/components/Spinner";

interface Voice {
  voice_id: string;
  label: string;
  preview_url: string | null;
  category?: string | null;
  description?: string | null;
  use_case?: string | null;
}

const CATEGORY_DE: Record<string, string> = {
  professional: "Professionell",
  high_quality: "Hohe Qualität",
};

const DESCRIPTION_DE: Record<string, string> = {
  // Charakter / Stil
  "Laid-Back": "Entspannt",
  "Casual": "Locker",
  "Formal": "Förmlich",
  "Friendly": "Freundlich",
  "Warm": "Warm",
  "Authoritative": "Autoritär",
  "Confident": "Selbstsicher",
  "Calm": "Ruhig",
  "Energetic": "Energetisch",
  "Upbeat": "Lebhaft",
  "Serious": "Sachlich",
  "Raspy": "Rau",
  "Smooth": "Weich",
  "Deep": "Tief",
  "Resonant": "Resonant",
  "Crisp": "Klar",
  "Soft": "Sanft",
  "Husky": "Heiser",
  "Clear": "Deutlich",
  "Conversational": "Gesprächig",
  "Narrative": "Erzählend",
  "Expressive": "Ausdrucksstark",
  "Melodic": "Melodisch",
  "Mature": "Reif",
  "Powerful": "Kraftvoll",
  "Bright": "Hell",
  "Grounded": "Geerdet",
  "Soothing": "Beruhigend",
  "Professional": "Professionell",
};

const USE_CASE_DE: Record<string, string> = {
  "narration": "Erzählung",
  "news": "Nachrichten",
  "audiobook": "Hörbuch",
  "conversational": "Gespräch",
  "conversation": "Gespräch",
  "social media": "Social Media",
  "social_media": "Social Media",
  "interactive": "Interaktiv",
  "video games": "Videospiele",
  "video_games": "Videospiele",
  "entertainment & tv": "Unterhaltung & TV",
  "entertainment_tv": "Unterhaltung & TV",
  "training & elearning": "Training & E-Learning",
  "training_elearning": "Training & E-Learning",
  "meditation": "Meditation",
  "characters": "Charaktere",
  "animation": "Animation",
  "characters_animation": "Charaktere & Animation",
  "narrative_story": "Erzählung",
  "informative_educational": "Bildung & Information",
  "advertisement": "Werbung",
  "ads": "Werbung",
};

function translateDesc(description?: string | null): string | null {
  if (!description) return null;
  return description.split(",").map(d => {
    const key = d.trim();
    return DESCRIPTION_DE[key] ?? key;
  }).join(" · ");
}

function translateLabel(description?: string | null, use_case?: string | null): string | null {
  const parts: string[] = [];
  const desc = translateDesc(description);
  if (desc) parts.push(desc);
  if (use_case) parts.push(USE_CASE_DE[use_case.toLowerCase().trim()] ?? use_case);
  return parts.length > 0 ? parts.join(" · ") : null;
}

type VoicesTab = "elevenlabs" | "fish_speech" | "kokoro" | "mylab";

const KOKORO_ACCENT_LABEL: Record<string, string> = {
  "American": "🇺🇸",
  "British": "🇬🇧",
  "Deutsch": "🇩🇪",
};

const KOKORO_LANGUAGE_ORDER = ["Deutsch", "English"];
const KOKORO_LANGUAGE_LABEL: Record<string, string> = {
  "Deutsch": "🇩🇪 Deutsch",
  "English": "🇺🇸🇬🇧 English",
};

function StimmenPageInner() {
  const searchParams = useSearchParams();
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(true);
  const [fishSpeechEnabled, setFishSpeechEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [activeTab, setActiveTab] = useState<VoicesTab>(
    (searchParams.get("tab") as VoicesTab | null) ?? "elevenlabs"
  );
  const [voices, setVoices] = useState<Voice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{voice_id: string; name: string; language?: string; accent: string; gender: string}>>([]);
  const [kokoroLoading, setKokoroLoading] = useState(false);
  const [mylabVoices, setMylabVoices] = useState<Array<{voice_id: string; name: string; description: string}>>([]);
  const [mylabLoading, setMylabLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [loadingKokoroId, setLoadingKokoroId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const tabFromUrl = searchParams.get("tab") as VoicesTab | null;
    fetch("/api/tts/providers", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const el = d.elevenlabs_enabled ?? true;
        const fs = d.fish_speech_enabled ?? false;
        const ko = d.kokoro_enabled ?? false;
        const ml = d.mylab_enabled ?? false;
        setElevenlabsEnabled(el);
        setFishSpeechEnabled(fs);
        setKokoroEnabled(ko);
        setMylabEnabled(ml);
        // URL-Parameter hat Vorrang; sonst ersten aktiven Tab wählen
        if (tabFromUrl === "mylab" && ml) setActiveTab("mylab");
        else if (tabFromUrl === "kokoro" && ko) setActiveTab("kokoro");
        else if (tabFromUrl === "fish_speech" && fs) setActiveTab("fish_speech");
        else if (tabFromUrl === "elevenlabs" && el) setActiveTab("elevenlabs");
        else if (!el) setActiveTab(fs ? "fish_speech" : ko ? "kokoro" : ml ? "mylab" : "elevenlabs");
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!elevenlabsEnabled) { setLoading(false); return; }
    fetch("/api/voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setVoices(data.voices ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [elevenlabsEnabled]);

  useEffect(() => {
    if (activeTab === "kokoro" && kokoroVoices.length === 0) {
      setKokoroLoading(true);
      fetch("/api/kokoro/voices", { credentials: "include" })
        .then((r) => r.json())
        .then((data) => setKokoroVoices(data.voices ?? []))
        .catch(() => {})
        .finally(() => setKokoroLoading(false));
    }
  }, [activeTab, kokoroVoices.length]);

  useEffect(() => {
    if (activeTab === "mylab" && mylabVoices.length === 0) {
      setMylabLoading(true);
      fetch("/api/mylab/voices", { credentials: "include" })
        .then((r) => r.json())
        .then((data) => setMylabVoices(data.voices ?? []))
        .catch(() => {})
        .finally(() => setMylabLoading(false));
    }
  }, [activeTab, mylabVoices.length]);

  const handlePlayMylab = async (voiceId: string) => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;

    if (playingId === voiceId || loadingKokoroId === voiceId) {
      setPlayingId(null);
      setLoadingKokoroId(null);
      return;
    }

    setLoadingKokoroId(voiceId);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch("/api/mylab/preview", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_id: voiceId }),
        signal: controller.signal,
      });
      if (!res.ok) { setLoadingKokoroId(null); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setLoadingKokoroId(null);
      setPlayingId(voiceId);
      audio.play().catch(() => {});
      audio.onended = () => { setPlayingId(null); URL.revokeObjectURL(url); };
      audio.onerror = () => { setPlayingId(null); URL.revokeObjectURL(url); };
    } catch (e) {
      if ((e as Error).name !== "AbortError") setLoadingKokoroId(null);
    }
  };

  const handlePlayKokoro = async (voiceId: string) => {
    // Stop any current audio and abort any in-flight fetch
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    abortRef.current?.abort();
    abortRef.current = null;

    // Toggle off if same voice clicked while playing or loading
    if (playingId === voiceId || loadingKokoroId === voiceId) {
      setPlayingId(null);
      setLoadingKokoroId(null);
      return;
    }

    setLoadingKokoroId(voiceId);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const res = await fetch("/api/kokoro/preview", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice_id: voiceId }),
        signal: controller.signal,
      });
      if (!res.ok) { setLoadingKokoroId(null); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audioRef.current = audio;
      setLoadingKokoroId(null);
      setPlayingId(voiceId);
      audio.play().catch(() => {});
      audio.onended = () => { setPlayingId(null); URL.revokeObjectURL(url); };
      audio.onerror = () => { setPlayingId(null); URL.revokeObjectURL(url); };
    } catch (e) {
      if ((e as Error).name !== "AbortError") setLoadingKokoroId(null);
    }
  };

  const handlePlay = (voice: Voice) => {
    if (!voice.preview_url) return;

    // Stop currently playing audio
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    if (playingId === voice.voice_id) {
      setPlayingId(null);
      return;
    }

    const audio = new Audio(voice.preview_url);
    audioRef.current = audio;
    setPlayingId(voice.voice_id);
    audio.play().catch(() => {});
    audio.onended = () => setPlayingId(null);
    audio.onerror = () => setPlayingId(null);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => { audioRef.current?.pause(); };
  }, []);

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        <h1 className="text-xl font-bold text-gray-900 mb-1">Verfügbare Stimmen</h1>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 mb-6">
          {elevenlabsEnabled && (
            <button
              onClick={() => setActiveTab("elevenlabs")}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "elevenlabs"
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              ElevenLabs
            </button>
          )}

          {kokoroEnabled && (
            <button
              onClick={() => setActiveTab("kokoro")}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "kokoro"
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Kokoro TTS
            </button>
          )}

          {mylabEnabled && (
            <button
              onClick={() => setActiveTab("mylab")}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "mylab"
                  ? "border-primary text-primary"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              THL myLab
            </button>
          )}
        </div>



        {/* myLab Stimmen */}
        {activeTab === "mylab" && (
          mylabLoading ? (
            <p className="text-sm text-gray-500">Wird geladen…</p>
          ) : mylabVoices.length === 0 ? (
            <p className="text-sm text-gray-400">myLab TTS Server nicht erreichbar oder keine Stimmen gefunden.</p>
          ) : (
            <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
              {mylabVoices.map((voice) => (
                <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50">
                  <div>
                    <p className="text-sm font-medium text-gray-900">{voice.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">{voice.description}</p>
                  </div>
                  <button
                    onClick={() => handlePlayMylab(voice.voice_id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-blue-50 transition-colors"
                    aria-label={playingId === voice.voice_id ? "Stoppen" : "Anhören"}
                  >
                    {loadingKokoroId === voice.voice_id ? (
                      <>
                        <Spinner size="sm" />
                        Laden…
                      </>
                    ) : playingId === voice.voice_id ? (
                      <>
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <rect x="6" y="4" width="4" height="16" rx="1" />
                          <rect x="14" y="4" width="4" height="16" rx="1" />
                        </svg>
                        Stopp
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                        Anhören
                      </>
                    )}
                  </button>
                </div>
              ))}
            </div>
          )
        )}

        {/* Kokoro Stimmen — gruppiert nach Sprache */}
        {activeTab === "kokoro" && (
          kokoroLoading ? (
            <p className="text-sm text-gray-500">Wird geladen…</p>
          ) : kokoroVoices.length === 0 ? (
            <p className="text-sm text-gray-400">Kokoro Server nicht erreichbar oder keine Stimmen gefunden.</p>
          ) : (() => {
            const grouped: Record<string, typeof kokoroVoices> = {};
            for (const v of kokoroVoices) {
              const lang = v.language || (v.accent === "American" || v.accent === "British" ? "English" : v.accent);
              if (!grouped[lang]) grouped[lang] = [];
              grouped[lang].push(v);
            }
            const languages = KOKORO_LANGUAGE_ORDER.filter(l => grouped[l]);
            for (const l of Object.keys(grouped)) {
              if (!languages.includes(l)) languages.push(l);
            }
            return (
              <div className="space-y-4">
                {languages.map((lang) => (
                  <details key={lang} open={lang === "Deutsch"}>
                    <summary className="cursor-pointer select-none px-4 py-3 bg-gray-50 border border-gray-200 rounded-lg text-sm font-medium text-gray-800 hover:bg-gray-100 transition-colors">
                      {KOKORO_LANGUAGE_LABEL[lang] ?? lang}
                      <span className="ml-2 text-xs text-gray-400 font-normal">
                        {grouped[lang].length} {grouped[lang].length === 1 ? "Stimme" : "Stimmen"}
                      </span>
                    </summary>
                    <div className="mt-1 divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
                      {grouped[lang].map((voice) => (
                        <div key={voice.voice_id} className="flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50">
                          <div>
                            <p className="text-sm font-medium text-gray-900">
                              {voice.name}
                            </p>
                            <p className="text-xs text-gray-400 mt-0.5">
                              {voice.gender === "Female" ? "Weiblich" : "Männlich"}
                              {voice.accent && lang === "English" ? ` · ${voice.accent}` : ""}
                            </p>
                          </div>
                          <button
                            onClick={() => handlePlayKokoro(voice.voice_id)}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-blue-50 transition-colors"
                            aria-label={playingId === voice.voice_id ? "Stoppen" : "Anhören"}
                          >
                            {loadingKokoroId === voice.voice_id ? (
                              <>
                                <Spinner size="sm" />
                                Laden…
                              </>
                            ) : playingId === voice.voice_id ? (
                              <>
                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                  <rect x="6" y="4" width="4" height="16" rx="1" />
                                  <rect x="14" y="4" width="4" height="16" rx="1" />
                                </svg>
                                Stopp
                              </>
                            ) : (
                              <>
                                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                                  <path d="M8 5v14l11-7z" />
                                </svg>
                                Anhören
                              </>
                            )}
                          </button>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            );
          })()
        )}

        {activeTab === "elevenlabs" && (
          loading ? (
            <p className="text-sm text-gray-500">Wird geladen…</p>
          ) : voices.length === 0 ? (
            <p className="text-sm text-gray-500">Keine Stimmen verfügbar.</p>
          ) : (
          <div className="divide-y divide-gray-100 border border-gray-200 rounded-lg overflow-hidden">
            {voices.map((voice) => (
              <div
                key={voice.voice_id}
                className="flex items-center justify-between px-4 py-3 bg-white hover:bg-gray-50"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{voice.label.split(" - ")[0]}</p>
                  {(() => {
                    const parts: string[] = [];
                    if (voice.category && CATEGORY_DE[voice.category]) parts.push(CATEGORY_DE[voice.category]);
                    const desc = translateLabel(voice.description, voice.use_case);
                    if (desc) parts.push(desc);
                    return parts.length > 0 ? (
                      <p className="text-xs text-gray-400 mt-0.5">{parts.join(" · ")}</p>
                    ) : null;
                  })()}
                </div>
                {voice.preview_url ? (
                  <button
                    onClick={() => handlePlay(voice)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-blue-50 transition-colors"
                    aria-label={playingId === voice.voice_id ? "Stoppen" : "Anhören"}
                  >
                    {playingId === voice.voice_id ? (
                      <>
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <rect x="6" y="4" width="4" height="16" rx="1" />
                          <rect x="14" y="4" width="4" height="16" rx="1" />
                        </svg>
                        Stopp
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                        Anhören
                      </>
                    )}
                  </button>
                ) : (
                  <span className="text-xs text-gray-400">Kein Sample</span>
                )}
              </div>
            ))}
          </div>
          )
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function StimmenPage() {
  return (
    <Suspense>
      <StimmenPageInner />
    </Suspense>
  );
}
