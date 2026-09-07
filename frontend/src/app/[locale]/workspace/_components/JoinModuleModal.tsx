"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import JoinSection from "./JoinSection";

interface JoinModuleModalProps {
  onClose: () => void;
}

/** One dialog for joining by link or code, the work happens in JoinSection. */
export default function JoinModuleModal({ onClose }: JoinModuleModalProps) {
  const t = useTranslations("workspace.list");
  const labels = useWorkspaceLabel();

  return (
    <Modal open onClose={onClose} title={t("joinTitle", { label: labels.singular })} size="sm">
      <JoinSection onDone={onClose} />
    </Modal>
  );
}
