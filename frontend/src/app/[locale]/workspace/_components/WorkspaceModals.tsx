"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLocale, useTranslations } from "next-intl";
import StatsModal from "./StatsModal";
import EditWorkspaceModal from "./EditWorkspaceModal";
import LinksModal from "./LinksModal";
import ParticipantsModal from "./ParticipantsModal";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
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
  onSubmitEdit: (title: string, description: string) => Promise<boolean>;
  showLinks: boolean;
  onCloseLinks: () => void;
  links: AccessLink[];
  onLinkCreated: (link: AccessLink) => void;
  onRequestDeleteLink: (link: AccessLink) => void;
  deleteConfirm: boolean;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
  deleting: boolean;
  deleteParticipantCount: number | null;
  deleteLinkConfirm: AccessLink | null;
  onCancelDeleteLink: () => void;
  onConfirmDeleteLink: () => void;
  deletingLink: boolean;
}

export default function WorkspaceModals(props: WorkspaceModalsProps) {
  const {
    workspace,
    showStats, onCloseStats,
    showParticipants, onCloseParticipants, onRolesChanged,
    editOpen, onCloseEdit, onSubmitEdit,
    showLinks, onCloseLinks, links, onLinkCreated, onRequestDeleteLink,
    deleteConfirm, onCancelDelete, onConfirmDelete, deleting, deleteParticipantCount,
    deleteLinkConfirm, onCancelDeleteLink, onConfirmDeleteLink, deletingLink,
  } = props;

  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const labels = useWorkspaceLabel();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return createPortal(
    <>
      {showStats && (
        <StatsModal workspaceUuid={workspace.uuid} moduleTitle={workspace.title} onClose={onCloseStats} />
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
          onClose={onCloseEdit}
          onSubmit={onSubmitEdit}
        />
      )}
      {showLinks && (
        <LinksModal
          workspaceUuid={workspace.uuid}
          links={links}
          onClose={onCloseLinks}
          onCreated={onLinkCreated}
          onRequestDelete={onRequestDeleteLink}
        />
      )}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteTitle", { label: labels.singular })}</h3>
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
      {deleteLinkConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-xl shadow-xl max-w-sm w-full p-6">
            <h3 className="text-base font-semibold mb-2">{t("deleteLinkTitle")}</h3>
            <p className="text-sm text-foreground-soft mb-1">
              <span className="font-medium">...{deleteLinkConfirm.code}</span> - {deleteLinkConfirm.expires_at ? t("linkValidUntil", { date: new Date(deleteLinkConfirm.expires_at).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" }) }) : t("linkUnlimited")}
            </p>
            <p className="text-sm text-error mb-6">{t("deleteLinkWarning")}</p>
            <div className="flex gap-3 justify-end">
              <button onClick={onCancelDeleteLink} disabled={deletingLink} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg disabled:opacity-50">{t("cancel")}</button>
              <button onClick={onConfirmDeleteLink} disabled={deletingLink} className="px-4 py-2 text-sm btn-danger rounded-lg disabled:opacity-50">{deletingLink ? "..." : t("delete")}</button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body
  );
}
