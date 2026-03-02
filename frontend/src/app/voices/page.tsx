"use client";

import { useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";

interface Voice {
  voice_id: string;
  label: string;
  preview_url: string | null;
}

export default function StimmenPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    fetch("/api/voices", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => setVoices(data.voices ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Verfügbare Stimmen</h1>

        {loading ? (
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
                  <p className="text-sm font-medium text-gray-900">{voice.label}</p>
                  <p className="text-xs text-gray-400 font-mono mt-0.5">{voice.voice_id}</p>
                </div>
                {voice.preview_url ? (
                  <button
                    onClick={() => handlePlay(voice)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-[#0066cc] border border-[#0066cc] rounded-md hover:bg-blue-50 transition-colors"
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
        )}
      </div>
    </ProtectedRoute>
  );
}
