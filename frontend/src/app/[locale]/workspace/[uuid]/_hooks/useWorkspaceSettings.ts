"use client";

import { useCallback, useEffect, useState } from "react";

export interface WorkspaceSettings {
  chat_lang: "de" | "en";
  studio_enabled: boolean;
  popup_translate_lang: string;
}

/** The per-person settings of a workspace, the defaults count until the stored ones arrive. */
export function useWorkspaceSettings() {
  const [chatLang, setChatLang] = useState<"de" | "en">("de");
  const [studioEnabled, setStudioEnabled] = useState(true);
  // Target language of the selection bar translation, per reading person.
  const [popupTranslateLang, setPopupTranslateLang] = useState<string>("en");

  const applyLoaded = useCallback((s: WorkspaceSettings) => {
    setChatLang(s.chat_lang);
    setStudioEnabled(s.studio_enabled);
    setPopupTranslateLang(s.popup_translate_lang);
  }, []);

  return { chatLang, studioEnabled, setStudioEnabled, popupTranslateLang, setPopupTranslateLang, applyLoaded };
}

/** Stores every change, only after the init so the defaults never overwrite the stored values. */
export function usePersistWorkspaceSettings(
  uuid: string,
  initialized: boolean,
  { chatLang, studioEnabled, popupTranslateLang }: { chatLang: "de" | "en"; studioEnabled: boolean; popupTranslateLang: string },
) {
  useEffect(() => {
    if (!initialized) return;
    fetch(`/api/ai-assistant/workspaces/${uuid}/settings`, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        chat_lang: chatLang,
        studio_enabled: studioEnabled,
        popup_translate_lang: popupTranslateLang,
      }),
    }).catch(() => { /* ignore */ });
  }, [chatLang, studioEnabled, popupTranslateLang, initialized, uuid]);
}
