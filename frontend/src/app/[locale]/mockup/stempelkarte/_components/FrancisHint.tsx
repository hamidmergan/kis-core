"use client";

import { useTranslations } from "next-intl";
import Mascot, { type MascotState, type MascotVariant } from "@/components/ui/Mascot";
import type { Station } from "../../_lib/types";
import { useText2 } from "../../_lib/useText2";

export type HintMood = { kind: "welcome" } | { kind: "stamped"; station: Station } | { kind: "wrong" };

const STATE: Record<HintMood["kind"], MascotState> = { welcome: "idle", stamped: "found", wrong: "confused" };

/** Speech bubble next to the mascot, after a stamp it carries the stand text and the next open stand. */
export default function FrancisHint({
  variant,
  mood,
  next,
  onAsk,
}: {
  variant: MascotVariant;
  mood: HintMood;
  next: Station | null;
  onAsk: () => void;
}) {
  const t = useTranslations("mockup.stamp.francis");
  const text = useText2();
  const lines: string[] = [];
  if (mood.kind === "welcome") lines.push(t("welcome"));
  if (mood.kind === "wrong") lines.push(t("wrong"));
  if (mood.kind === "stamped") {
    lines.push(t("stamped", { station: text(mood.station.name) }), text(mood.station.francis));
    lines.push(next ? t("next", { station: text(next.name) }) : t("allDone"));
  }
  return (
    <div className="flex items-start gap-3" data-testid="francis-hint" data-mood={mood.kind}>
      <Mascot key={mood.kind} variant={variant} size={64} state={STATE[mood.kind]} className="shrink-0" />
      <div className="flex-1 min-w-0 flex flex-col items-start gap-2">
        <div
          className="w-full rounded-2xl border-2 border-border bg-surface px-4 py-3 text-sm leading-relaxed text-foreground"
          style={{ borderTopLeftRadius: 6 }}
        >
          {lines.map((line, i) => (
            <p key={i} className={i > 0 ? "mt-1" : ""}>
              {line}
            </p>
          ))}
        </div>
        <button
          type="button"
          onClick={onAsk}
          className="px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors disabled:opacity-60"
          data-testid="ask-francis"
        >
          {t("ask")}
        </button>
      </div>
    </div>
  );
}
