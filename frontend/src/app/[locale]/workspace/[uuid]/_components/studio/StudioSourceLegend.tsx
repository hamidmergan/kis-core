"use client";

import { useState, type CSSProperties, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { CaretDown } from "@phosphor-icons/react";

/** Collapsed source list, the same shape as in the language trainer. */
export function StudioSourceLegend({
  count, children, className = "", listClassName = "flex flex-col gap-1", style,
}: {
  count: number;
  children: ReactNode;
  className?: string;
  listClassName?: string;
  style?: CSSProperties;
}) {
  const t = useTranslations("workspace.detail.studio");
  const [open, setOpen] = useState(false);

  if (count <= 0) return null;
  return (
    <div className={`flex flex-col gap-1 ${className}`} style={style}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        aria-expanded={open}
        className="flex items-center gap-1.5 text-xs leading-snug text-left min-w-0 hover-lighten transition-colors"
        style={{ color: "var(--muted)" }}
      >
        <CaretDown
          size={12}
          weight="bold"
          className="shrink-0 transition-transform"
          style={{ transform: open ? "none" : "rotate(-90deg)" }}
        />
        <span className="truncate">{t("sourcesToggle", { count })}</span>
      </button>

      {open && <div className={listClassName}>{children}</div>}
    </div>
  );
}
