"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import StatsModal from "./StatsModal";
import EditModuleModal from "./EditModuleModal";
import AddLinkModal from "./AddLinkModal";
import type { AccessLink, KiTutorModule } from "../_shared";

interface ModuleModalsProps {
  module: KiTutorModule;
  showStats: boolean;
  onCloseStats: () => void;
  editOpen: boolean;
  onCloseEdit: () => void;
  onSubmitEdit: (title: string, description: string) => Promise<boolean>;
  showAddLink: boolean;
  onCloseAddLink: () => void;
  onLinkCreated: (link: AccessLink) => void;
  deleteConfirm: boolean;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
  deleting: boolean;
  deleteLinkConfirm: AccessLink | null;
  onCancelDeleteLink: () => void;
  onConfirmDeleteLink: () => void;
  deletingLink: boolean;
}

export default function ModuleModals(props: ModuleModalsProps) {
  const {
    module,
    showStats, onCloseStats,
    editOpen, onCloseEdit, onSubmitEdit,
    showAddLink, onCloseAddLink, onLinkCreated,
    deleteConfirm, onCancelDelete, onConfirmDelete, deleting,
    deleteLinkConfirm, onCancelDeleteLink, onConfirmDeleteLink, deletingLink,
  } = props;

  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <>
      {showStats && (
        <StatsModal moduleUuid={module.uuid} moduleTitle={module.title} onClose={onCloseStats} />
      )}
      {editOpen && (
        <EditModuleModal
          currentTitle={module.title}
          currentDescription={module.description ?? ""}
          onClose={onCloseEdit}
          onSubmit={onSubmitEdit}
        />
      )}
      {showAddLink && (
        <AddLinkModal moduleUuid={module.uuid} onClose={onCloseAddLink} onCreated={onLinkCreated} />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Workspace löschen?</h3>
            <p className="text-sm text-gray-600 mb-1"><span className="font-medium">{module.title}</span></p>
            <p className="text-sm text-red-600 mb-6">Der Workspace und alle zugehörigen Daten werden unwiderruflich gelöscht.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={onCancelDelete} disabled={deleting} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={onConfirmDelete} disabled={deleting} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deleting ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}
      {deleteLinkConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">Einschreibelink löschen?</h3>
            <p className="text-sm text-gray-600 mb-1">
              <span className="font-medium">...{deleteLinkConfirm.code}</span> – {deleteLinkConfirm.expires_at ? `gültig bis ${new Date(deleteLinkConfirm.expires_at).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" })}` : "unbegrenzt gültig"}
            </p>
            <p className="text-sm text-red-600 mb-6">Der Link wird ungültig. Bereits eingeschriebene Studierende behalten ihren Zugang.</p>
            <div className="flex gap-3 justify-end">
              <button onClick={onCancelDeleteLink} disabled={deletingLink} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50">Abbrechen</button>
              <button onClick={onConfirmDeleteLink} disabled={deletingLink} className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg disabled:opacity-50">{deletingLink ? "..." : "Löschen"}</button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body
  );
}
