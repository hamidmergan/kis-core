"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { checkAuthStatus } from "@/lib/auth";
import type { AuthStatus } from "@/types";
import type { WorkspaceDetail, Source } from "../_types";
import type { Note } from "../_components/studio/NotesStudio";

interface WorkspaceSettings {
  chat_lang: "de" | "en";
  studio_enabled: boolean;
  language_training_active: boolean;
}

interface UseWorkspaceInitOptions {
  uuid: string;
  setSources: (srcs: Source[]) => void;
  setSelectedSourceIds: (ids: string[]) => void;
  setWorkspaceDetail: (m: WorkspaceDetail) => void;
  setNotes: (notes: Note[]) => void;
  loadMessages: () => Promise<void>;
  onSettingsLoaded: (s: WorkspaceSettings) => void;
}

export function useWorkspaceInit(opts: UseWorkspaceInitOptions) {
  const { uuid, setSources, setSelectedSourceIds, setWorkspaceDetail, setNotes, loadMessages, onSettingsLoaded } = opts;
  const router = useRouter();

  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        const authData = await checkAuthStatus();
        if (cancelled) return;
        if (!authData.authenticated) { router.push("/login"); return; }
        setAuth(authData);

        const modRes = await fetch(`/api/ai-assistant/workspaces/${uuid}`, { credentials: "include" });
        if (cancelled) return;
        if (!modRes.ok) { router.push("/"); return; }
        const mod: WorkspaceDetail = await modRes.json();
        setWorkspaceDetail(mod);

        const srcs: Source[] = mod.sources ?? [];
        setSources(srcs);
        setSelectedSourceIds(restoreSelectedSources(uuid, srcs));

        await loadMessages();

        const settingsRes = await fetch(`/api/ai-assistant/workspaces/${uuid}/settings`, { credentials: "include" });
        if (!cancelled && settingsRes.ok) {
          const s: Partial<WorkspaceSettings> = await settingsRes.json();
          onSettingsLoaded({
            chat_lang: s.chat_lang ?? "de",
            studio_enabled: s.studio_enabled ?? true,
            language_training_active: s.language_training_active ?? false,
          });
        }

        const notesRes = await fetch(`/api/ai-assistant/workspaces/${uuid}/notes`, { credentials: "include" });
        if (!cancelled && notesRes.ok) setNotes(await notesRes.json());

        if (!cancelled) setInitialized(true);
      } catch {
        if (!cancelled) router.push("/");
      }
    }

    init();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uuid, router, loadMessages]);

  return { auth, initialized };
}

// Restore previously selected sources from sessionStorage, fallback to all ready.
// "Fully ready" excludes sources still running page/doc summaries - selecting
// those would feed the chat empty context (see SourcesPanel.tsx).
function restoreSelectedSources(uuid: string, srcs: Source[]): string[] {
  const storageKey = `kis-selected-sources-${uuid}`;
  const isFullyReady = (s: Source) => s.status === "ready" && !s.progress;
  const allReady = () => srcs.filter(isFullyReady).map((s) => s.uuid);
  const saved = sessionStorage.getItem(storageKey);
  if (!saved) return allReady();
  try {
    const savedIds: string[] = JSON.parse(saved);
    const validIds = savedIds.filter((id) => srcs.some((s) => s.uuid === id && isFullyReady(s)));
    return validIds.length > 0 ? validIds : allReady();
  } catch {
    return allReady();
  }
}
