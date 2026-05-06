import { SidebarSimple } from "@phosphor-icons/react";

export function MiniStrip({
  label,
  onClick,
  side,
  disabled,
  disabledTooltip,
}: {
  label: string;
  onClick: () => void;
  side: "left" | "right";
  disabled?: boolean;
  disabledTooltip?: string;
}) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      aria-disabled={disabled}
      className="mini-strip-btn flex flex-col items-center pt-4 h-full w-full gap-2 disabled:cursor-not-allowed"
      style={disabled ? { opacity: 0.4 } : undefined}
      title={disabled && disabledTooltip ? disabledTooltip : label}
    >
      <span
        className="mini-strip-icon w-7 h-7 flex items-center justify-center rounded-full"
        style={{ backgroundColor: "var(--surface-dim)" }}
      >
        <SidebarSimple
          size={13}
          style={{ transform: side === "right" ? "scaleX(-1)" : "none", flexShrink: 0 }}
        />
      </span>
      <span
        className="text-[10px] font-semibold tracking-widest uppercase select-none"
        style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
      >
        {label}
      </span>
    </button>
  );
}

