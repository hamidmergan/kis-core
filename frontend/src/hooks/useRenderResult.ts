"use client";

import { useCallback, useState } from "react";

interface ApplyOptions {
  audioId?: string;
  audioCount?: number;
  resultStem?: string;
  hasSubtitles?: boolean;
}

export function useRenderResult() {
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [resultStem, setResultStem] = useState<string>("");
  const [hasSubtitles, setHasSubtitles] = useState(false);

  // Die Adresse statt eines Blobs: das Video startet sofort und laesst sich springen.
  const apply = useCallback((url: string, opts: ApplyOptions = {}) => {
    setHasSubtitles(opts.hasSubtitles === true);
    if (opts.audioId) setAudioId(opts.audioId);
    if (opts.audioCount !== undefined) setAudioCount(opts.audioCount);
    if (opts.resultStem) setResultStem(opts.resultStem);
    setVideoUrl(url);
  }, []);

  const clear = useCallback(() => {
    setVideoUrl(null);
    setAudioId("");
    setAudioCount(0);
    setResultStem("");
    setHasSubtitles(false);
  }, []);

  return { videoUrl, audioId, audioCount, resultStem, hasSubtitles, apply, clear };
}
