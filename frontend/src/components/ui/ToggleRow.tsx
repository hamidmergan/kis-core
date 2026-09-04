"use client";

export default function ToggleRow({
  title,
  description,
  checked,
  onToggle,
  disabled,
}: {
  title: string;
  description: string;
  checked: boolean;
  onToggle: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4" style={{ opacity: disabled ? 0.4 : 1 }}>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium" style={{ color: "var(--foreground)" }}>{title}</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={title}
        onClick={() => !disabled && onToggle()}
        disabled={disabled}
        className="relative inline-flex h-5 w-9 flex-shrink-0 rounded-full border-2 border-transparent hover:border-[var(--kb)] disabled:hover:border-transparent transition-colors duration-200"
        style={{ backgroundColor: checked && !disabled ? "var(--kb)" : "var(--border)", cursor: disabled ? "not-allowed" : "pointer" }}
      >
        <span
          className="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200"
          style={{ transform: checked && !disabled ? "translateX(16px)" : "translateX(0)" }}
        />
      </button>
    </div>
  );
}
