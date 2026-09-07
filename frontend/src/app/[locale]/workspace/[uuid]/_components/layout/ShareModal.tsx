"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import ActiveToggle from "../../../_components/ActiveToggle";
import LinksSection from "../../../_components/LinksSection";
import ParticipantsSection from "../../../_components/ParticipantsSection";
import type { AccessLink } from "../../../_shared";

interface ShareModalProps {
  open: boolean;
  workspaceUuid: string;
  /** Active means students can enrol through a link and get in. */
  isActive: boolean;
  onToggleActive: (newVal: boolean) => Promise<void>;
  onClose: () => void;
}

/**
 * Sharing a module: the enrollment links on top, who is in it below.
 *
 * Both blocks are the same components the module list uses, so a change to
 * either shows up in both places. The links are fetched here because a module
 * page never carries them, unlike the list.
 */
export function ShareModal({ open, workspaceUuid, isActive, onToggleActive, onClose }: ShareModalProps) {
  const t = useTranslations("workspace.detail.share");
  const tList = useTranslations("workspace.list");
  const [links, setLinks] = useState<AccessLink[]>([]);
  const [toggling, setToggling] = useState(false);

  async function handleToggleActive(newVal: boolean) {
    setToggling(true);
    try {
      await onToggleActive(newVal);
    } finally {
      setToggling(false);
    }
  }

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/access-links`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && Array.isArray(data)) setLinks(data);
      })
      .catch(() => { /* Ohne Links bleibt der Abschnitt leer und laesst trotzdem einen anlegen. */ });
    return () => { cancelled = true; };
  }, [open, workspaceUuid]);

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="lg">
      <div className="flex items-center justify-between gap-4 mb-2">
        <h3 className="text-sm font-semibold" style={{ color: "var(--foreground)" }}>
          {tList("linksTitle")}
        </h3>
        {/* The switch sits here because active is exactly what an enrolment link is worth. */}
        <ActiveToggle active={isActive} disabled={toggling} onToggle={handleToggleActive} />
      </div>
      <LinksSection workspaceUuid={workspaceUuid} links={links} onLinksChanged={setLinks} />

      <div className="mt-6 pt-5" style={{ borderTop: "1px solid var(--border)" }}>
        <h3 className="text-sm font-semibold mb-2" style={{ color: "var(--foreground)" }}>
          {tList("participantsTitle")}
        </h3>
        <ParticipantsSection workspaceUuid={workspaceUuid} />
      </div>
    </Modal>
  );
}
