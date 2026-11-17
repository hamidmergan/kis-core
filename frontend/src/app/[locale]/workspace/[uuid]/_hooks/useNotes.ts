"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { _formatApiError } from "../_utils";
import type { Note } from "../_components/studio/NotesStudio";
import type { SourceRef } from "../_types";

interface UseNotesOptions {
  uuid: string;
}

export interface AddNoteExtras {
  sourcePages?: SourceRef[];
  popupSelection?: { uuid: string; page: number; text: string } | null;
  autoTitle?: boolean;
}

export function useNotes({ uuid }: UseNotesOptions) {
  const t = useTranslations("workspace.detail.errors");
  const [notes, setNotes] = useState<Note[]>([]);
  const [pendingTitleIds, setPendingTitleIds] = useState<Set<number>>(new Set());

  // False once the page is left, the title poll would otherwise ask on for two minutes.
  const aliveRef = useRef(false);
  useEffect(() => {
    aliveRef.current = true;
    return () => { aliveRef.current = false; };
  }, []);

  const loadNotes = useCallback(async () => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes`, { credentials: "include" });
      if (res.ok) setNotes(await res.json());
    } catch { /* the list stays as it is */ }
  }, [uuid]);

  const pollForTitle = useCallback(async (noteId: number) => {
    setPendingTitleIds((prev) => { const next = new Set(prev); next.add(noteId); return next; });
    const clear = () => setPendingTitleIds((prev) => { const next = new Set(prev); next.delete(noteId); return next; });
    // ~120s window covers slow LLM providers (myLab/Ollama cold start).
    const delays = [2000, 3000, 4000, 6000, 10000, 15000, 25000, 25000, 30000];
    for (const wait of delays) {
      await new Promise((r) => setTimeout(r, wait));
      if (!aliveRef.current) return;
      try {
        const r = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes`, { credentials: "include" });
        if (!r.ok) continue;
        const fresh = await r.json();
        const updated = fresh.find((n: { id: number; title?: string | null }) => n.id === noteId);
        if (updated?.title) {
          setNotes((cur) => cur.map((n) => n.id === noteId ? { ...n, title: updated.title } : n));
          clear();
          return;
        }
      } catch { /* keep polling */ }
    }
    clear();
  }, [uuid]);

  const addNote = useCallback(async (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => {
    const autoTitle = extras?.autoTitle ?? true;
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          source_uuids: sourceUuids ?? null,
          source_pages: extras?.sourcePages ?? null,
          popup_selection: extras?.popupSelection ?? null,
          auto_title: autoTitle,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        alert(_formatApiError(data) ?? t("noteSaveFailed"));
        return;
      }
      const note = await res.json();
      setNotes((prev) => [note, ...prev]);
      if (autoTitle && !note.title) pollForTitle(note.id);
    } catch { /* ignore */ }
  }, [uuid, pollForTitle, t]);

  const deleteNote = useCallback(async (noteId: number) => {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes/${noteId}`, {
        method: "DELETE", credentials: "include",
      });
      if (res.ok) setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch { /* ignore */ }
  }, [uuid]);

  const updateNoteTitle = useCallback(async (noteId: number, title: string | null) => {
    // Only this title goes back on a failure, notes added in the meantime stay.
    const before = notes.find((n) => n.id === noteId)?.title ?? null;
    const setTitle = (value: string | null) =>
      setNotes((cur) => cur.map((n) => n.id === noteId ? { ...n, title: value } : n));
    setTitle(title);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes/${noteId}/title`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) setTitle(before);
    } catch {
      setTitle(before);
    }
  }, [uuid, notes]);

  return {
    notes, setNotes, loadNotes,
    pendingTitleIds,
    addNote, deleteNote, updateNoteTitle,
  };
}
