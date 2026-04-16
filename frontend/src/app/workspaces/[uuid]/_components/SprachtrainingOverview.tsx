import { BookOpenText, Exam, TextAa } from "@phosphor-icons/react";
import type { SprachtrainingView } from "../_types";

export function SprachtrainingOverview({
  activeSourceCount, glossaryCount, onNavigate,
}: {
  activeSourceCount: number;
  glossaryCount: number;
  onNavigate: (view: SprachtrainingView) => void;
}) {
  const noSources = activeSourceCount === 0;

  const tiles = [
    { key: "lk-sets" as const, Icon: BookOpenText, label: "Lernkarten", desc: "Übungen", iconBg: "rgba(245,235,220,0.7)", iconColor: "#78350F" },
    { key: "cl-sets" as const, Icon: TextAa, label: "Lückentext", desc: "Übungen", iconBg: "rgba(254,226,226,0.7)", iconColor: "#B91C1C" },
    { key: "vt-sets" as const, Icon: Exam, label: "Begriffe-Quiz", desc: "Übungen", iconBg: "rgba(237,233,254,0.7)", iconColor: "#534AB7" },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-3">
        {/* Glossar counter */}
        {glossaryCount > 0 && (
          <span className="text-xs font-medium px-1" style={{ color: "var(--muted)" }}>
            {glossaryCount}/150 Glossar
          </span>
        )}

        {/* Tool tiles */}
        <div className="grid gap-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))" }}>
          {tiles.map((tile) => {
            const disabled = noSources;
            return (
              <button
                key={tile.key}
                type="button"
                onClick={() => !disabled && onNavigate(tile.key)}
                disabled={disabled}
                className="flex flex-col items-center justify-center gap-1.5 p-3 rounded-2xl text-center transition-all hover:brightness-95 disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  minHeight: 85,
                  backgroundColor: tile.iconBg,
                  border: `1.5px solid ${tile.iconColor}22`,
                }}
              >
                <tile.Icon size={20} color={tile.iconColor} weight="bold" />
                <span className="text-xs font-semibold leading-tight" style={{ color: tile.iconColor }}>
                  {tile.label}
                </span>
                <span className="text-xs" style={{ color: tile.iconColor, opacity: 0.7 }}>
                  {tile.desc}
                </span>
              </button>
            );
          })}
        </div>

      </div>
    </div>
  );
}

