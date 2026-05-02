"use client";

import { useCallback, useEffect, useState } from "react";
import type { WorkspaceDetail, Source } from "../_types";

interface UseSourcesOptions {
  uuid: string;
  onModuleUpdate?: (workspace: WorkspaceDetail) => void;
}

export function useSources({ uuid, onModuleUpdate }: UseSourcesOptions) {
  const [sources, setSources] = useState<Source[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [prevSelectedSourceIds, setPrevSelectedSourceIds] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState<{ current: number; total: number; percent: number } | null>(null);
  const [uploadErrors, setUploadErrors] = useState<{ filename: string; message: string }[]>([]);

  // Persist selected sources
  useEffect(() => {
    if (selectedSourceIds.length > 0) {
      sessionStorage.setItem(`kis-selected-sources-${uuid}`, JSON.stringify(selectedSourceIds));
    }
  }, [selectedSourceIds, uuid]);

  // Poll pending/indexing sources
  useEffect(() => {
    const pendingIds = sources.filter((s) => s.status === "indexing" || s.status === "pending").map((s) => s.uuid);
    if (pendingIds.length === 0) return;
    const id = setInterval(async () => {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, { credentials: "include" });
      if (!res.ok) return;
      const mod: WorkspaceDetail = await res.json();
      const srcs: Source[] = mod.sources ?? [];
      setSources(srcs);
      onModuleUpdate?.(mod);
      setSelectedSourceIds((prev) => {
        const justBecameReady = srcs.filter((s) => s.status === "ready" && pendingIds.includes(s.uuid) && !prev.includes(s.uuid)).map((s) => s.uuid);
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

  const retrySource = useCallback(async (srcUuid: string) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${srcUuid}/retry`, { method: "POST", credentials: "include" });
      if (res.ok) {
        setSources((prev) => prev.map((s) => s.uuid === srcUuid ? { ...s, status: "pending", error_message: null } : s));
      }
    } catch { /* ignore */ }
  }, [uuid]);

  const uploadFiles = useCallback(async (files: File[]) => {
    if (files.length === 0) return;
    const MAX_BATCH = 10;
    const skipped = files.length > MAX_BATCH ? files.slice(MAX_BATCH) : [];
    const toUpload = files.length > MAX_BATCH ? files.slice(0, MAX_BATCH) : files;
    const errors: { filename: string; message: string }[] = skipped.map((f) => ({
      filename: f.name,
      message: `Übersprungen, maximal ${MAX_BATCH} Dateien gleichzeitig hochladen.`,
    }));
    setUploadErrors(errors);
    for (let i = 0; i < toUpload.length; i++) {
      const file = toUpload[i];
      setUploadProgress({ current: i + 1, total: toUpload.length, percent: 0 });
      try {
        await new Promise<void>((resolve, reject) => {
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
              let detail = "Upload fehlgeschlagen";
              try {
                const body = JSON.parse(xhr.responseText);
                if (body?.detail) detail = body.detail;
              } catch { /* ignore */ }
              reject(new Error(detail));
            }
          };
          xhr.onerror = () => reject(new Error("Netzwerkfehler"));
          const form = new FormData();
          form.append("file", file);
          xhr.send(form);
        });
      } catch (err) {
        errors.push({ filename: file.name, message: err instanceof Error ? err.message : "Upload fehlgeschlagen" });
      }
    }
    setUploadProgress(null);
    if (errors.length > 0) setUploadErrors(errors);
  }, [uuid]);

  return {
    sources, setSources,
    selectedSourceIds, setSelectedSourceIds,
    prevSelectedSourceIds, setPrevSelectedSourceIds,
    uploadProgress,
    uploadErrors, setUploadErrors,
    toggleSource, deleteSource, retrySource, uploadFiles,
  };
}
