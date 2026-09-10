"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretDown, CaretUp } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";

/** The module description, cut to one line until the reader unfolds it. */
export default function WorkspaceDescription({ text }: { text: string }) {
  const t = useTranslations("workspace.list");
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  const textRef = useRef<HTMLSpanElement>(null);

  // Only a description that really does not fit earns the caret.
  useEffect(() => {
    if (open) return; // a wrapped text never overflows, so the last verdict stands
    const el = textRef.current;
    if (!el) return;
    const measure = () => setCut(el.scrollWidth > el.clientWidth + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [text, open]);

  const label = open ? t("descriptionLess") : t("descriptionMore");

  return (
    <span className="flex items-start gap-1.5 mt-0.5">
      <span
        ref={textRef}
        className={`text-xs min-w-0 ${open ? "" : "truncate"}`}
        style={{ color: "var(--muted)" }}
        title={open ? undefined : text}
      >
        {text}
      </span>
      {cut && (
        <IconButton
          size="sm"
          aria-label={label}
          aria-expanded={open}
          title={label}
          data-testid="module-description-toggle"
          className="-mt-0.5"
          style={{ backgroundColor: "transparent" }}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        >
          {open ? <CaretUp size={12} weight="bold" /> : <CaretDown size={12} weight="bold" />}
        </IconButton>
      )}
    </span>
  );
}
