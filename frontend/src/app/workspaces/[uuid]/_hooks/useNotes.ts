"use client";

import { useCallback, useState } from "react";
import { _formatApiError } from "../_utils";
import type { Note } from "../_components/studio/NotizenStudio";
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
  const [notes, setNotes] = useState<Note[]>([]);
  const [pendingTitleIds, setPendingTitleIds] = useState<Set<number>>(new Set());

  const pollForTitle = useCallback(async (noteId: number) => {
    setPendingTitleIds((prev) => { const next = new Set(prev); next.add(noteId); return next; });
    const clear = () => setPendingTitleIds((prev) => { const next = new Set(prev); next.delete(noteId); return next; });
    const delays = [3000, 4000, 6000, 8000, 10000];
    for (const wait of delays) {
      await new Promise((r) => setTimeout(r, wait));
      try {
        const r = await fetch(`/api/ki-assistent/modules/${uuid}/notes`, { credentials: "include" });
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes`, {
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
        alert(_formatApiError(data) ?? "Notiz konnte nicht gespeichert werden.");
        return;
      }
      const note = await res.json();
      setNotes((prev) => [note, ...prev]);
      if (autoTitle && !note.title) pollForTitle(note.id);
    } catch { /* ignore */ }
  }, [uuid, pollForTitle]);

  const deleteNote = useCallback(async (noteId: number) => {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes/${noteId}`, {
        method: "DELETE", credentials: "include",
      });
      if (res.ok) setNotes((prev) => prev.filter((n) => n.id !== noteId));
    } catch { /* ignore */ }
  }, [uuid]);

  const updateNoteTitle = useCallback(async (noteId: number, title: string | null) => {
    const prev = notes;
    setNotes((cur) => cur.map((n) => n.id === noteId ? { ...n, title } : n));
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}/notes/${noteId}/title`, {
        method: "PATCH", credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) setNotes(prev);
    } catch {
      setNotes(prev);
    }
  }, [uuid, notes]);

  return {
    notes, setNotes,
    pendingTitleIds,
    addNote, deleteNote, updateNoteTitle,
  };
}
