"use client";

import { useCallback, useState } from "react";
import type { Chapter, Source } from "../_types";

interface UseChaptersOptions {
  uuid: string;
  /** From useSources, moving a file changes its chapter. */
  setSources: (updater: (prev: Source[]) => Source[]) => void;
}

/** Create, rename, move and delete chapters and assign files. */
export function useChapters({ uuid, setSources }: UseChaptersOptions) {
  const [chapters, setChapters] = useState<Chapter[]>([]);

  const createChapter = useCallback(async (name: string) => {
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/chapters`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "");
    setChapters((prev) => [...prev, data as Chapter]);
  }, [uuid]);

  const renameChapter = useCallback(async (chapterUuid: string, name: string) => {
    const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/chapters/${chapterUuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "");
    setChapters((prev) => prev.map((c) => (c.uuid === chapterUuid ? { ...c, name: data.name } : c)));
  }, [uuid]);

  const deleteChapter = useCallback(async (chapterUuid: string) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/chapters/${chapterUuid}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) return;
      setChapters((prev) => prev.filter((c) => c.uuid !== chapterUuid));
      // The files in it stay, they end up without a chapter.
      setSources((prev) =>
        prev.map((s) => (s.chapter_uuid === chapterUuid ? { ...s, chapter_uuid: null } : s))
      );
    } catch { /* ignore */ }
  }, [uuid, setSources]);

  const moveChapter = useCallback(async (chapterUuid: string, direction: "up" | "down") => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/chapters/${chapterUuid}/move`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ direction }),
      });
      if (!res.ok) return;
      // The server sends the new order, swapping ourselves would be a second truth.
      const data = await res.json().catch(() => null);
      if (Array.isArray(data?.chapters)) setChapters(data.chapters as Chapter[]);
    } catch { /* ignore */ }
  }, [uuid]);

  const setSourceChapter = useCallback(async (sourceUuid: string, chapterUuid: string | null) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/sources/${sourceUuid}/chapter`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chapter_uuid: chapterUuid }),
      });
      if (!res.ok) return;
      setSources((prev) =>
        prev.map((s) => (s.uuid === sourceUuid ? { ...s, chapter_uuid: chapterUuid } : s))
      );
    } catch { /* ignore */ }
  }, [uuid, setSources]);

  return {
    chapters, setChapters,
    createChapter, renameChapter, deleteChapter, moveChapter, setSourceChapter,
  };
}
