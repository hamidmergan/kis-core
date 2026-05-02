"use client";

import { useTranslations } from "next-intl";
import {
  ArrowRight,
  CaretRight,
  Plus,
} from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import LinkRow from "./LinkRow";
import WorkspaceMenu from "./WorkspaceMenu";
import WorkspaceModals from "./WorkspaceModals";
import { MAX_ACCESS_LINKS, type AccessLink, type KiTutorWorkspace } from "../_shared";
import { useWorkspaceActions } from "../_hooks/useWorkspaceActions";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";

interface WorkspaceTableRowProps {
  workspace: KiTutorWorkspace;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export default function WorkspaceTableRow({
  workspace,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: WorkspaceTableRowProps) {
  const t = useTranslations("workspace.list");
  const a = useWorkspaceActions({ workspace, onToggleActive, onDelete, onLinksChanged });
  const labels = useWorkspaceLabel();

  return (
    <>
      <WorkspaceModals
        workspace={workspace}
        showStats={a.showStats} onCloseStats={() => a.setShowStats(false)}
        editOpen={a.editOpen} onCloseEdit={() => a.setEditOpen(false)}
        onSubmitEdit={(t, d) => onEdit(workspace.uuid, t, d)}
        showAddLink={a.showAddLink} onCloseAddLink={() => a.setShowAddLink(false)} onLinkCreated={a.handleLinkCreated}
        deleteConfirm={a.deleteConfirm} onCancelDelete={() => a.setDeleteConfirm(false)}
        onConfirmDelete={a.handleDeleteConfirm} deleting={a.deleting}
        deleteLinkConfirm={a.deleteLinkConfirm} onCancelDeleteLink={() => a.setDeleteLinkConfirm(null)}
        onConfirmDeleteLink={a.handleDeleteLinkConfirm} deletingLink={a.deletingLink}
      />

      <tr
        className={`border-b border-border-soft transition-colors ${a.expanded ? "bg-surface" : "hover:bg-surface"}`}
        onMouseEnter={a.handlePrefetch}
      >
        <td className="px-4 py-3 cursor-pointer" onClick={() => a.setExpanded(!a.expanded)}>
          <button
            type="button"
            onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.setExpanded(!a.expanded); }}
            title={a.expanded ? t("collapse") : t("expand")}
            className="w-6 h-6 flex items-center justify-center text-[var(--muted)] hover:text-kb transition"
          >
            <CaretRight size={12} weight="bold" className={`transition-transform ${a.expanded ? "rotate-90" : ""}`} />
          </button>
        </td>
        <td
          className="px-4 py-3 cursor-pointer w-full max-w-0"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          <span className="font-medium text-foreground-soft truncate block" title={workspace.title}>{workspace.title}</span>
        </td>
        <td
          className="px-4 py-3 text-right tabular-nums text-foreground-soft cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          {workspace.source_count}
        </td>
        <td
          className="px-4 py-3 text-right tabular-nums text-foreground-soft cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          {a.links.length}
        </td>
        <td
          className="px-4 py-3 cursor-pointer"
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
                  workspace.is_active ? "translate-x-[18px]" : "translate-x-0.5"
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
        <td className="px-4 py-3">
          <div className="flex justify-center">
            <WorkspaceMenu
              onStats={() => a.setShowStats(true)}
              onEdit={() => a.setEditOpen(true)}
              onDelete={() => a.setDeleteConfirm(true)}
            />
          </div>
        </td>
        <td
          className="px-4 py-3 cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
        >
          <div className="flex justify-end">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.handleOpen(); }}
              title={t("openWorkspace", { label: labels.singular })}
            >
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </td>
      </tr>

      {/* Expanded row */}
      {a.expanded && (
        <tr className="bg-surface">
          <td colSpan={7} className="px-4 pb-4 pt-0 pl-11">
            <div className="flex flex-col gap-3 max-w-full break-words">
              {workspace.description && (
                <p className="text-[13px] leading-relaxed break-words" style={{ color: "var(--muted)" }}>
                  {workspace.description}
                </p>
              )}
              {a.links.map((link) => (
                <LinkRow key={link.id} link={link} onRequestDelete={a.setDeleteLinkConfirm} />
              ))}
              {a.links.length >= MAX_ACCESS_LINKS ? (
                <p className="text-xs self-start mt-0.5" style={{ color: "var(--muted)" }}>
                  {t("maxLinksReached", { n: MAX_ACCESS_LINKS })}
                </p>
              ) : (
                <button
                  onClick={() => a.setShowAddLink(true)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-soft hover:text-kb transition-colors self-start mt-0.5"
                >
                  <Plus size={12} weight="bold" />
                  {t("newLink")}
                </button>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
