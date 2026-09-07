"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import LinksSection from "./LinksSection";
import type { AccessLink } from "../_shared";

interface LinksModalProps {
  workspaceUuid: string;
  links: AccessLink[];
  onClose: () => void;
  onLinksChanged: (links: AccessLink[]) => void;
}

/** One dialog for all enrollment links of a course, the work happens in LinksSection. */
export default function LinksModal({
  workspaceUuid,
  links,
  onClose,
  onLinksChanged,
}: LinksModalProps) {
  const t = useTranslations("workspace.list");

  return (
    <Modal open onClose={onClose} title={t("linksTitle")} size="md">
      <LinksSection workspaceUuid={workspaceUuid} links={links} onLinksChanged={onLinksChanged} />
    </Modal>
  );
}
