"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import Modal from "@/components/ui/Modal";
import Mascot, { type MascotVariant } from "@/components/ui/Mascot";

const QUESTIONS = ["what", "sources", "reward"] as const;
type QuestionKey = (typeof QUESTIONS)[number];
type Turn = { key: QuestionKey; answered: boolean };
const THINK_MS = 800;

/** Prepared questions as chips, the answer arrives after a short thinking pause. */
export default function FrancisChatModal({
  open,
  onClose,
  variant,
}: {
  open: boolean;
  onClose: () => void;
  variant: MascotVariant;
}) {
  const t = useTranslations("mockup.stamp.chat");
  const [turns, setTurns] = useState<Turn[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  const ask = (key: QuestionKey) => {
    if (timer.current) return;
    setTurns((list) => [...list, { key, answered: false }]);
    timer.current = setTimeout(() => {
      timer.current = null;
      setTurns((list) => list.map((turn, i) => (i === list.length - 1 ? { ...turn, answered: true } : turn)));
    }, THINK_MS);
  };
  const asked = new Set(turns.map((turn) => turn.key));

  return (
    <Modal open={open} onClose={onClose} title={t("title")} size="md">
      <div className="flex flex-col gap-4" data-testid="francis-chat">
        <p className="text-xs text-muted">{t("hint")}</p>
        {turns.map((turn, i) => (
          <div key={i} className="flex flex-col gap-4">
            <div className="flex justify-end">
              <div
                className="bg-kb text-white px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%]"
                style={{ borderBottomRightRadius: 6 }}
              >
                {t(`questions.${turn.key}.q`)}
              </div>
            </div>
            <div className="flex items-start gap-2.5">
              <div className="shrink-0 mt-0.5">
                <Mascot variant={variant} size={36} state={turn.answered ? "found" : "thinking"} />
              </div>
              <div
                className="bg-surface text-foreground-soft px-3.5 py-2.5 rounded-[20px] text-sm leading-relaxed max-w-[85%] sm:max-w-[70%] border border-border"
                style={{ borderBottomLeftRadius: 6 }}
                data-testid={turn.answered ? "chat-answer" : "chat-thinking"}
              >
                {turn.answered ? t(`questions.${turn.key}.a`) : t("thinking")}
              </div>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-2 pt-3 border-t border-border items-center">
          {QUESTIONS.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => ask(key)}
              className={`px-3.5 py-2 rounded-full text-xs font-semibold border transition-all whitespace-nowrap ${
                asked.has(key)
                  ? "bg-kb text-white border-kb"
                  : "bg-background text-foreground-soft border-border hover:border-kb"
              }`}
            >
              {t(`questions.${key}.q`)}
            </button>
          ))}
        </div>
      </div>
    </Modal>
  );
}
