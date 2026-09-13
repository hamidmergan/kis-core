"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import AiHinweisText from "@/components/ui/AiHinweisText";
import type { Side, Turn } from "../_types";

interface Props {
  open: boolean;
  onClose: () => void;
  turns: Turn[];
  names: Record<Side, string>;
  formatTime: (at: number) => string;
}

/** The whole conversation in both languages, to take along. */
export default function ProtocolModal({ open, onClose, turns, names, formatTime }: Props) {
  const t = useTranslations("tools.interpreter.protocol");
  const tCommon = useTranslations("common");
  const lines = turns.filter((turn) => turn.original.trim());

  const download = () => {
    const text = lines.map((turn) => `[${formatTime(turn.at)}] ${names[turn.side]}\n${turn.original}\n${turn.translation}`).join("\n\n");
    const blob = new Blob([`${tCommon("aiHinweis")}\n\n${text}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${t("filename")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t("title")}
      size="lg"
      footer={
        <>
          <button type="button" onClick={onClose} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">
            {t("close")}
          </button>
          <button type="button" onClick={download} disabled={!lines.length} className="px-4 py-2 text-sm btn-primary rounded-lg disabled:opacity-50">
            {t("download")}
          </button>
        </>
      }
    >
      <p className="text-sm text-muted mb-1">{t("intro")}</p>
      <AiHinweisText className="mb-4" />
      {lines.length === 0 ? (
        <p className="text-sm text-muted-soft">{t("empty")}</p>
      ) : (
        <ol className="space-y-3">
          {lines.map((turn) => (
            <li key={turn.id} className="text-sm">
              <div className="text-2xs text-muted-soft">{formatTime(turn.at)} {names[turn.side]}</div>
              <p className="text-foreground whitespace-pre-wrap">{turn.original}</p>
              <p className="text-foreground-soft whitespace-pre-wrap">{turn.translation}</p>
            </li>
          ))}
        </ol>
      )}
    </Modal>
  );
}
