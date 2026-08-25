"use client";

import { useCallback, useState } from "react";

interface ApplyOptions {
  audioId?: string;
  audioCount?: number;
  laufStempel?: string;
  hasSubtitles?: boolean;
  videoFolien?: number[] | null;
}

export function useRenderResult() {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [laufStempel, setLaufStempel] = useState<string>("");
  const [hasSubtitles, setHasSubtitles] = useState(false);
  const [videoFolien, setVideoFolien] = useState<number[] | null>(null);

  // Die Adresse statt eines Blobs: das Video startet sofort und laesst sich springen.
  const apply = useCallback((url: string, opts: ApplyOptions = {}) => {
    setHasSubtitles(opts.hasSubtitles === true);
    if (opts.audioId) setAudioId(opts.audioId);
    if (opts.audioCount !== undefined) setAudioCount(opts.audioCount);
    if (opts.laufStempel) setLaufStempel(opts.laufStempel);
    setVideoFolien(opts.videoFolien ?? null);
    setVideoUrl(url);
  }, []);

  const clear = useCallback(() => {
    setVideoUrl(null);
    setAudioId("");
    setAudioCount(0);
    setLaufStempel("");
    setHasSubtitles(false);
    setVideoFolien(null);
  }, []);

  return { videoUrl, audioId, audioCount, laufStempel, hasSubtitles, videoFolien, apply, clear };
}
