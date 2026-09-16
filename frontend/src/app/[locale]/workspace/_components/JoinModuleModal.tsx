"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import JoinSection from "./JoinSection";

interface JoinModuleModalProps {
  onClose: () => void;
}

/** One dialog for joining by link or code, the work happens in JoinSection. */
export default function JoinModuleModal({ onClose }: JoinModuleModalProps) {
  const t = useTranslations("workspace.list");

  return (
    <Modal open onClose={onClose} title={t("joinTitle", { label: "Workspace" })} size="sm">
      <JoinSection onDone={onClose} />
    </Modal>
  );
}
