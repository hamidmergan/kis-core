import { useEffect, useRef, useState } from "react";

export function StudioTabs({ tabs, active, onSelect, accentColor }: {
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
  accentColor?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<"row" | "grid" | "stack">("row");

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      if (w >= tabs.length * 90) setLayout("row");
      else if (w >= 160) setLayout("grid");
      else setLayout("stack");
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [tabs.length]);

  const cols = layout === "row" ? tabs.map(t => t.key === "sprachtraining" ? "1.4fr" : "1fr").join(" ") : layout === "grid" ? "repeat(2, 1fr)" : "1fr";

  return (
    <div ref={ref} className="flex-shrink-0 px-3 pt-6 pb-2 w-full mx-auto" style={{ maxWidth: 500 }}>
      <div
        className="grid gap-1 p-1 rounded-xl"
        style={{ backgroundColor: "rgba(var(--accent-rgb), 0.08)", gridTemplateColumns: cols }}
      >
        {tabs.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onSelect(tab.key)}
              className={`py-1.5 px-3 text-xs font-medium rounded-lg transition-all overflow-hidden text-ellipsis whitespace-nowrap ${!isActive ? "hover:bg-black/[0.03] hover:text-[var(--text)]" : ""}`}
              style={{
                color: isActive ? (accentColor || "var(--accent)") : "var(--muted)",
                backgroundColor: isActive ? "var(--bg)" : undefined,
                border: "none",
                boxShadow: isActive ? "0 1px 3px rgba(0,0,0,0.08)" : "none",
              }}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

