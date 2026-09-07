"use client";

import { useRef } from "react";
import { useTranslations } from "next-intl";
import ParticipantsSection from "./ParticipantsSection";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";

interface Props {
  workspaceUuid: string;
  onClose: () => void;
  /** Called after a promotion or demotion, so the list outside can update its icon. */
  onRolesChanged?: () => void;
}

/** Who is in the course and who is a tutor, the work happens in ParticipantsSection. */
export default function ParticipantsModal({ workspaceUuid, onClose, onRolesChanged }: Props) {
  const t = useTranslations("workspace.list");
  const press = useRef(newBackdropPress()).current;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.4)" }}
      {...backdropClose(press, onClose)}
    >
      <div
        className="w-full max-w-lg rounded-xl p-6 shadow-xl max-h-[80vh] overflow-y-auto"
        style={{ backgroundColor: "var(--surface)" }}
      >
        <h2 className="text-lg font-semibold mb-1">{t("participantsTitle")}</h2>
        <ParticipantsSection workspaceUuid={workspaceUuid} onRolesChanged={onRolesChanged} />

        <div className="flex justify-end mt-6">
          <button
            type="button"
            onClick={onClose}
            className="btn-cancel px-4 py-2 rounded-lg text-sm font-medium"
            style={{ backgroundColor: "var(--border)", color: "var(--foreground)" }}
          >
            {t("cancel")}
          </button>
        </div>
      </div>
    </div>
  );
}
