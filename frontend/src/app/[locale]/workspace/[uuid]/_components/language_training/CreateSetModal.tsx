import { useState } from "react";
import { Sparkle } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";

export function CreateSetModal({
  tool, glossaryCount, selectedSource,
  onClose, onCreate,
}: {
  tool: string; glossaryCount: number; selectedSource?: { uuid: string; filename: string } | null;
  onClose: () => void;
  onCreate: (mode: string, count: number) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const isQuiz = tool === "quiz";
  const [mode, setMode] = useState<"glossary" | "source">(isQuiz || glossaryCount === 0 ? "source" : "glossary");
  const [count, setCount] = useState(isQuiz ? 5 : 10);
  const toolLabel = (() => {
    const map: Record<string, string> = {
      karteikarten: t("tools.karteikarten"),
      flashcards: t("tools.flashcards"),
      lueckentext: t("tools.lueckentext"),
      vokabeltest: t("tools.vokabeltest"),
      quiz: t("tools.quiz"),
    };
    return map[tool] || t("tools.exerciseFallback");
  })();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-[340px]" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">{t("createModal.title", { tool: toolLabel })}</h3>

        {/* Mode */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.sourceHeading")}</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && (
            <button type="button" onClick={() => glossaryCount > 0 && setMode("glossary")}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
              style={{
                ...(mode === "glossary"
                  ? { border: "1.5px solid var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)", color: "var(--foreground)" }
                  : { border: "1.5px solid var(--border)", backgroundColor: "var(--background)", color: "var(--foreground)" }),
                ...(glossaryCount === 0 ? { opacity: 0.4, pointerEvents: "none" as const } : {}),
              }}>
              <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
                style={{ borderColor: mode === "glossary" ? "var(--kb)" : "var(--border)" }}>
                {mode === "glossary" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--kb)" }} />}
              </div>
              {t("createModal.fromGlossary")} <span className="text-[10px]" style={{ color: "var(--muted)" }}>{t("createModal.glossaryTermsCount", { count: glossaryCount })}</span>
            </button>
          )}
          <button type="button" onClick={() => selectedSource && setMode("source")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
            style={{
              ...(mode === "source"
                ? { border: "1.5px solid var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--background)" }),
              color: "var(--foreground)",
              opacity: selectedSource ? 1 : 0.4,
              pointerEvents: selectedSource ? "auto" : "none",
            }}>
            <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
              style={{ borderColor: mode === "source" ? "var(--kb)" : "var(--border)" }}>
              {mode === "source" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--kb)" }} />}
            </div>
            {t("createModal.fromSelectedSource")} {selectedSource && <span className="text-[10px] inline-block max-w-[120px] truncate align-bottom" title={selectedSource.filename} style={{ color: "var(--muted)" }}>({selectedSource.filename})</span>}
          </button>
          {!selectedSource && (
            <p className="text-[10px] ml-5" style={{ color: "#c4820e" }}>
              {t("createModal.noSourceHint")}
            </p>
          )}
        </div>

        {/* Count */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.countHeading")}</div>
        <div className="flex gap-1.5 mb-4">
          {[5, 10, 15].map((n) => (
            <button key={n} type="button" onClick={() => setCount(n)}
              className="flex-1 py-2 rounded-lg text-xs font-semibold transition-all text-center"
              style={count === n
                ? { border: "1.5px solid var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)", color: "var(--kb)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--background)", color: "var(--foreground)" }}>
              {n}
            </button>
          ))}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button type="button" onClick={onClose}
            className="btn-cancel px-4 py-2 rounded-full text-xs font-semibold"
            style={{ color: "var(--kb)", backgroundColor: "var(--surface)", border: "2px solid var(--border)" }}>
            {t("common.cancel")}
          </button>
          <button type="button" onClick={() => onCreate(mode, count)}
            className="btn-fill-accent flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all">
            <Sparkle size={12} weight="bold" />
            {t("common.create")}
          </button>
        </div>
      </div>
    </div>
  );
}
