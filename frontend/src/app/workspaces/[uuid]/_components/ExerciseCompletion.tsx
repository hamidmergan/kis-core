import { Check } from "@phosphor-icons/react";
import { SubviewHeader } from "./SubviewHeader";

export function ExerciseCompletion({
  title, results, total, onRetryWrong, onBack, breadcrumbs,
}: {
  title: string; results: { item_id: number; correct: boolean }[];
  total: number; onRetryWrong: () => void; onBack: () => void;
  breadcrumbs?: { label: string; onClick: () => void }[];
}) {
  const correct = results.filter((r) => r.correct).length;
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} onBack={onBack} breadcrumbs={breadcrumbs} />
      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-2">
        {/* Animated check */}
        <div className="w-16 h-16 rounded-full flex items-center justify-center mb-2"
          style={{ backgroundColor: "#1a8a5c", boxShadow: "0 4px 20px rgba(26,138,92,0.25)" }}>
          <Check size={30} weight="bold" color="white" />
        </div>
        <h3 className="text-lg font-semibold">Geschafft!</h3>
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          <strong style={{ color: "#1a8a5c" }}>{correct} / {total}</strong> gewusst — <strong style={{ color: "#1a8a5c" }}>{pct}%</strong>
        </p>
        <div className="flex gap-2 mt-4">
          {correct < total && (
            <button type="button" onClick={onRetryWrong}
              className="px-4 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
              style={{ color: "var(--accent)", backgroundColor: "var(--surface)", border: "1.5px solid var(--border)" }}>
              Falsche wiederholen
            </button>
          )}
          <button type="button" onClick={onBack}
            className="px-4 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90"
            style={{ backgroundColor: "var(--accent)" }}>
            Zur Übersicht
          </button>
        </div>
      </div>
    </div>
  );
}

