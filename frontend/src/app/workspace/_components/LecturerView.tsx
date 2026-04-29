"use client";

import { useCallback, useEffect, useState } from "react";
import { Files } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import CreateWorkspaceModal from "./CreateWorkspaceModal";
import WorkspaceTable from "./WorkspaceTable";
import UpcomingDeadlinesWidget from "./UpcomingDeadlinesWidget";
import type { AccessLink, KiTutorWorkspace } from "../_shared";

export default function LecturerView() {
  const [workspaces, setModules] = useState<KiTutorWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/workspaces", { credentials: "include" });
      if (res.ok) setModules(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadModules().finally(() => setLoading(false));
  }, [loadModules]);

  useEffect(() => {
    const needsPoll = workspaces.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(loadModules, 3000);
    return () => clearInterval(id);
  }, [workspaces, loadModules]);

  async function handleToggleActive(uuid: string, newVal: boolean) {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: newVal }),
      });
      if (res.ok) {
        setModules((prev) => prev.map((m) => m.uuid === uuid ? { ...m, is_active: newVal } : m));
      }
    } catch { /* ignore */ }
  }

  async function handleDelete(uuid: string) {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        setModules((prev) => prev.filter((m) => m.uuid !== uuid));
      }
    } catch { /* ignore */ }
  }

  async function handleEdit(uuid: string, newTitle: string, newDescription: string): Promise<boolean> {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle, description: newDescription }),
      });
      if (res.ok) {
        setModules((prev) => prev.map((m) => m.uuid === uuid ? { ...m, title: newTitle, description: newDescription || null } : m));
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }

  function handleLinksChanged(uuid: string, links: AccessLink[]) {
    setModules((prev) =>
      prev.map((m) => m.uuid === uuid ? { ...m, access_links: links } : m)
    );
  }

  return (
    <>
      {showCreate && (
        <CreateWorkspaceModal
          onClose={() => setShowCreate(false)}
          onCreated={(m) => setModules((prev) => [m, ...prev])}
        />
      )}

      <div className="px-4 sm:px-6 md:px-8 pt-6 pb-20 lg:pt-15 lg:pb-30">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-3xl font-bold mb-10 lg:mb-16">KI-Internationalisierung von Studiengängen</h1>

          <div className="mb-12">
            <UpcomingDeadlinesWidget />
          </div>

          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg md:text-xl font-semibold">Meine Workspaces</h2>
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              aria-label="Neuer Workspace"
              className="whitespace-nowrap rounded-lg text-sm font-medium btn-primary w-9 h-9 flex items-center justify-center text-lg md:w-auto md:h-auto md:px-4 md:py-2 md:text-sm"
            >
              <span className="md:hidden">+</span>
              <span className="hidden md:inline">+ Neuer Workspace</span>
            </button>
          </div>

          {loading ? (
            <div className="flex items-center justify-center min-h-[60vh]">
              <Spinner size="lg" />
            </div>
          ) : workspaces.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20" style={{ color: "var(--muted)" }}>
              <Files size={40} weight="duotone" className="mb-3 opacity-40" />
              <p className="text-base">Noch keine Workspaces vorhanden.</p>
              <p className="text-sm mt-1">Erstelle deinen ersten Workspace mit dem Button oben.</p>
            </div>
          ) : (
            <div className="mt-3 md:mt-10">
              <WorkspaceTable
                workspaces={workspaces}
                onToggleActive={handleToggleActive}
                onDelete={handleDelete}
                onEdit={handleEdit}
                onLinksChanged={handleLinksChanged}
              />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
