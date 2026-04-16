import { useState } from "react";
import { Plus } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";

export function CreateSetModal({
  tool, glossaryCount, selectedSource, creating,
  onClose, onCreate,
}: {
  tool: string; glossaryCount: number; selectedSource?: { uuid: string; filename: string } | null;
  creating: boolean;
  onClose: () => void;
  onCreate: (mode: string, count: number) => void;
}) {
  const isQuiz = tool === "quiz";
  const [mode, setMode] = useState<"glossar" | "quelle">(isQuiz || glossaryCount === 0 ? "quelle" : "glossar");
  const [count, setCount] = useState(isQuiz ? 5 : 10);
  const toolLabels: Record<string, string> = { karteikarten: "Karteikarten", lernkarten: "Lernkarten", lueckentext: "Lückentext", vokabeltest: "Begriffe-Quiz", quiz: "Quiz" };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-[340px]" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">Neue {toolLabels[tool] || "Übung"} erstellen</h3>

        {/* Mode */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>Quelle</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && (
            <button type="button" onClick={() => glossaryCount > 0 && setMode("glossar")}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
              style={{
                ...(mode === "glossar"
                  ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)", color: "var(--text)" }
                  : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)" }),
                ...(glossaryCount === 0 ? { opacity: 0.4, pointerEvents: "none" as const } : {}),
              }}>
              <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
                style={{ borderColor: mode === "glossar" ? "var(--accent)" : "var(--border)" }}>
                {mode === "glossar" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--accent)" }} />}
              </div>
              Aus Glossar <span className="text-[10px]" style={{ color: "var(--muted)" }}>({glossaryCount} Begriffe)</span>
            </button>
          )}
          <button type="button" onClick={() => selectedSource && setMode("quelle")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
            style={{
              ...(mode === "quelle"
                ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)" }),
              color: "var(--text)",
              opacity: selectedSource ? 1 : 0.4,
              pointerEvents: selectedSource ? "auto" : "none",
            }}>
            <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
              style={{ borderColor: mode === "quelle" ? "var(--accent)" : "var(--border)" }}>
              {mode === "quelle" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--accent)" }} />}
            </div>
            Aus ausgewählter Quelle {selectedSource && <span className="text-[10px] inline-block max-w-[120px] truncate align-bottom" title={selectedSource.filename} style={{ color: "var(--muted)" }}>({selectedSource.filename})</span>}
          </button>
          {!selectedSource && (
            <p className="text-[10px] ml-5" style={{ color: "#c4820e" }}>
              Wähle links eine Quelle aus, um aus ihr zu generieren.
            </p>
          )}
        </div>

        {/* Count */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>Anzahl</div>
        <div className="flex gap-1.5 mb-4">
          {[5, 10, 15].map((n) => (
            <button key={n} type="button" onClick={() => setCount(n)}
              className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all text-center"
              style={count === n
                ? { border: "1.5px solid var(--accent)", backgroundColor: "rgba(var(--accent-rgb),0.07)", color: "var(--accent)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--bg)", color: "var(--text)" }}>
              {n}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded-full text-xs font-semibold transition-all hover:opacity-80"
            style={{ color: "var(--accent)", backgroundColor: "var(--surface)", border: "1.5px solid var(--border)" }}>
            Abbrechen
          </button>
          <button type="button" onClick={() => onCreate(mode, count)} disabled={creating}
            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50"
            style={{ backgroundColor: "var(--accent)" }}>
            {creating ? <Spinner size="xs" color="current" /> : <Plus size={13} weight="bold" />}
            {creating ? "Generieren…" : "Erstellen"}
          </button>
        </div>
      </div>
    </div>
  );
}

