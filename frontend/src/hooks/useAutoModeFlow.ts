"use client";

import { useCallback, useState } from "react";
import type { ScreencastState } from "@/types";

export function useAutoModeFlow() {
  const [state, setState] = useState<ScreencastState>("idle");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState("");
  const [error, setError] = useState("");

  const start = useCallback(() => {
    setDownloadBlob(null);
    setDownloadName("");
    setError("");
    setState("processing");
  }, []);

  const succeed = useCallback((blob: Blob, name: string) => {
    setDownloadBlob(blob);
    setDownloadName(name);
    setState("done");
  }, []);

  const fail = useCallback((msg: string) => {
    setError(msg);
    setState("error");
  }, []);

  const reset = useCallback(() => {
    setState("idle");
    setDownloadBlob(null);
    setDownloadName("");
    setError("");
  }, []);

  return { state, setState, downloadBlob, downloadName, error, setError, start, succeed, fail, reset };
}
