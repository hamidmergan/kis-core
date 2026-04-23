"use client";

import { type ReactNode } from "react";

interface AccordionProps {
  children: ReactNode;
  className?: string;
}

export function Accordion({ children, className = "" }: AccordionProps) {
  return <div className={`flex flex-col gap-2 ${className}`}>{children}</div>;
}

interface AccordionItemProps {
  header: ReactNode;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  className?: string;
}

export function AccordionItem({ header, open, onToggle, children, className = "" }: AccordionItemProps) {
  return (
    <div
      className={`rounded-lg overflow-hidden ${className}`}
      style={{ backgroundColor: "var(--bg)", border: "1px solid var(--border)" }}
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full px-4 py-3 flex items-center justify-between gap-3 text-left hover:opacity-80 transition-opacity"
        style={{ color: "var(--text)" }}
      >
        <div className="flex-1 min-w-0">{header}</div>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
          className="transition-transform shrink-0"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", color: "var(--muted)" }}
        >
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1" style={{ borderTop: "1px solid var(--border)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

export default Accordion;
