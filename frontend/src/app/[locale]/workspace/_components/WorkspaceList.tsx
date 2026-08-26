"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Files } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import CreateWorkspaceModal from "./CreateWorkspaceModal";
import WorkspaceTable from "./WorkspaceTable";
import DemoModal from "./DemoModal";
import { useDemoWorkspaces } from "./useDemoWorkspaces";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { canManage, type AccessLink, type KiTutorWorkspace } from "../_shared";

interface Props {
  /** May own workspaces. Controls the create button, nothing else. */
  canCreate: boolean;
}

/** One list for everything the user can reach: workspaces they own, workspaces
 *  they tutor, and workspaces they learn from. Each row carries its own access
 *  level, so a single table can show all three without splitting the page. */
export default function WorkspaceList({ canCreate }: Props) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();
  const [workspaces, setWorkspaces] = useState<KiTutorWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const tDemo = useTranslations("workspace.demo");
  const demo = useDemoWorkspaces();

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/workspaces", { credentials: "include" });
      if (res.ok) setWorkspaces(await res.json());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  useEffect(() => {
    const needsPoll = workspaces.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [workspaces, load]);

  // Only rows the user manages can change, so the optimistic updates below
  // never need to consider student rows.
  async function handleToggleActive(uuid: string, newVal: boolean) {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: newVal }),
      });
      if (res.ok) {
        setWorkspaces((prev) => prev.map((m) => m.uuid === uuid ? { ...m, is_active: newVal } : m));
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
        setWorkspaces((prev) => prev.filter((m) => m.uuid !== uuid));
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
        setWorkspaces((prev) => prev.map((m) => m.uuid === uuid ? { ...m, title: newTitle, description: newDescription || null } : m));
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }

  function handleLinksChanged(uuid: string, links: AccessLink[]) {
    setWorkspaces((prev) =>
      prev.map((m) => m.uuid === uuid ? { ...m, access_links: links } : m)
    );
  }

  async function demoJoin(uuid: string | null) {
    await demo.join(uuid);
    await load();
  }

  async function demoLeave(uuid: string) {
    await demo.leave(uuid);
    await load();
  }

  const heading = workspaces.some((m) => !canManage(m.access))
    ? t("allWorkspaces", { label: labels.plural })
    : t("myWorkspaces", { label: labels.plural });

  return (
    <>
      {showCreate && (
        <CreateWorkspaceModal
          onClose={() => setShowCreate(false)}
          onCreated={(m) => setWorkspaces((prev) => [m, ...prev])}
        />
      )}

      <section>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg md:text-xl font-semibold">{heading}</h2>
          <div className="flex items-center gap-2">
          {demo.items.some((m) => !m.owned) && (
            <button
              type="button"
              data-testid="demo-open"
              onClick={() => setShowDemo(true)}
              className="whitespace-nowrap text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors"
              style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
            >
              {tDemo("button")}
            </button>
          )}
          {canCreate && (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              aria-label={t("createAria", { label: labels.singular })}
              className="whitespace-nowrap rounded-lg text-sm font-medium btn-primary w-9 h-9 flex items-center justify-center text-lg md:w-auto md:h-auto md:px-4 md:py-2 md:text-sm"
            >
              <span className="md:hidden">+</span>
              <span className="hidden md:inline">+ {labels.singular}</span>
            </button>
          )}
          </div>
        </div>

        <DemoModal
          open={showDemo}
          onClose={() => setShowDemo(false)}
          items={demo.items.filter((m) => !m.owned)}
          busy={demo.busy}
          onJoin={demoJoin}
          onLeave={demoLeave}
        />

        {loading ? (
          <div className="flex items-center justify-center min-h-[40vh]">
            <Spinner size="lg" />
          </div>
        ) : workspaces.length === 0 ? (
          <EmptyState
            size="lg"
            icon={<Files size={40} weight="bold" />}
            title={canCreate ? t("emptyTitle", { label: labels.plural }) : t("noEnrollments")}
            text={canCreate ? t("emptyText") : ""}
          />
        ) : (
          <div className="mt-3 md:mt-10">
            <WorkspaceTable
              workspaces={workspaces}
              onToggleActive={handleToggleActive}
              onDelete={handleDelete}
              onEdit={handleEdit}
              onLinksChanged={handleLinksChanged}
              onRolesChanged={load}
              onLeaveDemo={demoLeave}
            />
          </div>
        )}
      </section>
    </>
  );
}
