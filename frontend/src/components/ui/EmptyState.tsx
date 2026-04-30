import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  text,
  action,
  className = "",
  size = "md",
}: {
  icon?: ReactNode;
  title?: string;
  text?: string | ReactNode;
  action?: ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const padY = size === "sm" ? "py-6" : size === "lg" ? "py-12" : "py-8";
  const textSize = "text-sm";

  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 ${padY} px-4 text-center ${className}`}
      style={{ color: "var(--muted)" }}
    >
      {icon && <div style={{ color: "var(--border)" }}>{icon}</div>}
      {title && <p className={`${textSize} font-medium`} style={{ color: "var(--muted)" }}>{title}</p>}
      {text && (
        typeof text === "string"
          ? <p className={`${textSize} leading-snug max-w-xs`}>{text}</p>
          : <div className={`${textSize} leading-snug max-w-xs`}>{text}</div>
      )}
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}
