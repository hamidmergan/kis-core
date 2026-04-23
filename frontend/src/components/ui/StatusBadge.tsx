import { type ReactNode } from "react";

export type StatusKind = "queued" | "running" | "success" | "failed" | "neutral" | "warning";

interface StatusBadgeProps {
  kind: StatusKind;
  children: ReactNode;
  className?: string;
}

const palette: Record<StatusKind, { bg: string; fg: string; border: string }> = {
  queued:   { bg: "#F3F4F6", fg: "#4B5563", border: "#E5E7EB" },
  running:  { bg: "#DBEAFE", fg: "#1D4ED8", border: "#BFDBFE" },
  success:  { bg: "#D1FAE5", fg: "#047857", border: "#A7F3D0" },
  failed:   { bg: "#FEE2E2", fg: "#B91C1C", border: "#FECACA" },
  neutral:  { bg: "#F3F4F6", fg: "#374151", border: "#E5E7EB" },
  warning:  { bg: "#FEF3C7", fg: "#92400E", border: "#FDE68A" },
};

export default function StatusBadge({ kind, children, className = "" }: StatusBadgeProps) {
  const c = palette[kind];
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold ${className}`}
      style={{ backgroundColor: c.bg, color: c.fg, border: `1px solid ${c.border}` }}
    >
      {children}
    </span>
  );
}
