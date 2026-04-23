"use client";

import { useCallback, useEffect, useState } from "react";
import { Files } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import CreateModuleModal from "./CreateModuleModal";
import ModuleTable from "./ModuleTable";
import type { AccessLink, KiTutorModule } from "../_shared";

export default function LecturerView() {
  const [modules, setModules] = useState<KiTutorModule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-assistent/modules", { credentials: "include" });
      if (res.ok) setModules(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    loadModules().finally(() => setLoading(false));
  }, [loadModules]);

  useEffect(() => {
    const needsPoll = modules.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(loadModules, 3000);
    return () => clearInterval(id);
  }, [modules, loadModules]);

  async function handleToggleActive(uuid: string, newVal: boolean) {
    try {
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
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
      const res = await fetch(`/api/ki-assistent/modules/${uuid}`, {
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
        <CreateModuleModal
          onClose={() => setShowCreate(false)}
          onCreated={(m) => setModules((prev) => [m, ...prev])}
        />
      )}

      <div className="mb-3">
        <h1 className="text-3xl font-bold mb-10">Willkommen bei KIS</h1>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">Meine Workspaces</h2>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-primary"
          >
            + Neuer Workspace
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[60vh]">
          <Spinner size="lg" />
        </div>
      ) : modules.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20" style={{ color: "var(--muted)" }}>
          <Files size={40} weight="duotone" className="mb-3 opacity-40" />
          <p className="text-base">Noch keine Workspaces vorhanden.</p>
          <p className="text-sm mt-1">Erstelle deinen ersten Workspace mit dem Button oben.</p>
        </div>
      ) : (
        <div className="mt-6 md:mt-20">
          <ModuleTable
            modules={modules}
            onToggleActive={handleToggleActive}
            onDelete={handleDelete}
            onEdit={handleEdit}
            onLinksChanged={handleLinksChanged}
          />
        </div>
      )}
    </>
  );
}
