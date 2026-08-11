"use client";

import { useCallback, useState } from "react";
import type { Chapter, Source } from "../_types";

interface UseChaptersOptions {
  uuid: string;
  /** Aus useSources. Beim Verschieben einer Datei aendert sich deren Kapitel. */
  setSources: (updater: (prev: Source[]) => Source[]) => void;
}

/** Kapitel des Quellenbereichs: anlegen, umbenennen, verschieben, loeschen und
 *  Dateien zuordnen.
 *
 *  Anlegen und Umbenennen werfen bei Fehlern, weil dabei jemand tippt und einen
 *  abgelehnten Namen sehen muss. Die uebrigen Wege schlucken den Fehler wie
 *  Loeschen und erneut versuchen bei den Quellen.
 */
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
      // Die Dateien darin bleiben, sie stehen danach ohne Kapitel.
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
      // Der Server schickt die neue Reihenfolge zurueck. Selbst tauschen waere
      // eine zweite Wahrheit, die frueher oder spaeter abweicht.
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
