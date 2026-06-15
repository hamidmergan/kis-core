"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { MindmapNodeData } from "../_components/studio/MindmapStudio";

interface UseMindmapOptions {
  uuid: string;
  selectedSourceIds: string[];
}

export function useMindmap({ uuid, selectedSourceIds }: UseMindmapOptions) {
  const [mindmapData, setMindmapData] = useState<MindmapNodeData | null>(null);
  const [mindmapLoading, setMindmapLoading] = useState(false);
  const [mindmapList, setMindmapList] = useState<{ id: number; created_at: string | null; topic: string }[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const refreshList = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmaps`, { credentials: "include" });
      if (res.ok) setMindmapList(await res.json());
    } catch { /* ignore */ }
  }, [uuid]);

  const startPolling = useCallback((mindmapId: number) => {
    stopPolling();
    setMindmapLoading(true);
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/${mindmapId}`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.mindmap) {
          setMindmapData(data.mindmap);
          setMindmapLoading(false);
          stopPolling();
          refreshList();
        } else if (data.status === "failed") {
          console.error("Mindmap failed:", data.error);
          setMindmapLoading(false);
          stopPolling();
        }
      } catch { /* ignore */ }
    }, 3000);
  }, [uuid, stopPolling, refreshList]);

  // Load existing + resume polling
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.mindmap) {
          setMindmapData(data.mindmap);
        } else if (data.id && (data.status === "pending" || data.status === "running")) {
          startPolling(data.id);
        }
      } catch { /* ignore */ }
    })();
    refreshList();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  const generate = useCallback(async () => {
    if (selectedSourceIds.length === 0) return;
    setMindmapLoading(true);
    try {
      // api.fetch attaches Accept-Language from the NEXT_LOCALE cookie so the
      // mind map labels are generated in the UI language (raw fetch defaulted to de).
      const res = await api.fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds.slice(0, 5) }),
      });
      if (res.ok) {
        const data = await res.json();
        startPolling(data.mindmap_id);
      } else {
        const err = await res.text();
        console.error("Mindmap generate error:", res.status, err);
        setMindmapLoading(false);
      }
    } catch {
      setMindmapLoading(false);
    }
  }, [uuid, selectedSourceIds, startPolling]);

  const select = useCallback(async (id: number) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/${id}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === "success" && data.mindmap) setMindmapData(data.mindmap);
    } catch { /* ignore */ }
  }, [uuid]);

  const remove = useCallback(async (id: number) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/${id}`, { method: "DELETE", credentials: "include" });
      setMindmapList((prev) => prev.filter((m) => m.id !== id));
    } catch { /* ignore */ }
  }, [uuid]);

  return {
    mindmapData, mindmapLoading, mindmapList,
    generate, select, remove,
  };
}
