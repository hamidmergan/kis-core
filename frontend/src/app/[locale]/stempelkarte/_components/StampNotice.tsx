"use client";

import { useTranslations } from "next-intl";
import type { PublicStation } from "@/lib/event/types";
import { useText2 } from "@/lib/event/useText2";

export type HintMood = { kind: "welcome" } | { kind: "stamped"; station: PublicStation } | { kind: "wrong" };

/** Notice at the top, the welcome text is plain and the rest sits in a box, after a stamp it carries the stand text and the next open stand. */
export default function StampNotice({ mood, next }: { mood: HintMood; next: PublicStation | null }) {
  const t = useTranslations("eventStamp.francis");
  const text = useText2();
  const lines: string[] = [];
  if (mood.kind === "welcome") lines.push(t("welcome"));
  if (mood.kind === "wrong") lines.push(t("wrong"));
  if (mood.kind === "stamped") {
    lines.push(t("stamped", { station: text(mood.station.name) }), text(mood.station.francis));
    lines.push(next ? t("next", { station: text(next.name) }) : t("allDone"));
  }
  if (mood.kind === "welcome") {
    return (
      <p className="text-base text-foreground-soft" data-testid="stamp-notice" data-mood={mood.kind}>
        {lines[0]}
      </p>
    );
  }
  return (
    <div
      className="rounded-2xl border-2 border-kb/15 bg-kb/5 px-4 py-3 text-sm leading-relaxed text-foreground"
      role="status"
      data-testid="stamp-notice"
      data-mood={mood.kind}
    >
      {lines.map((line, i) => (
        <p key={i} className={i > 0 ? "mt-1" : ""}>
          {line}
        </p>
      ))}
    </div>
  );
}
