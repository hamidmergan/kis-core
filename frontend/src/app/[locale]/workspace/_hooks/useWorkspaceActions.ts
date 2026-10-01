"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useNavTransition } from "@/components/ui/useNavTransition";
import type { AccessLink, KiTutorWorkspace } from "../_shared";

interface UseWorkspaceActionsOptions {
  workspace: KiTutorWorkspace;
  onToggleActive: (uuid: string, newVal: boolean) => Promise<void>;
  onToggleFavorite: (uuid: string, newVal: boolean) => Promise<void>;
  onDelete: (uuid: string) => Promise<void>;
  onLinksChanged: (uuid: string, links: AccessLink[]) => void;
}

export function useWorkspaceActions({ workspace, onToggleActive, onToggleFavorite, onDelete, onLinksChanged }: UseWorkspaceActionsOptions) {
  const router = useRouter();
  const { pending: opening, navigate } = useNavTransition();

  const [toggling, setToggling] = useState(false);
  const [favoriting, setFavoriting] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showLinks, setShowLinks] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteParticipantCount, setDeleteParticipantCount] = useState<number | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  const links = workspace.access_links ?? [];
  const moduleHref = `/workspace/${workspace.uuid}`;

  const handleOpen = () => navigate(() => router.push(moduleHref));
  const handlePrefetch = () => router.prefetch(moduleHref);

  async function handleToggle(newVal: boolean) {
    setToggling(true);
    await onToggleActive(workspace.uuid, newVal);
    setToggling(false);
  }

  async function handleToggleFavorite() {
    setFavoriting(true);
    await onToggleFavorite(workspace.uuid, !workspace.is_favorite);
    setFavoriting(false);
  }

  async function handleDeleteClick() {
    setDeleteConfirm(true);
    setDeleteParticipantCount(null);
    try {
      const res = await fetch(`/api/ai-assistant/workspaces/${workspace.uuid}/lecturer-stats`, {
        credentials: "include",
      });
      if (res.ok) {
        const stats = await res.json();
        setDeleteParticipantCount(stats.overview?.total_enrolled ?? 0);
      }
    } catch {
      // Dialog just shows the generic warning without a count.
    }
  }

  async function handleDeleteConfirm() {
    setDeleting(true);
    await onDelete(workspace.uuid);
    setDeleteConfirm(false);
    setDeleting(false);
  }

  function handleLinksChanged(next: AccessLink[]) {
    onLinksChanged(workspace.uuid, next);
  }

  return {
    links, moduleHref,
    toggling,
    favoriting, handleToggleFavorite,
    showStats, setShowStats,
    showLinks, setShowLinks,
    deleteConfirm, setDeleteConfirm, deleting, deleteParticipantCount,
    editOpen, setEditOpen,
    handleOpen, handlePrefetch, opening,
    handleToggle, handleDeleteClick, handleDeleteConfirm, handleLinksChanged,
  };
}
