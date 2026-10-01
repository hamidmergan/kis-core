"use client";

import { useCallback, useEffect, useState } from "react";
import { readWorkspaceUi, updateWorkspaceUi } from "@/lib/browserStore";
import type { Chapter, Source } from "../_types";

interface UseChaptersOptions {
  uuid: string;
  /** From useSources, moving a file changes its chapter. */
  setSources: (updater: (prev: Source[]) => Source[]) => void;
}

/** Create, rename, move and delete chapters, assign files, fold and unfold. */
export function useChapters({ uuid, setSources }: UseChaptersOptions) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [closedChapters, setClosedChapters] = useState<string[]>([]);

  // Collapsed chapters survive a page change.
  useEffect(() => {
    const saved = readWorkspaceUi(uuid).closedChapters;
    setClosedChapters(Array.isArray(saved) ? saved : []);
  }, [uuid]);

  const merkeGeschlossen = useCallback((next: string[]) => {
    updateWorkspaceUi(uuid, { closedChapters: next.length ? next : undefined });
    return next;
  }, [uuid]);

  const toggleChapterOpen = useCallback((chapterUuid: string) => {
    setClosedChapters((prev) => merkeGeschlossen(
      prev.includes(chapterUuid) ? prev.filter((id) => id !== chapterUuid) : [...prev, chapterUuid],
    ));
  }, [merkeGeschlossen]);

  /** Unfolds one chapter, the tour needs a row that may sit in a folded one. */
  const openChapter = useCallback((chapterUuid: string) => {
    setClosedChapters((prev) =>
      prev.includes(chapterUuid) ? merkeGeschlossen(prev.filter((id) => id !== chapterUuid)) : prev,
    );
  }, [merkeGeschlossen]);

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
    closedChapters, toggleChapterOpen, openChapter,
    createChapter, renameChapter, deleteChapter, moveChapter, setSourceChapter,
  };
}
