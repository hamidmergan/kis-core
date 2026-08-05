import React, { useEffect, useRef, useState } from "react";
import HoverTooltip from "@/components/ui/HoverTooltip";

export function LerntoolsGrid({ tiles, onSelect }: {
  tiles: { key: string; Icon: React.ComponentType<any>; label: string; description?: string; iconBg: string; iconColor: string }[];
  onSelect: (key: string) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [compact, setCompact] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => {
      setCompact(entry.contentRect.width < 160);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} className="px-3 pb-3 flex-shrink-0">
      <div className="grid gap-2" style={{ gridTemplateColumns: compact ? "repeat(auto-fill, minmax(50px, 1fr))" : "repeat(auto-fill, minmax(120px, 1fr))" }}>
        {tiles.map((tile) => (
          <HoverTooltip
            key={tile.key}
            // Die Kachel zeigt ihren Namen selbst, nur die schmale Ansicht nicht.
            // Deshalb steht der Name auch nur dort im Tooltip.
            text={
              !tile.description ? tile.label
                : compact ? `${tile.label}\n${tile.description}`
                : tile.description
            }
          >
            <button
              type="button"
              onClick={() => onSelect(tile.key)}
              className="flex flex-col items-center justify-center gap-2 p-3 rounded-2xl text-center border-2 transition-colors border-[var(--tile-border)] hover:border-[var(--tile-color)]"
              style={{
                minHeight: compact ? 50 : 90,
                backgroundColor: tile.iconBg,
                ["--tile-color" as string]: tile.iconColor,
                ["--tile-border" as string]: `color-mix(in srgb, ${tile.iconColor} 20%, transparent)`,
              }}
            >
              <tile.Icon size={compact ? 18 : 20} color={tile.iconColor} weight="bold" />
              {!compact && (
                <span className="text-xs font-semibold leading-tight" style={{ color: tile.iconColor }}>
                  {tile.label}
                </span>
              )}
            </button>
          </HoverTooltip>
        ))}
      </div>
    </div>
  );
}

