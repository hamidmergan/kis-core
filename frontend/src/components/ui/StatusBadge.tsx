import { type ReactNode } from "react";

export type StatusKind = "queued" | "running" | "success" | "failed" | "neutral" | "warning";

interface StatusBadgeProps {
  kind: StatusKind;
  children: ReactNode;
  className?: string;
}

const palette: Record<StatusKind, { bg: string; fg: string; border: string }> = {
  queued:   { bg: "var(--surface)",    fg: "var(--foreground-soft)",       border: "var(--border-soft)" },
  running:  { bg: "var(--info-bg)",    fg: "var(--info-strong)",     border: "var(--info-border)" },
  success:  { bg: "var(--success-bg)", fg: "var(--success-strong)",  border: "var(--success-border)" },
  failed:   { bg: "var(--error-bg)",   fg: "var(--error-strong)",    border: "var(--error-border)" },
  neutral:  { bg: "var(--surface)",    fg: "var(--foreground-soft)",       border: "var(--border-soft)" },
  warning:  { bg: "var(--warn-bg)",    fg: "var(--warn-strong)",     border: "var(--warn-border)" },
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
