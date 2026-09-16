"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Files } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import CreateWorkspaceModal from "./CreateWorkspaceModal";
import WorkspaceTable from "./WorkspaceTable";
import DemoModal from "./DemoModal";
import DemoHintModal from "./DemoHintModal";
import { DemoInvite } from "./DemoInvite";
import JoinModuleModal from "./JoinModuleModal";
import JoinSection from "./JoinSection";
import { useDemoWorkspaces } from "./useDemoWorkspaces";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import { canManage, type AccessLink, type KiTutorWorkspace } from "../_shared";

interface Props {
  /** May own workspaces. Controls the create button, nothing else. */
  canCreate: boolean;
}

/** One list for owned, tutored and enrolled courses, every row carries its level. */
export default function WorkspaceList({ canCreate }: Props) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();
  const [workspaces, setWorkspaces] = useState<KiTutorWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [showDemo, setShowDemo] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [showHint, setShowHint] = useState(false);
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

  // Only managed rows change, learner rows stay out.
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

  async function handleEdit(uuid: string, newTitle: string, newDescription: string, tourModule: boolean | null): Promise<boolean> {
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${uuid}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTitle,
          description: newDescription,
          ...(tourModule === null ? {} : { is_tour_module: tourModule }),
        }),
      });
      if (res.ok) {
        // The mark sits on exactly one module, so every other one loses it here too.
        setWorkspaces((prev) => prev.map((m) => {
          const rundgang = tourModule === null ? m.is_tour_module
            : m.uuid === uuid ? tourModule
            : tourModule ? false : m.is_tour_module;
          return m.uuid === uuid
            ? { ...m, title: newTitle, description: newDescription || null, is_tour_module: rundgang }
            : { ...m, is_tour_module: rundgang };
        }));
        await demo.reload();
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

  // The safety net for a list that stayed empty, whatever the reason was.
  const demoOffen = demo.items.filter((m) => !m.owned && !m.joined);

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

      {showJoin && <JoinModuleModal onClose={() => setShowJoin(false)} />}

      <section>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg md:text-xl font-semibold">{heading}</h2>
          <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowJoin(true)}
            data-testid="join-open"
            className="whitespace-nowrap rounded-lg text-sm font-medium btn-secondary px-3 py-2 md:px-4"
          >
            {t("joinButton")}
          </button>
          {canCreate && (
            <button
              type="button"
              onClick={() => setShowCreate(true)}
              aria-label={t("createAria", { label: labels.singular })}
              className="whitespace-nowrap rounded-lg text-sm font-medium btn-primary px-3 py-2 md:px-4"
            >
              + {labels.singular}
            </button>
          )}
          </div>
        </div>

        <DemoHintModal
          open={showHint}
          busy={demo.busy !== null}
          onJoin={async () => { await demoJoin(null); setShowHint(false); }}
          onClose={() => setShowHint(false)}
        />

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
            text={canCreate ? t("emptyText") : t("noEnrollmentsText")}
            action={
              <div className="w-full max-w-sm flex flex-col gap-4">
                {!canCreate && <JoinSection compact />}
                {demoOffen.length > 0 && (
                  <DemoInvite onOpen={() => setShowHint(true)} />
                )}
              </div>
            }
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
