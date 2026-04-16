import type { StudentStats } from "../_types";

export function MasteryBar({ stats }: { stats: StudentStats | null }) {
  if (!stats) return null;
  const o = stats.lerntools;
  return (
    <div className="px-3 py-2.5 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold" style={{ color: "var(--text)" }}>
          {o.total_sets} {o.total_sets === 1 ? "Übung" : "Übungen"} · {o.total_cards} Karten
        </span>
        <span className="text-xs" style={{ color: "var(--muted)" }}>{o.total_attempts} Antworten</span>
      </div>
    </div>
  );
}

