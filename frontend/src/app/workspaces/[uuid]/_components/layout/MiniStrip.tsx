import { SidebarSimple } from "@phosphor-icons/react";

export function MiniStrip({ label, onClick, side }: { label: string; onClick: () => void; side: "left" | "right" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-center pt-4 h-full w-full gap-2 btn-icon"
      
      title={label}
    >
      <span
        className="w-7 h-7 flex items-center justify-center rounded-full"
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

