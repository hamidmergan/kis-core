import { useEffect, useState } from "react";
import { Sparkle } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { GrammarType } from "../../_types";

export function CreateSetModal({
  tool, glossaryCount, selectedSources, workspaceUuid,
  onClose, onCreate,
}: {
  tool: string; glossaryCount: number; selectedSources?: { uuid: string; filename: string }[] | null;
  workspaceUuid: string;
  onClose: () => void;
  onCreate: (mode: string, count: number, grammarType?: string) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const pickedSources = selectedSources ?? [];
  const hasSource = pickedSources.length > 0;
  // One source shows its filename, several show the count (the full list goes in the tooltip)
  const sourceHint = pickedSources.length === 1
    ? pickedSources[0].filename
    : t("createModal.selectedSourcesCount", { count: pickedSources.length });
  const isQuiz = tool === "quiz";
  // The grammar tool rewrites sentences about the source content, so it has no
  // glossary mode at all.
  const isGrammar = tool === "grammatik";
  const [mode, setMode] = useState<"glossary" | "source">(
    isQuiz || isGrammar || glossaryCount === 0 ? "source" : "glossary",
  );
  const [count, setCount] = useState(isQuiz ? 5 : 10);

  // The catalogue is owner-configurable per workspace, so it is fetched rather
  // than hardcoded here: a new exercise type shows up without a frontend change.
  const [grammarTypes, setGrammarTypes] = useState<GrammarType[]>([]);
  const [grammarType, setGrammarType] = useState<string>("");
  const [typesLoading, setTypesLoading] = useState(false);
  useEffect(() => {
    if (!isGrammar) return;
    let cancelled = false;
    setTypesLoading(true);
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/grammar-types`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data?.types) return;
        setGrammarTypes(data.types);
        setGrammarType((prev) => prev || data.types[0]?.id || "");
      })
      .catch(() => { /* the create button stays disabled */ })
      .finally(() => { if (!cancelled) setTypesLoading(false); });
    return () => { cancelled = true; };
  }, [isGrammar, workspaceUuid]);

  const toolLabel = (() => {
    const map: Record<string, string> = {
      karteikarten: t("tools.karteikarten"),
      flashcards: t("tools.flashcards"),
      grammatik: t("tools.grammar"),
      quiz: t("tools.quiz"),
    };
    return map[tool] || t("tools.exerciseFallback");
  })();

  const canCreate = isGrammar ? Boolean(hasSource && grammarType) : true;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-[340px] max-h-[85vh] overflow-y-auto" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">{t("createModal.title", { tool: toolLabel })}</h3>

        {/* Mode */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.sourceHeading")}</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && !isGrammar && (
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
          <button type="button" onClick={() => hasSource && setMode("source")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-[11px] font-medium transition-all text-left"
            style={{
              ...(mode === "source"
                ? { border: "1.5px solid var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }
                : { border: "1.5px solid var(--border)", backgroundColor: "var(--background)" }),
              color: "var(--foreground)",
              opacity: hasSource ? 1 : 0.4,
              pointerEvents: hasSource ? "auto" : "none",
            }}>
            <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0"
              style={{ borderColor: mode === "source" ? "var(--kb)" : "var(--border)" }}>
              {mode === "source" && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--kb)" }} />}
            </div>
            {t("createModal.fromSelectedSource", { count: pickedSources.length })} {hasSource && <span className="text-[10px] inline-block max-w-[120px] truncate align-bottom" title={pickedSources.map((s) => s.filename).join("\n")} style={{ color: "var(--muted)" }}>({sourceHint})</span>}
          </button>
          {!hasSource && (
            <p className="text-[10px] ml-5" style={{ color: "#c4820e" }}>
              {t("createModal.noSourceHint")}
            </p>
          )}
        </div>

        {/* Grammar exercise type */}
        {isGrammar && (
          <>
            <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.grammarTypeHeading")}</div>
            <div className="flex flex-col gap-1.5 mb-3">
              {typesLoading && (
                <p className="text-[10px]" style={{ color: "var(--muted)" }}>{t("common.loading")}</p>
              )}
              {!typesLoading && grammarTypes.length === 0 && (
                <p className="text-[10px]" style={{ color: "#c4820e" }}>{t("createModal.noGrammarTypes")}</p>
              )}
              {grammarTypes.map((gt) => (
                <button key={gt.id} type="button" onClick={() => setGrammarType(gt.id)}
                  className="flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all"
                  style={grammarType === gt.id
                    ? { border: "1.5px solid var(--kb)", backgroundColor: "rgba(var(--kb-rgb),0.07)" }
                    : { border: "1.5px solid var(--border)", backgroundColor: "var(--background)" }}>
                  <div className="w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 mt-0.5"
                    style={{ borderColor: grammarType === gt.id ? "var(--kb)" : "var(--border)" }}>
                    {grammarType === gt.id && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: "var(--kb)" }} />}
                  </div>
                  {/* Label only. The instruction is the worksheet line ("transform
                      according to the pattern below") and reads identically for every
                      type, so it belongs above the sentences, not in the picker. */}
                  <span className="min-w-0">
                    <span className="block text-[11px] font-semibold" style={{ color: "var(--foreground)" }}>{gt.label}</span>
                  </span>
                </button>
              ))}
            </div>
          </>
        )}

        {/* Count */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{isGrammar ? t("createModal.sentenceCountHeading") : t("createModal.countHeading")}</div>
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
          <button type="button" onClick={() => onCreate(mode, count, isGrammar ? grammarType : undefined)}
            disabled={!canCreate}
            className="btn-fill-accent flex-1 flex items-center justify-center gap-1.5 py-2 rounded-full text-xs font-semibold transition-all disabled:opacity-50">
            <Sparkle size={12} weight="bold" />
            {t("common.create")}
          </button>
        </div>
      </div>
    </div>
  );
}
