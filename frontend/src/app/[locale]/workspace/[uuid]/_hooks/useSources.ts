"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import type { WorkspaceDetail, Source } from "../_types";

interface UseSourcesOptions {
  uuid: string;
  onModuleUpdate?: (workspace: WorkspaceDetail) => void;
}

export function useSources({ uuid, onModuleUpdate }: UseSourcesOptions) {
  const t = useTranslations("workspace.detail.errors");
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; percent: number } | null>(null);
  const [uploadErrors, setUploadErrors] = useState<{ filename: string; message: string }[]>([]);

  // Persist selected sources
  useEffect(() => {
    if (selectedSourceIds.length > 0) {
      sessionStorage.setItem(`kis-selected-sources-${uuid}`, JSON.stringify(selectedSourceIds));
    }
  }, [selectedSourceIds, uuid]);

  // Keep polling while a source is still being processed.
  useEffect(() => {
    const isProcessing = (s: Source) =>
      s.status === "pending" || s.status === "indexing" || (s.status === "ready" && !!s.progress);
    const isFullyReady = (s: Source) => s.status === "ready" && !s.progress;
    const pendingIds = sources.filter(isProcessing).map((s) => s.uuid);
    if (pendingIds.length === 0) return;
    const id = setInterval(async () => {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, { credentials: "include" });
      if (!res.ok) return;
      const mod: WorkspaceDetail = await res.json();
      const srcs: Source[] = mod.sources ?? [];
      setSources(srcs);
      onModuleUpdate?.(mod);
      setSelectedSourceIds((prev) => {
        const justBecameReady = srcs.filter((s) => isFullyReady(s) && pendingIds.includes(s.uuid) && !prev.includes(s.uuid)).map((s) => s.uuid);
        return justBecameReady.length > 0 ? [...prev, ...justBecameReady] : prev;
      });
    }, 3000);
    return () => clearInterval(id);
  }, [sources, uuid, onModuleUpdate]);

  const toggleSource = useCallback((srcUuid: string) => {
    setSelectedSourceIds((prev) =>
      prev.includes(srcUuid) ? prev.filter((id) => id !== srcUuid) : [...prev, srcUuid]
    );
  }, []);

  const deleteSource = useCallback(async (srcUuid: string) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${srcUuid}`, { method: "DELETE", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.filter((s) => s.uuid !== srcUuid));
        setSelectedSourceIds((prev) => prev.filter((id) => id !== srcUuid));
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const renameSource = useCallback(async (srcUuid: string, name: string) => {
    // Unlike deleting this swallows no error, a rejected name has to be noticed.
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${srcUuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "");
    setSources((prev) => prev.map((s) => (s.uuid === srcUuid ? { ...s, filename: data.filename } : s)));
  }, [uuid]);

  const retrySource = useCallback(async (srcUuid: string) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${srcUuid}/retry`, { method: "POST", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.map((s) => s.uuid === srcUuid ? { ...s, status: "pending", error_message: null } : s));
      }
    } catch { /* ignore */ }
  }, [uuid]);

  // The progress makes the row spin and keeps the polling on until the summary is there.
  const summarizeSource = useCallback(async (srcUuid: string) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${srcUuid}/summary`, { method: "POST", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.map((s) => s.uuid === srcUuid ? { ...s, progress: { stage: "summarizing" } } : s));
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const uploadFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    // Only caps absurdly large batches, the real limits are drawn by the backend.
    const MAX_BATCH = 30;
    const skipped = files.length > MAX_BATCH ? files.slice(MAX_BATCH) : [];
    const toUpload = files.length > MAX_BATCH ? files.slice(0, MAX_BATCH) : files;
    const errors: { filename: string; message: string }[] = skipped.map((f) => ({
      filename: f.name,
      message: t("uploadSkippedMax", { max: MAX_BATCH }),
    }));
    setUploadErrors(errors);
    let rateLimitHit = false;
    // Existing names save the network trip, the backend stays authoritative.
    const existingNames = new Set(sources.map((s) => (s.filename ?? "").trim().toLowerCase()));
    for (let i = 0; i < toUpload.length; i++) {
      const file = toUpload[i];
      if (rateLimitHit) {
        // If the limit is full, the remaining files bounce off just the same.
        errors.push({ filename: file.name, message: t("uploadSkippedLimit") });
        continue;
      }
      const nameKey = file.name.trim().toLowerCase();
      if (existingNames.has(nameKey)) {
        errors.push({ filename: file.name, message: t("uploadDuplicate") });
        continue;
      }
      // Guard against duplicates within the same drop too.
      existingNames.add(nameKey);
      setUploadProgress({ current: i + 1, total: toUpload.length, percent: 0 });
      // A full server answers 503 after a short wait, the file then goes again by itself.
      const sendOnce = () => new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `/api/ai-assistant/workspaces/${uuid}/sources`);
        xhr.withCredentials = true;
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) setUploadProgress({ current: i + 1, total: toUpload.length, percent: Math.round((e.loaded / e.total) * 100) });
        };
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            const newSrc: Source = JSON.parse(xhr.responseText);
            setSources((prev) => [newSrc, ...prev]);
            resolve();
          } else {
            if (xhr.status === 429) rateLimitHit = true;
            let detail: string = t("uploadFailed");
            try {
              const body = JSON.parse(xhr.responseText);
              // The reason arrives sometimes as an object and sometimes as text.
              if (typeof body?.detail === "string") {
                detail = body.detail;
              } else if (body?.detail?.message) {
                detail = body.detail.message;
              }
            } catch { /* ignore */ }
            reject(Object.assign(new Error(detail), { status: xhr.status }));
          }
        };
        xhr.onerror = () => reject(new Error(t("networkError")));
        const form = new FormData();
        form.append("file", file);
        xhr.send(form);
      });
      try {
        const bis = Date.now() + 20 * 60 * 1000;
        for (;;) {
          try {
            await sendOnce();
            break;
          } catch (err) {
            const busy = (err as { status?: number }).status === 503;
            if (!busy || Date.now() > bis) throw err;
            await new Promise((r) => setTimeout(r, 5000 + Math.random() * 5000));
          }
        }
      } catch (err) {
        errors.push({ filename: file.name, message: err instanceof Error ? err.message : t("uploadFailed") });
      }
    }
    setUploadProgress(null);
    if (errors.length > 0) setUploadErrors(errors);
  }, [uuid, sources, t]);

  // One JSON post for every link-based source, the answer is the new row.
  const postSource = useCallback(async (path: string, payload: Record<string, string>) => {
    let res: Response;
    try {
      res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${path}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch {
      throw new Error(t("networkError"));
    }
    if (!res.ok) {
      let detail: string = t("uploadFailed");
      try {
        const body = await res.json();
        // The reason arrives sometimes as an object and sometimes as text.
        if (typeof body?.detail === "string") {
          detail = body.detail;
        } else if (body?.detail?.message) {
          detail = body.detail.message;
        }
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    const newSrc: Source = await res.json();
    setSources((prev) => [newSrc, ...prev]);
  }, [uuid, t]);

  const addLink = useCallback((url: string) => postSource("link", { url }), [postSource]);

  const addYoutube = useCallback(
    (url: string, transcript: string) => postSource("youtube", { url, transcript }),
    [postSource],
  );

  return {
    sources, setSources,
    selectedSourceIds, setSelectedSourceIds,
    uploadProgress,
    uploadErrors, setUploadErrors,
    toggleSource, deleteSource, renameSource, retrySource, summarizeSource, uploadFiles, addLink, addYoutube,
  };
}
