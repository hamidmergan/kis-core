"use client";

import {
  ArrowRight,
  CaretRight,
  ChartBar,
  DotsThreeVertical,
  PencilSimple,
  Plus,
  Trash,
} from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import LinkRow from "./LinkRow";
import WorkspaceModals from "./WorkspaceModals";
import { MAX_ACCESS_LINKS, type AccessLink, type KiTutorWorkspace } from "../_shared";
import { useWorkspaceActions } from "../_hooks/useWorkspaceActions";

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
  const a = useWorkspaceActions({ workspace, onToggleActive, onDelete, onLinksChanged });

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
        className="workspace-row border-t transition-colors"
        style={{
          borderColor: "var(--border)",
          backgroundColor: a.expanded ? "var(--surface)" : undefined,
        }}
        onMouseEnter={a.handlePrefetch}
      >
        <td className="py-5 cursor-pointer" onClick={() => a.setExpanded(!a.expanded)}>
          <div className="flex justify-center">
            <button
              type="button"
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.setExpanded(!a.expanded); }}
              title={a.expanded ? "Zuklappen" : "Aufklappen"}
              className="w-7 h-7 flex items-center justify-center text-[var(--muted)] hover:text-kb transition flex-shrink-0"
            >
              <CaretRight size={13} weight="bold" className={`transition-transform ${a.expanded ? "rotate-90" : ""}`} />
            </button>
          </div>
        </td>
        <td
          className="row-main pr-6 py-5 cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="min-w-0">
            <div className="text-[15px] font-semibold text-foreground truncate">{workspace.title}</div>
          </div>
        </td>
        <td
          className="row-main px-6 py-5 text-[15px] font-medium tabular-nums text-foreground cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {workspace.source_count}
        </td>
        <td
          className="row-main px-6 py-5 text-[15px] font-medium tabular-nums text-foreground cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          {a.links.length}
        </td>
        <td
          className="px-6 py-5 cursor-pointer"
          onClick={() => !a.toggling && a.handleToggle(!workspace.is_active)}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              role="switch"
              aria-checked={workspace.is_active}
              aria-label={workspace.is_active ? "Workspace deaktivieren" : "Workspace aktivieren"}
              onClick={(e) => { e.stopPropagation(); a.handleToggle(!workspace.is_active); }}
              disabled={a.toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2 hover:outline-2 hover:outline-kb"
              style={{
                backgroundColor: workspace.is_active ? "var(--kb)" : "var(--border)",
                ...(workspace.is_active && { boxShadow: "0 0 0 0 var(--kb)" }),
              }}
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
              {workspace.is_active ? "Aktiv" : "Inaktiv"}
            </span>
          </div>
        </td>
        <td
          className="py-5 text-center relative cursor-pointer"
          onClick={() => a.setShowMenu(!a.showMenu)}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex justify-center">
            <IconButton onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.setShowMenu(!a.showMenu); }} title="Mehr">
              <DotsThreeVertical size={13} weight="bold" />
            </IconButton>
          </div>
          {a.showMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => a.setShowMenu(false)} />
              <div
                className="absolute right-2 top-12 z-50 rounded-xl py-1"
                style={{
                  backgroundColor: "var(--surface)",
                  border: "1px solid var(--border)",
                  minWidth: 220,
                  boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                }}
              >
                <button
                  type="button"
                  onClick={() => { a.setShowMenu(false); a.setShowStats(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                  style={{ color: "var(--foreground)" }}
                >
                  <ChartBar size={16} />
                  Statistik
                </button>
                <button
                  type="button"
                  onClick={() => { a.setShowMenu(false); a.setEditOpen(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                  style={{ color: "var(--foreground)" }}
                >
                  <PencilSimple size={16} />
                  Bearbeiten
                </button>
                <button
                  type="button"
                  onClick={() => { a.setShowMenu(false); a.setDeleteConfirm(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                  style={{ color: "rgb(185, 28, 28)" }}
                >
                  <Trash size={16} />
                  Löschen
                </button>
              </div>
            </>
          )}
        </td>
        <td
          className="pr-2 py-5 cursor-pointer"
          onClick={a.handleOpen}
          onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(a.moduleHref, "_blank"); } }}
          onMouseEnter={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = "var(--surface)"; }}
          onMouseLeave={(e) => { if (!a.expanded) (e.currentTarget.parentElement as HTMLElement).style.backgroundColor = ""; }}
        >
          <div className="flex justify-end">
            <IconButton
              onClick={(e: React.MouseEvent) => { e.stopPropagation(); a.handleOpen(); }}
              title="Workspace öffnen"
              className="row-arrow"
            >
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </td>
      </tr>

      {/* Expanded row */}
      {a.expanded && (
        <tr style={{ backgroundColor: "var(--surface)" }}>
          <td colSpan={7} className="pl-11 pr-6 pb-5" style={{ borderTop: "none" }}>
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
          </td>
        </tr>
      )}
    </>
  );
}
