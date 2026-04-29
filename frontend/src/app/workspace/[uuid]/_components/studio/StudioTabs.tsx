import { useEffect, useRef, useState } from "react";

export function StudioTabs({ tabs, active, onSelect, accentColor }: {
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
  accentColor?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [fits, setFits] = useState(true);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width;
      setFits(w >= tabs.length * 80);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [tabs.length]);

  const cols = fits ? tabs.map(t => t.key === "language_training" ? "1.4fr" : "1fr").join(" ") : undefined;

  return (
    <div ref={ref} className="flex-shrink-0 px-3 pt-6 pb-2 w-full mx-auto" style={{ maxWidth: 500 }}>
      <div
        className={fits ? "grid gap-1 p-1 rounded-xl" : "flex gap-1 p-1 rounded-xl overflow-x-auto scrollbar-hide"}
        style={{ backgroundColor: "rgba(var(--kb-rgb), 0.08)", ...(cols ? { gridTemplateColumns: cols } : {}) }}
      >
        {tabs.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onSelect(tab.key)}
              className={`py-1.5 px-3 text-xs font-medium rounded-lg transition-all overflow-hidden text-ellipsis whitespace-nowrap ${!fits ? "flex-shrink-0" : ""} ${!isActive ? "text-[var(--muted)] hover:text-[var(--kb)] hover:outline-2 hover:outline-[var(--kb)] -outline-offset-1" : ""}`}
              style={{
                ...(isActive ? {
                  color: accentColor || "var(--kb)",
                  backgroundColor: "var(--background)",
                  boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                } : {}),
                border: "none",
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

