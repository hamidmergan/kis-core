"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTopLoader } from "nextjs-toploader";
import type { AccessLink, KiTutorWorkspace } from "../_shared";

interface UseWorkspaceActionsOptions {
  workspace: KiTutorWorkspace;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export function useWorkspaceActions({ workspace, onToggleActive, onDelete, onLinksChanged }: UseWorkspaceActionsOptions) {
  const router = useRouter();
  const loader = useTopLoader();

  const [toggling, setToggling] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showAddLink, setShowAddLink] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteLinkConfirm, setDeleteLinkConfirm] = useState<AccessLink | null>(null);
  const [deletingLink, setDeletingLink] = useState(false);
  const [editOpen, setEditOpen] = useState(false);

  const links = workspace.access_links ?? [];
  const moduleHref = `/workspace/${workspace.uuid}`;

  const handleOpen = () => { loader.start(); router.push(moduleHref); };
  const handlePrefetch = () => router.prefetch(moduleHref);

  async function handleToggle(newVal: boolean) {
    setToggling(true);
    await onToggleActive(workspace.uuid, newVal);
    setToggling(false);
  }

  async function handleDeleteConfirm() {
    setDeleting(true);
    await onDelete(workspace.uuid);
    setDeleteConfirm(false);
    setDeleting(false);
  }

  async function handleDeleteLinkConfirm() {
    if (!deleteLinkConfirm) return;
    setDeletingLink(true);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${workspace.uuid}/access-links/${deleteLinkConfirm.id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (res.ok) {
        onLinksChanged(workspace.uuid, links.filter((l) => l.id !== deleteLinkConfirm.id));
      }
      setDeleteLinkConfirm(null);
    } finally {
      setDeletingLink(false);
    }
  }

  function handleLinkCreated(newLink: AccessLink) {
    onLinksChanged(workspace.uuid, [...links, newLink]);
  }

  return {
    links, moduleHref,
    toggling, expanded, setExpanded,
    showStats, setShowStats,
    showAddLink, setShowAddLink,
    showMenu, setShowMenu,
    deleteConfirm, setDeleteConfirm, deleting,
    deleteLinkConfirm, setDeleteLinkConfirm, deletingLink,
    editOpen, setEditOpen,
    handleOpen, handlePrefetch,
    handleToggle, handleDeleteConfirm, handleDeleteLinkConfirm, handleLinkCreated,
  };
}
