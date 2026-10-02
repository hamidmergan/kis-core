"use client";

import { useTranslations } from "next-intl";
import { ImageSquare } from "@phosphor-icons/react";

/** Dashed frame where a real screenshot goes once the pages exist. */
export default function ScreenshotSlot({ caption, className = "" }: { caption?: string; className?: string }) {
  const t = useTranslations("mockup.info");
  return (
    <figure className={`flex flex-col gap-2 ${className}`} data-testid="screenshot-slot">
      <div className="aspect-video w-full rounded-2xl border-2 border-dashed border-border bg-surface flex flex-col items-center justify-center gap-2 text-muted">
        <ImageSquare size={32} aria-hidden="true" />
        <span className="text-sm">{t("placeholder")}</span>
      </div>
      {caption && <figcaption className="text-xs text-muted">{caption}</figcaption>}
    </figure>
  );
}
