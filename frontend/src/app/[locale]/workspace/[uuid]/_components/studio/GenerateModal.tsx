"use client";

import { useRef, useState } from "react";
import { Sparkle } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";
import { InstructionField } from "./InstructionField";

/** The create dialog of mindmap and data table, the same shape the exercise sets have. */
export function GenerateModal({ id, toolName, onClose, onCreate }: {
  id: string;
  toolName: string;
  onClose: () => void;
  onCreate: (instruction: string) => void;
}) {
  const t = useTranslations("workspace.detail.studio.generate");
  const [instruction, setInstruction] = useState("");
  const press = useRef(newBackdropPress()).current;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} {...backdropClose(press, onClose)}>
      <div className="rounded-2xl p-5 w-85 max-h-[85vh] overflow-y-auto" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">{t("modalTitle", { tool: toolName })}</h3>
        <div className="mb-4">
          <InstructionField id={id} value={instruction} onChange={setInstruction}
            label={t("instructionLabel")} placeholder={t("instructionPlaceholder")} />
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={onClose}
            className="btn-cancel px-4 py-2 rounded-full text-xs font-semibold"
            style={{ color: "var(--kb)", backgroundColor: "var(--surface)", border: "2px solid var(--border)" }}>
            {t("cancel")}
          </button>
          <button type="button" onClick={() => onCreate(instruction)}
            className="btn-fill-accent flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all">
            <Sparkle size={12} weight="bold" />
            {t("create")}
          </button>
        </div>
      </div>
    </div>
  );
}
