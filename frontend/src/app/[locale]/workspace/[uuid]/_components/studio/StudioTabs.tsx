import { useEffect, useRef, useState } from "react";

export function StudioTabs({ tabs, active, onSelect, accentColor }: {
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
  accentColor?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startScroll: number; moved: boolean } | null>(null);
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

  useEffect(() => {
    if (fits) return;
    const el = scrollRef.current;
    if (!el) return;

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      dragRef.current = { startX: e.clientX, startScroll: el.scrollLeft, moved: false };
      e.preventDefault();
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) sel.removeAllRanges();
    };
    const onPointerMove = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      const dx = e.clientX - d.startX;
      if (!d.moved && Math.abs(dx) > 4) {
        d.moved = true;
        el.setPointerCapture(e.pointerId);
        el.style.cursor = "grabbing";
      }
      if (d.moved) {
        el.scrollLeft = d.startScroll - dx;
        e.preventDefault();
      }
    };
    const endDrag = (e: PointerEvent) => {
      const d = dragRef.current;
      if (!d) return;
      if (d.moved && el.hasPointerCapture(e.pointerId)) el.releasePointerCapture(e.pointerId);
      el.style.cursor = "";
      dragRef.current = null;
    };
    const onClickCapture = (e: MouseEvent) => {
      const d = dragRef.current;
      if (d?.moved) {
        e.stopPropagation();
        e.preventDefault();
      }
    };

    el.addEventListener("pointerdown", onPointerDown);
    el.addEventListener("pointermove", onPointerMove);
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener("click", onClickCapture, true);
    return () => {
      el.removeEventListener("pointerdown", onPointerDown);
      el.removeEventListener("pointermove", onPointerMove);
      el.removeEventListener("pointerup", endDrag);
      el.removeEventListener("pointercancel", endDrag);
      el.removeEventListener("click", onClickCapture, true);
    };
  }, [fits]);

  const cols = fits ? tabs.map(t => t.key === "language_training" ? "1.4fr" : "1fr").join(" ") : undefined;

  return (
    <div ref={ref} className="flex-shrink-0 px-3 pt-6 pb-2 w-full mx-auto" style={{ maxWidth: 500 }}>
      <div
        ref={scrollRef}
        className={fits ? "grid gap-1 p-1 rounded-xl" : "flex gap-1 p-1 rounded-xl overflow-x-auto scrollbar-hide cursor-grab select-none"}
        style={{ backgroundColor: "rgba(var(--kb-rgb), 0.08)", ...(cols ? { gridTemplateColumns: cols } : {}), ...(fits ? {} : { touchAction: "pan-x" }) }}
      >
        {tabs.map((tab) => {
          const isActive = active === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => onSelect(tab.key)}
              className={`py-1.5 px-3 text-sm font-medium rounded-lg transition-all overflow-hidden text-ellipsis whitespace-nowrap border-2 ${!fits ? "flex-shrink-0 select-none" : ""} ${
                isActive
                  ? "text-[var(--tab-accent)] dark:text-white bg-transparent border-[var(--tab-accent)]"
                  : "border-transparent text-[var(--muted)] outline-[#004261] hover:text-[var(--kb)] dark:hover:text-white hover:bg-transparent hover:outline-2 -outline-offset-1"
              }`}
              style={{ ["--tab-accent" as string]: accentColor || "var(--kb)" } as React.CSSProperties}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

