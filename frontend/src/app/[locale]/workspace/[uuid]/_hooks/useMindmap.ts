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
  const [mindmapList, setMindmapList] = useState<{ id: number; created_at: string | null; topic: string; user_instruction?: string }[]>([]);
  // What the user ticked, so the legend can also show what did not make it into the map.
  const [mindmapSources, setMindmapSources] = useState<{ number: number; filename: string }[]>([]);
  // The instruction this map was made with, and whether the sources had nothing on it.
  const [mindmapInstruction, setMindmapInstruction] = useState("");
  const [mindmapUnmatched, setMindmapUnmatched] = useState(false);

  const takeMap = useCallback((data: { mindmap: MindmapNodeData; sources?: { number: number; filename: string }[]; user_instruction?: string; instruction_unmatched?: boolean }) => {
    setMindmapData(data.mindmap);
    setMindmapSources(data.sources || []);
    setMindmapInstruction(data.user_instruction || "");
    setMindmapUnmatched(Boolean(data.instruction_unmatched));
  }, []);
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
          takeMap(data);
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
  }, [uuid, stopPolling, refreshList, takeMap]);

  // Load existing + resume polling
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap`, { credentials: "include" });
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success" && data.mindmap) {
          takeMap(data);
        } else if (data.id && (data.status === "pending" || data.status === "running")) {
          startPolling(data.id);
        }
      } catch { /* ignore */ }
    })();
    refreshList();
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid]);

  const generate = useCallback(async (instruction = "") => {
    if (selectedSourceIds.length === 0) return;
    setMindmapLoading(true);
    try {
      // api.fetch appends the interface language so the labels are produced in it.
      const res = await api.fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_source_ids: selectedSourceIds, instruction }),
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
      if (data.status === "success" && data.mindmap) {
        takeMap(data);
      }
    } catch { /* ignore */ }
  }, [uuid, takeMap]);

  const remove = useCallback(async (id: number) => {
    try {
      await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/${id}`, { method: "DELETE", credentials: "include" });
      setMindmapList((prev) => prev.filter((m) => m.id !== id));
    } catch { /* ignore */ }
  }, [uuid]);

  // Rethrows, when renaming the field should show the reason.
  const rename = useCallback(async (id: number, title: string) => {
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/mindmap/${id}/title`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "");
    const daten = await res.json();
    // Replace in the list directly so it does not flicker.
    setMindmapList((prev) => prev.map((m) => (m.id === id ? { ...m, topic: daten.title } : m)));
  }, [uuid]);

  return {
    mindmapData, mindmapLoading, mindmapList, mindmapSources,
    mindmapInstruction, mindmapUnmatched,
    generate, select, remove, rename,
  };
}
