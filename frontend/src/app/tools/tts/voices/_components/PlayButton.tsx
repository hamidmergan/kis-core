"use client";

import Spinner from "@/components/ui/Spinner";


interface Props {
  voiceId: string;
  playingId: string | null;
  loadingId: string | null;
  onClick: () => void;
}


export default function PlayButton({ voiceId, playingId, loadingId, onClick }: Props) {
  const isPlaying = playingId === voiceId;
  const isLoading = loadingId === voiceId;

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary border border-primary rounded-md hover:bg-blue-50 transition-colors"
      aria-label={isPlaying ? "Stoppen" : "Anhören"}
    >
      {isLoading ? (
        <>
          <Spinner size="sm" />
          Laden…
        </>
      ) : isPlaying ? (
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
  );
}
