"use client";

import { useCallback, useState } from "react";

interface ApplyOptions {
  audioId?: string;
  audioCount?: number;
  resultStem?: string;
}

export function useRenderResult() {
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [resultStem, setResultStem] = useState<string>("");

  const apply = useCallback((blob: Blob, opts: ApplyOptions = {}) => {
    if (opts.audioId) setAudioId(opts.audioId);
    if (opts.audioCount !== undefined) setAudioCount(opts.audioCount);
    if (opts.resultStem) setResultStem(opts.resultStem);
    setDownloadBlob(blob);
    setVideoUrl(URL.createObjectURL(blob));
  }, []);

  const clear = useCallback(() => {
    setDownloadBlob(null);
    setVideoUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
    setAudioId("");
    setAudioCount(0);
    setResultStem("");
  }, []);

  return { downloadBlob, videoUrl, audioId, audioCount, resultStem, apply, clear };
}
