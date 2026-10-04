"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import RoteKugel from "@/components/ui/RoteKugel";
import { phaseAt } from "./_phase";

/** Ticks often enough for the grace period and the minimum to land, rarely enough to stay cheap. */
const TICK_MS = 100;

export default function ChatPhaseLine({
  qmapArrived,
  isPopup,
}: {
  qmapArrived: boolean;
  isPopup: boolean;
}) {
  const t = useTranslations("workspace.detail.chat.phases");
  const startedAt = useRef(Date.now());
  const qmapAt = useRef<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  if (qmapArrived && qmapAt.current === null) qmapAt.current = Date.now() - startedAt.current;

  useEffect(() => {
    const id = setInterval(() => setElapsedMs(Date.now() - startedAt.current), TICK_MS);
    return () => clearInterval(id);
  }, []);

  const phase = phaseAt({ elapsedMs, qmapAtMs: qmapAt.current, hasText: false, isPopup });

  // The row keeps its height through the grace period, so nothing shifts once the text appears.
  return (
    <div
      data-testid="chat-phase"
      role="status"
      aria-live="polite"
      className="flex items-center h-5 px-1 text-xs"
      style={{ color: "var(--muted)" }}
    >
      {/* Keyframe lives in globals.css, so reduced motion switches it off with everything else. */}
      {phase && (
        <span className="flex items-center gap-2">
          <RoteKugel />
          <span className="text-glanz">{t(phase)}</span>
        </span>
      )}
    </div>
  );
}
