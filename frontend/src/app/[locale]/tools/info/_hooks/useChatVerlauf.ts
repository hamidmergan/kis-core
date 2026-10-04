"use client";

import { useCallback, useEffect, useState } from "react";
import { backendApi } from "@/lib/api";
import type { CampusChatEintrag } from "../_types";

/** The chat list of the person, with rename and delete. */
export function useChatVerlauf() {
  const [chats, setChats] = useState<CampusChatEintrag[]>([]);
  const [loaded, setLoaded] = useState(false);

  const reload = useCallback(async () => {
    try {
      const list = await backendApi.getJson<CampusChatEintrag[]>("/campus/chats");
      setChats(list);
    } catch {
      // The list stays as it was, the chat itself still works.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const rename = useCallback(async (id: number, title: string) => {
    await backendApi.patchJson(`/campus/chats/${id}`, { title });
    setChats((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  }, []);

  const remove = useCallback(async (id: number) => {
    const res = await backendApi.fetch(`/campus/chats/${id}`, { method: "DELETE" });
    if (!res.ok) throw new Error(String(res.status));
    setChats((prev) => prev.filter((c) => c.id !== id));
  }, []);

  /** A chat that just got its first answer moves to the top with its title. */
  const upsertTop = useCallback((entry: CampusChatEintrag) => {
    setChats((prev) => [entry, ...prev.filter((c) => c.id !== entry.id)]);
  }, []);

  return { chats, loaded, reload, rename, remove, upsertTop };
}
