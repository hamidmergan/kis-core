"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";


interface Props {
  voiceId: string;
  playingId: string | null;
  loadingId: string | null;
  onClick: () => void;
}


export default function PlayButton({ voiceId, playingId, loadingId, onClick }: Props) {
  const t = useTranslations("tools.tts.voices.playButton");
  const isPlaying = playingId === voiceId;
  const isLoading = loadingId === voiceId;

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-kb border border-kb rounded-md hover:bg-kb20 transition-colors"
      aria-label={isPlaying ? t("stop") : t("play")}
    >
      {isLoading ? (
        <>
          <Spinner size="sm" />
          {t("loading")}
        </>
      ) : isPlaying ? (
        <>
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <rect x="6" y="4" width="4" height="16" rx="1" />
            <rect x="14" y="4" width="4" height="16" rx="1" />
          </svg>
          {t("stop")}
        </>
      ) : (
        <>
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M8 5v14l11-7z" />
          </svg>
          {t("play")}
        </>
      )}
    </button>
  );
}
