"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import WorkspaceMenu from "./WorkspaceMenu";
import WorkspaceModals from "./WorkspaceModals";
import { type AccessLink, type KiTutorWorkspace } from "../_shared";
import { useWorkspaceActions } from "../_hooks/useWorkspaceActions";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

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
  const a = useWorkspaceActions({ workspace, onToggleActive, onDelete, onLinksChanged });
  const labels = useWorkspaceLabel();
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
        links={a.links} onLinkCreated={a.handleLinkCreated} onRequestDeleteLink={a.setDeleteLinkConfirm}
        deleteConfirm={a.deleteConfirm} onCancelDelete={() => a.setDeleteConfirm(false)}
        onConfirmDelete={a.handleDeleteConfirm} deleting={a.deleting}
        deleteLinkConfirm={a.deleteLinkConfirm} onCancelDeleteLink={() => a.setDeleteLinkConfirm(null)}
        onConfirmDeleteLink={a.handleDeleteLinkConfirm} deletingLink={a.deletingLink}
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
            {/* The row looks the same whether it is owned or tutored, so say which. */}
            {!isOwner && (
              <span
                className="flex-shrink-0 text-2xs font-medium px-1.5 py-0.5 rounded-full"
                style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              >
                {t("roleTutor")}
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
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={workspace.is_active}
              aria-label={workspace.is_active ? t("deactivate", { label: labels.singular }) : t("activate", { label: labels.singular })}
              onClick={(e) => { e.stopPropagation(); a.handleToggle(!workspace.is_active); }}
              disabled={a.toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full border-2 border-transparent transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2 enabled:hover:border-kb"
              style={{ backgroundColor: workspace.is_active ? "var(--kb)" : "var(--border)" }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  workspace.is_active ? "translate-x-[1.125rem]" : "translate-x-0.5"
                }`}
              />
            </button>
            <span
              className="text-xs font-medium"
              style={{ color: workspace.is_active ? "var(--kb)" : "var(--muted)" }}
            >
              {workspace.is_active ? t("active") : t("inactive")}
            </span>
          </div>
        </td>
        <td className="pl-20 pr-4 py-3">
          <div className="flex justify-center">
            <WorkspaceMenu
              onStats={() => a.setShowStats(true)}
              onParticipants={() => setShowParticipants(true)}
              onLinks={() => a.setShowLinks(true)}
              onEdit={() => a.setEditOpen(true)}
              onDelete={isOwner ? () => a.setDeleteConfirm(true) : undefined}
            />
          </div>
        </td>
      </tr>
    </>
  );
}
