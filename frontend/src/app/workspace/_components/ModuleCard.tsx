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
import ModuleModals from "./ModuleModals";
import { MAX_ACCESS_LINKS, type AccessLink, type KiTutorModule } from "../_shared";
import { useModuleActions } from "../_hooks/useModuleActions";

interface ModuleCardProps {
  module: KiTutorModule;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onEdit: (uuid: string, newTitle: string, newDescription: string) => Promise<boolean>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export default function ModuleCard({
  module,
  onToggleActive,
  onDelete,
  onEdit,
  onLinksChanged,
}: ModuleCardProps) {
  const a = useModuleActions({ module, onToggleActive, onDelete, onLinksChanged });

  return (
    <>
      <ModuleModals
        module={module}
        showStats={a.showStats} onCloseStats={() => a.setShowStats(false)}
        editOpen={a.editOpen} onCloseEdit={() => a.setEditOpen(false)}
        onSubmitEdit={(t, d) => onEdit(module.uuid, t, d)}
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
            className="w-7 h-7 flex items-center justify-center hover:opacity-60 transition-opacity flex-shrink-0"
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
            <div className="text-[15px] font-semibold text-foreground break-words">{module.title}</div>
          </button>
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-3 pl-[52px] pr-2 pb-4 flex-wrap">
          <div className="flex items-center gap-2">
            <button
              type="button"
              role="switch"
              aria-checked={module.is_active}
              aria-label={module.is_active ? "Workspace deaktivieren" : "Workspace aktivieren"}
              onClick={() => a.handleToggle(!module.is_active)}
              disabled={a.toggling}
              className="relative inline-flex h-5 w-9 flex-shrink-0 items-center rounded-full transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-offset-2"
              style={{ backgroundColor: module.is_active ? "var(--kb)" : "var(--border)" }}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform ${
                  module.is_active ? "translate-x-[18px]" : "translate-x-0.5"
                }`}
              />
            </button>
            <span className="text-xs font-medium" style={{ color: module.is_active ? "var(--kb)" : "var(--muted)" }}>
              {module.is_active ? "Aktiv" : "Inaktiv"}
            </span>
          </div>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{module.source_count} Quellen</span>
          <span className="text-xs" style={{ color: "var(--muted)" }}>{a.links.length} Links</span>
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <IconButton onClick={() => a.setShowMenu(!a.showMenu)} title="Mehr">
                <DotsThreeVertical size={13} weight="bold" />
              </IconButton>
              {a.showMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => a.setShowMenu(false)} />
                  <div
                    className="absolute right-0 top-9 z-50 rounded-xl py-1"
                    style={{
                      backgroundColor: "var(--surface)",
                      border: "1px solid var(--border)",
                      minWidth: 220,
                      boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
                    }}
                  >
                    <button type="button" onClick={() => { a.setShowMenu(false); a.setShowStats(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ color: "var(--foreground)" }}>
                      <ChartBar size={16} />
                      Statistik
                    </button>
                    <button type="button" onClick={() => { a.setShowMenu(false); a.setEditOpen(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ color: "var(--foreground)" }}>
                      <PencilSimple size={16} />
                      Bearbeiten
                    </button>
                    <button type="button" onClick={() => { a.setShowMenu(false); a.setDeleteConfirm(true); }}
                      className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-[var(--surface-dim)] transition-colors"
                      style={{ color: "rgb(185, 28, 28)" }}>
                      <Trash size={16} />
                      Löschen
                    </button>
                  </div>
                </>
              )}
            </div>
            <IconButton onClick={a.handleOpen} title="Workspace öffnen">
              <ArrowRight size={13} weight="bold" />
            </IconButton>
          </div>
        </div>

        {a.expanded && (
          <div className="flex flex-col gap-3 pl-[52px] pr-2 pb-5">
            {module.description && (
              <p className="text-[13px] leading-relaxed break-words" style={{ color: "var(--muted)" }}>
                {module.description}
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
