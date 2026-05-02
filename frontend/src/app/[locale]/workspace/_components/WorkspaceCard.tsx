"use client";

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

interface WorkspaceCardProps {
  workspace: KiTutorWorkspace;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export default function WorkspaceCard({
  workspace,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: WorkspaceCardProps) {
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

      <div
        className="border-t"
        style={{
          borderColor: "var(--border)",
          backgroundColor: a.expanded ? "var(--surface)" : undefined,
        }}
        onTouchStart={a.handlePrefetch}
      >
        {/* Top row: chevron + title */}
        <div className="flex items-center gap-2 pt-4 pb-2 pl-2">
          <button
            type="button"
            onClick={() => a.setExpanded(!a.expanded)}
            title={a.expanded ? "Zuklappen" : "Aufklappen"}
            className="w-7 h-7 flex items-center justify-center rounded-full transition-colors flex-shrink-0 hover:bg-[var(--surface-dim)] hover:text-kb"
            style={{ color: "var(--muted)" }}
          >
            <CaretRight size={13} weight="bold" className={`transition-transform ${a.expanded ? "rotate-90" : ""}`} />
          </button>
          <button
            type="button"
            onClick={a.handleOpen}
            onAuxClick={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
            className="flex-1 min-w-0 text-left"
          >
            <div className="text-[15px] font-semibold text-foreground break-words">{workspace.title}</div>
          </button>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 pl-[52px] pr-2 pb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={workspace.is_active}
              aria-label={workspace.is_active ? `${labels.singular} deaktivieren` : `${labels.singular} aktivieren`}
              onClick={() => a.handleToggle(!workspace.is_active)}
              disabled={a.toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2"
              style={{ backgroundColor: workspace.is_active ? "var(--kb)" : "var(--border)" }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  workspace.is_active ? "translate-x-[18px]" : "translate-x-0.5"
                }`}
              />
            </button>
            <span className="text-xs font-medium" style={{ color: workspace.is_active ? "var(--kb)" : "var(--muted)" }}>
              {workspace.is_active ? "Aktiv" : "Inaktiv"}
            </span>
          </div>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{workspace.source_count} Quellen</span>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{a.links.length} Links</span>
          <div className="ml-auto flex items-center gap-2">
            <WorkspaceMenu
              onStats={() => a.setShowStats(true)}
              onEdit={() => a.setEditOpen(true)}
              onDelete={() => a.setDeleteConfirm(true)}
            />
            <IconButton onClick={a.handleOpen} title={`${labels.singular} öffnen`}>
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </div>

        {a.expanded && (
          <div className="flex flex-col gap-3 pl-[52px] pr-2 pb-5">
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
                Maximal {MAX_ACCESS_LINKS} Einschreibelinks erreicht. Lösche einen alten Link, um einen neuen zu erstellen.
              </p>
            ) : (
              <button
                onClick={() => a.setShowAddLink(true)}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-soft hover:text-kb transition-colors self-start mt-0.5"
              >
                <Plus size={12} weight="bold" />
                Neuer Link
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}
