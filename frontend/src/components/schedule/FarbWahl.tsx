"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Check } from "@phosphor-icons/react";

/** The legend square, a click opens the palette for this workspace. */
export default function FarbWahl({
  color,
  palette,
  name,
  dimmed,
  onPick,
}: {
  color: string;
  palette: string[];
  name: string;
  dimmed: boolean;
  onPick: (index: number) => void;
}) {
  const t = useTranslations("schedule.month");
  const [open, setOpen] = useState(false);
  const boxRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const klick = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const taste = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", klick);
    document.addEventListener("keydown", taste);
    return () => {
      document.removeEventListener("mousedown", klick);
      document.removeEventListener("keydown", taste);
    };
  }, [open]);

  return (
    <span ref={boxRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t("pickColor", { name })}
        title={t("pickColor", { name })}
        aria-expanded={open}
        className="rounded-sm cursor-pointer border-2 border-transparent hover:border-foreground transition-colors"
        style={{ width: 14, height: 14, backgroundColor: color, opacity: dimmed ? 0.35 : 1 }}
      />
      {open && (
        <span
          role="listbox"
          aria-label={t("pickColor", { name })}
          className="absolute z-50 bottom-full left-0 mb-2 w-max grid grid-cols-5 gap-1.5 p-2 rounded-xl"
          style={{
            backgroundColor: "var(--surface)",
            border: "1px solid var(--border)",
            boxShadow: "rgba(0, 0, 0, 0.12) 0px 4px 16px",
          }}
        >
          {palette.map((farbe, i) => {
            const aktiv = farbe.toLowerCase() === color.toLowerCase();
            return (
              <button
                key={farbe}
                type="button"
                role="option"
                aria-selected={aktiv}
                aria-label={farbe}
                onClick={() => { setOpen(false); if (!aktiv) onPick(i); }}
                className={`w-6 h-6 rounded-md flex items-center justify-center border-2 transition-colors ${
                  aktiv ? "border-foreground" : "border-transparent hover:border-foreground cursor-pointer"
                }`}
                style={{ backgroundColor: farbe, color: "#fff" }}
              >
                {aktiv && <Check size={12} weight="bold" />}
              </button>
            );
          })}
        </span>
      )}
    </span>
  );
}
