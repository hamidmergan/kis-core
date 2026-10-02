"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { ImageSquare } from "@phosphor-icons/react";

/** Browser-style frame around a dashed slot where the real screenshot goes later. */
export default function ScreenshotSlot({
  caption,
  className = "",
  compact = false,
  icon,
}: {
  caption?: string;
  className?: string;
  compact?: boolean;
  icon?: ReactNode;
}) {
  const t = useTranslations("mockup.info");
  return (
    <figure className={`flex flex-col gap-3 ${className}`} data-testid="screenshot-slot">
      <div className="rounded-2xl border border-border bg-background overflow-hidden" style={{ boxShadow: "var(--shadow)" }}>
        <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-border-soft bg-surface" aria-hidden="true">
          <span className="w-2.5 h-2.5 rounded-full bg-border" />
          <span className="w-2.5 h-2.5 rounded-full bg-border" />
          <span className="w-2.5 h-2.5 rounded-full bg-border" />
        </div>
        <div
          className={`${compact ? "aspect-[16/10]" : "aspect-[16/10] lg:aspect-[3/2]"} w-full bg-surface flex flex-col items-center justify-center gap-2 text-muted`}
        >
          {icon ?? <ImageSquare size={compact ? 32 : 48} aria-hidden="true" />}
          {!compact && <span className="text-sm">{t("placeholder")}</span>}
        </div>
      </div>
      {caption && <figcaption className="text-xs text-muted">{caption}</figcaption>}
    </figure>
  );
}
