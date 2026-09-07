"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChartBar } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import ActiveToggle from "./ActiveToggle";
import WorkspaceMenu from "./WorkspaceMenu";
import WorkspaceModals from "./WorkspaceModals";
import { type AccessLink, type KiTutorWorkspace } from "../_shared";
import { useWorkspaceActions } from "../_hooks/useWorkspaceActions";

interface WorkspaceTableRowProps {
  workspace: KiTutorWorkspace;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
  onRolesChanged: () => void;
}

export default function WorkspaceTableRow({
  workspace,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
  onRolesChanged,
}: WorkspaceTableRowProps) {
  const t = useTranslations("workspace.list");
  const tDemo = useTranslations("workspace.demo");
  const a = useWorkspaceActions({ workspace, onToggleActive, onDelete, onLinksChanged });
  const [showParticipants, setShowParticipants] = useState(false);
  // A tutor manages like the owner, only deleting stays with the owner.
  const isOwner = workspace.access === "owner";

  return (
    <>
      <WorkspaceModals
        workspace={workspace}
        showStats={a.showStats} onCloseStats={() => a.setShowStats(false)}
        showParticipants={showParticipants} onCloseParticipants={() => setShowParticipants(false)}
        onRolesChanged={onRolesChanged}
        editOpen={a.editOpen} onCloseEdit={() => a.setEditOpen(false)}
        onSubmitEdit={(t, d) => onEdit(workspace.uuid, t, d)}
        showLinks={a.showLinks} onCloseLinks={() => a.setShowLinks(false)}
        links={a.links} onLinksChanged={a.handleLinksChanged}
        deleteConfirm={a.deleteConfirm} onCancelDelete={() => a.setDeleteConfirm(false)}
        onConfirmDelete={a.handleDeleteConfirm} deleting={a.deleting}
        deleteParticipantCount={a.deleteParticipantCount}
      />

      <tr
        className="border-b border-border-soft transition-colors hover:bg-surface"
        onMouseEnter={a.handlePrefetch}
      >
        <td
          className="px-4 py-3 cursor-pointer w-full max-w-0"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          <span className="font-medium text-foreground-soft truncate flex items-center gap-1.5" title={workspace.title}>
            <span className="truncate">{workspace.title}</span>
            {a.opening && <Spinner size="xs" color="current" className="flex-shrink-0" />}
            {/* The row looks the same whether it is owned or tutored, so say which. */}
            {!isOwner && (
              <span
                className="flex-shrink-0 text-2xs font-medium px-1.5 py-0.5 rounded-full"
                style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              >
                {t("roleTutor")}
              </span>
            )}
            {workspace.is_demo_workspace && (
              <span
                className="flex-shrink-0 text-3xs font-semibold px-1.5 py-0.5 rounded"
                style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
              >
                {tDemo("button")}
              </span>
            )}
          </span>
          {workspace.description && (
            <span className="text-xs truncate block" style={{ color: "var(--muted)" }} title={workspace.description}>
              {workspace.description}
            </span>
          )}
        </td>
        <td
          className="pl-6 pr-4 py-3 text-right tabular-nums text-foreground-soft cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          {workspace.source_count}
        </td>
        <td
          className="pl-20 pr-4 py-3 text-right tabular-nums text-foreground-soft cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          {a.links.length}
        </td>
        <td
          className="pl-20 pr-4 py-3 cursor-pointer"
          onClick={() => !a.toggling && a.handleToggle(!workspace.is_active)}
        >
          <ActiveToggle
            active={workspace.is_active}
            disabled={a.toggling}
            onToggle={(v) => a.handleToggle(v)}
          />
        </td>
        <td className="pl-20 pr-4 py-3">
          <div className="flex items-center justify-center gap-1.5">
            {/* Owner and tutor read the numbers of the whole module here, everybody else only their own. */}
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.setShowStats(true); }}
              title={t("statsOpen")}
              data-testid="workspace-stats"
            >
              <ChartBar size={13} weight="bold" />
            </IconButton>
            <WorkspaceMenu
              onParticipants={() => setShowParticipants(true)}
              onLinks={() => a.setShowLinks(true)}
              onEdit={() => a.setEditOpen(true)}
              onDelete={isOwner ? a.handleDeleteClick : undefined}
            />
          </div>
        </td>
      </tr>
    </>
  );
}
