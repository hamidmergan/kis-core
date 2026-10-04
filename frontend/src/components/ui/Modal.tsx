"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";

import { backdropClose, newBackdropPress } from "./backdropClose";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  flush?: boolean;
  size?: "sm" | "md" | "lg" | "xl" | "full";
  closeOnBackdropClick?: boolean;
  closeOnEscape?: boolean;
  className?: string;
}

const sizeClass: Record<NonNullable<ModalProps["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  full: "max-w-[1400px]",
};

type Area = { left: number; top: number; width: number; height: number };

/** The layout viewport can be wider than the screen, so the dialog follows the visible area. */
function useVisibleArea(open: boolean): Area | null {
  const [area, setArea] = useState<Area | null>(null);
  useEffect(() => {
    const vv = typeof window === "undefined" ? null : window.visualViewport;
    if (!open || !vv) return;
    const read = () =>
      setArea({ left: vv.offsetLeft, top: vv.offsetTop, width: vv.width, height: vv.height });
    read();
    vv.addEventListener("resize", read);
    vv.addEventListener("scroll", read);
    return () => {
      vv.removeEventListener("resize", read);
      vv.removeEventListener("scroll", read);
    };
  }, [open]);
  return open ? area : null;
}

export default function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  flush = false,
  size = "md",
  closeOnBackdropClick = true,
  closeOnEscape = true,
  className = "",
}: ModalProps) {
  const t = useTranslations("common");
  const dialogRef = useRef<HTMLDivElement>(null);
  const press = useRef(newBackdropPress()).current;
  const area = useVisibleArea(open);

  useEffect(() => {
    if (!open || !closeOnEscape) return;
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, closeOnEscape, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed z-50 flex items-center justify-center p-4"
      style={{
        backgroundColor: "rgba(0, 0, 0, 0.5)",
        ...(area
          ? { left: area.left, top: area.top, width: area.width, height: area.height }
          : { inset: 0 }),
      }}
      {...backdropClose(press, onClose, closeOnBackdropClick)}
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={dialogRef}
        className={`w-full ${sizeClass[size]} rounded-xl shadow-lg flex flex-col max-h-full ${className}`}
        style={{ backgroundColor: "var(--background)", border: "1px solid var(--border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div
            className="px-5 py-4 flex items-center justify-between gap-4"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            {/* min-w-0 plus the break: a long file name must not push the close button out of the dialog. */}
            <div className="min-w-0 break-words text-base font-semibold" style={{ color: "var(--foreground)" }}>
              {title}
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("close")}
              className="w-7 h-7 flex-shrink-0 inline-flex items-center justify-center rounded-full btn-icon dark:text-white dark:hover:!text-white transition-colors"
              style={{ backgroundColor: "var(--surface-dim)" }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M18 6 6 18M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div className={`${flush ? "" : "px-5 py-4"} overflow-y-auto flex-1`}>{children}</div>

        {footer && (
          <div
            className="px-5 py-3 flex items-center justify-end gap-2"
            style={{ borderTop: "1px solid var(--border)" }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
