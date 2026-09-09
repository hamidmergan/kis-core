"use client";

import { useState, type ReactNode } from "react";
import { CaretRight } from "@phosphor-icons/react";

/** Card with collapsible content, hidden instead of unmounted so input stays. */
export default function CollapsibleCard({
  title,
  badge,
  description,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  /** Placeholder name in monospace next to the title, e.g. {grading}. */
  badge?: string;
  description?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border-2 border-border-soft rounded-xl bg-background transition-colors hover:border-kb">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`w-full text-left flex items-start gap-2 px-5 pt-5 rounded-xl ${
          open ? "pb-4" : "pb-5"
        }`}
      >
        <CaretRight
          size={12}
          weight="bold"
          className={`mt-1 flex-shrink-0 text-muted-soft transition-transform ${open ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium text-foreground">
            {title}
            {badge && (
              <span className="ml-2 text-xs font-mono font-normal text-muted-soft">{badge}</span>
            )}
          </span>
          {description && <span className="block text-xs text-muted mt-1">{description}</span>}
        </span>
      </button>
      <div className={open ? "px-5 pb-5" : "hidden"}>{children}</div>
    </div>
  );
}
