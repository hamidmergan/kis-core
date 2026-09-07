"use client";

/** The whole module in numbers, open to whoever owns or tutors it. */

import Modal from "@/components/ui/Modal";
import { ModulAnsicht } from "@/app/[locale]/admin/_pages/statistik/_modul";

export default function ModuleStatsModal({
  workspaceUuid,
  moduleTitle,
  onClose,
}: {
  workspaceUuid: string;
  moduleTitle: string;
  onClose: () => void;
}) {
  return (
    <Modal open onClose={onClose} title={moduleTitle} size="xl">
      {/* The path with the owner check, not the open one of the admin area. */}
      <ModulAnsicht
        uuid={workspaceUuid}
        pfad={`/api/ai-assistant/workspaces/${workspaceUuid}/module-stats`}
      />
    </Modal>
  );
}
