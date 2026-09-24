"use client";

import { useFormatter, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import type { Bilanz, Messung } from "@/lib/materialMeasure";

/** The characters of one file or source, next to its name. */
export function MeasureNote({ messung }: { messung: Messung | undefined }) {
  const t = useTranslations("common.material");
  const format = useFormatter();
  if (!messung || messung.status === "laeuft") return <Spinner size="xs" />;
  if (messung.status === "fehler") return <span className="text-xs text-error">{t("unreadable")}</span>;
  return <span className="text-xs text-muted-soft">{t("chars", { n: format.number(messung.chars) })}</span>;
}

/** Why one file or source cannot be used, below its row. */
export function MeasureError({ messung }: { messung: Messung | undefined }) {
  if (messung?.status !== "fehler") return null;
  return <p className="mt-1 text-xs text-error">{messung.message}</p>;
}

/** How much of the character limit the picked material fills, for all three services alike. */
export default function MaterialGauge({ bilanz, max, className = "mb-3" }: { bilanz: Bilanz; max: number; className?: string }) {
  const t = useTranslations("common.material");
  const format = useFormatter();
  const pct = Math.min(100, (bilanz.total / max) * 100);
  const zahlen = { n: format.number(bilanz.total), max: format.number(max) };
  return (
    <div className={className}>
      <div className="w-full h-1.5 bg-surface-dim rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${bilanz.over ? "bg-error" : "bg-kb"}`} style={{ width: `${pct}%` }} />
      </div>
      <p className={`mt-1 text-xs ${bilanz.over ? "text-error font-medium" : "text-muted"}`}>
        {t(bilanz.pending ? "totalCounting" : "total", zahlen)}
      </p>
      {bilanz.over && (
        <p className="mt-2 rounded-lg border border-error-border bg-error-bg px-3 py-2 text-sm text-error">
          {t("tooMuch", { over: format.number(bilanz.total - max) })}
        </p>
      )}
    </div>
  );
}
