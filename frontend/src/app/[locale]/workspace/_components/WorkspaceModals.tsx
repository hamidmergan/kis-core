"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslations } from "next-intl";
import ModuleStatsModal from "./ModuleStatsModal";
import EditWorkspaceModal from "./EditWorkspaceModal";
import LinksModal from "./LinksModal";
import ParticipantsModal from "./ParticipantsModal";
import type { AccessLink, KiTutorWorkspace } from "../_shared";

interface WorkspaceModalsProps {
  workspace: KiTutorWorkspace;
  showStats: boolean;
  onCloseStats: () => void;
  showParticipants: boolean;
  onCloseParticipants: () => void;
  onRolesChanged: () => void;
  editOpen: boolean;
  onCloseEdit: () => void;
  onSubmitEdit: (title: string, description: string, tourModule: boolean | null) => Promise<boolean>;
  showLinks: boolean;
  onCloseLinks: () => void;
  links: AccessLink[];
  onLinksChanged: (links: AccessLink[]) => void;
  deleteConfirm: boolean;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
  deleting: boolean;
  deleteParticipantCount: number | null;
}

export default function WorkspaceModals(props: WorkspaceModalsProps) {
  const {
    workspace,
    showStats, onCloseStats,
    showParticipants, onCloseParticipants, onRolesChanged,
    editOpen, onCloseEdit, onSubmitEdit,
    showLinks, onCloseLinks, links, onLinksChanged,
    deleteConfirm, onCancelDelete, onConfirmDelete, deleting, deleteParticipantCount,
  } = props;

  const t = useTranslations("workspace.list");
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <>
      {showStats && (
        <ModuleStatsModal
          workspaceUuid={workspace.uuid}
          moduleTitle={workspace.title}
          onClose={onCloseStats}
        />
      )}
      {showParticipants && (
        <ParticipantsModal
          workspaceUuid={workspace.uuid}
          onClose={onCloseParticipants}
          onRolesChanged={onRolesChanged}
        />
      )}
      {editOpen && (
        <EditWorkspaceModal
          currentTitle={workspace.title}
          currentDescription={workspace.description ?? ""}
          canBeTourModule={!!workspace.is_demo_workspace}
          currentTourModule={!!workspace.is_tour_module}
          onClose={onCloseEdit}
          onSubmit={onSubmitEdit}
        />
      )}
      {showLinks && (
        <LinksModal
          workspaceUuid={workspace.uuid}
          links={links}
          onClose={onCloseLinks}
          onLinksChanged={onLinksChanged}
        />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteTitle", { label: "Workspace" })}</h3>
            <p className="text-sm text-foreground-soft mb-1"><span className="font-medium">{workspace.title}</span></p>
            <p className="text-sm text-error mb-1">{t("deleteWarning")}</p>
            {!!deleteParticipantCount && (
              <p className="text-sm text-error mb-1">
                {t("deleteParticipantsWarning", { count: deleteParticipantCount })}
              </p>
            )}
            <div className="flex gap-3 justify-end mt-5">
              <button onClick={onCancelDelete} disabled={deleting} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50">{t("cancel")}</button>
              <button onClick={onConfirmDelete} disabled={deleting} className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50">{deleting ? "..." : t("delete")}</button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body
  );
}
