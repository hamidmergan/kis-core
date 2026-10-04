"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ThlKugel from "@/components/ui/ThlKugel";
import { phaseAt } from "@/app/[locale]/workspace/[uuid]/_components/chat/_phase";

const TICK_MS = 100;

/** The two waiting lines of the assistant, with the campus texts. */
export default function WartezeileCampus({ metaArrived }: { metaArrived: boolean }) {
  const t = useTranslations("tools.campus.phases");
  const startedAt = useRef(Date.now());
  const metaAt = useRef<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  if (metaArrived && metaAt.current === null) metaAt.current = Date.now() - startedAt.current;

  useEffect(() => {
    const id = setInterval(() => setElapsedMs(Date.now() - startedAt.current), TICK_MS);
    return () => clearInterval(id);
  }, []);

  const phase = phaseAt({ elapsedMs, qmapAtMs: metaAt.current, hasText: false, isPopup: false });
  return (
    <div role="status" aria-live="polite" data-testid="campus-phase" className="flex items-center h-5 px-1 text-xs" style={{ color: "var(--muted)" }}>
      {phase && (
        <span className="flex items-center gap-2">
          <ThlKugel />
          <span className="text-shimmer">{t(phase)}</span>
        </span>
      )}
    </div>
  );
}
