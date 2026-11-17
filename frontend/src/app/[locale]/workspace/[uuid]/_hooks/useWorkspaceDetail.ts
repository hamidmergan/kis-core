"use client";

import { useCallback, useState } from "react";
import type { StaffNoteLink, WorkspaceDetail } from "../_types";

/** The workspace record and the two fields its owner changes from inside the workspace. */
export function useWorkspaceDetail(uuid: string) {
  const [moduleDetail, setWorkspaceDetail] = useState<WorkspaceDetail | null>(null);

  const patch = useCallback((body: Partial<WorkspaceDetail>) =>
    fetch(`/api/ai-assistant/workspaces/${uuid}`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }), [uuid]);

  // Throws so the note editor can say that saving failed.
  const saveStaffNote = useCallback(async (text: string | null, links: StaffNoteLink[]) => {
    const res = await patch({ staff_note_text: text, staff_note_links: links });
    if (!res.ok) throw new Error("save failed");
    setWorkspaceDetail((prev) => (prev ? { ...prev, staff_note_text: text, staff_note_links: links } : prev));
  }, [patch]);

  // The share window flips this, so the module list is not the only way in.
  const toggleActive = useCallback(async (newVal: boolean) => {
    const res = await patch({ is_active: newVal });
    if (!res.ok) return;
    setWorkspaceDetail((prev) => (prev ? { ...prev, is_active: newVal } : prev));
  }, [patch]);

  return { moduleDetail, setWorkspaceDetail, saveStaffNote, toggleActive };
}
