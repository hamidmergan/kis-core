import { Check } from "@phosphor-icons/react";
import { SubviewHeader, type BreadcrumbItem, type ToolCategory } from "../layout/SubviewHeader";

export function ExerciseCompletion({
  title, toolKey, category, results, total, onRetryWrong, onBack, breadcrumbs,
}: {
  title: string; toolKey?: string; category?: ToolCategory;
  results: { item_id: number; correct: boolean }[];
  total: number; onRetryWrong: () => void; onBack: () => void;
  breadcrumbs?: BreadcrumbItem[];
}) {
  const correct = results.filter((r) => r.correct).length;
  const pct = total > 0 ? Math.round((correct / total) * 100) : 0;
  return (
    <div className="flex flex-col h-full">
      <SubviewHeader title={title} toolKey={toolKey} category={category} onBack={onBack} breadcrumbs={breadcrumbs} />
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
              className="px-4 py-2 rounded-full text-xs font-semibold transition-all hover:outline-2 hover:outline-[var(--accent)]"
              style={{ color: "var(--accent)", backgroundColor: "var(--surface)", border: "2px solid var(--border)" }}>
              Falsche wiederholen
            </button>
          )}
          <button type="button" onClick={onBack}
            className="btn-fill-accent px-4 py-2 rounded-full text-xs font-semibold transition-all">
            Zur Übersicht
          </button>
        </div>
      </div>
    </div>
  );
}

