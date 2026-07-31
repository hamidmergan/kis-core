import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Sparkle } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { GrammarType } from "../../_types";

// Every picker in this modal shares one look: 2px border, primary on hover,
// primary + tint for the current choice (same classes as the quiz answers).
// The border must come from a class, not an inline style: an inline border
// always beats `hover:border-kb`, which is why hover used to do nothing here.
const PICK_BOX = "border-2 transition-colors disabled:opacity-40";
const PICK_ON = "border-kb bg-kb/10";
const PICK_OFF = "border-border bg-background enabled:hover:border-kb";

function PickerOption({ selected, disabled, onClick, children }: {
  selected: boolean; disabled?: boolean; onClick: () => void; children: ReactNode;
}) {
  return (
    <button type="button" onClick={onClick} disabled={disabled}
      className={`group flex items-center gap-2 px-3 py-2 rounded-lg text-left text-[11px] font-medium text-foreground ${PICK_BOX} ${selected ? PICK_ON : PICK_OFF}`}>
      <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
        selected ? "border-kb" : `border-border ${disabled ? "" : "group-hover:border-kb"}`}`}>
        {selected && <span className="w-1.5 h-1.5 rounded-full bg-kb" />}
      </span>
      <span className="min-w-0">{children}</span>
    </button>
  );
}

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
  // Hörverstehen fragt nach dem Inhalt einer Aufnahme, im Glossar gibt es keine.
  const isListening = tool === "hoerverstehen";
  const [mode, setMode] = useState<"glossary" | "source">(
    isQuiz || isGrammar || isListening || glossaryCount === 0 ? "source" : "glossary",
  );
  const [count, setCount] = useState(isQuiz || isListening ? 5 : 10);

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
      hoerverstehen: t("tools.listening"),
    };
    return map[tool] || t("tools.exerciseFallback");
  })();

  const canCreate = isGrammar ? Boolean(hasSource && grammarType) : !(isListening && !hasSource);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} onClick={onClose}>
      <div className="rounded-2xl p-5 w-[340px] max-h-[85vh] overflow-y-auto" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">{t("createModal.title", { tool: toolLabel })}</h3>

        {/* Mode */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.sourceHeading")}</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && !isGrammar && !isListening && (
            <PickerOption selected={mode === "glossary"} disabled={glossaryCount === 0}
              onClick={() => setMode("glossary")}>
              {t("createModal.fromGlossary")} <span className="text-[10px] text-muted">{t("createModal.glossaryTermsCount", { count: glossaryCount })}</span>
            </PickerOption>
          )}
          <PickerOption selected={mode === "source"} disabled={!hasSource}
            onClick={() => setMode("source")}>
            {t("createModal.fromSelectedSource", { count: pickedSources.length })} {hasSource && <span className="text-[10px] text-muted inline-block max-w-[120px] truncate align-bottom" title={pickedSources.map((s) => s.filename).join("\n")}>({sourceHint})</span>}
          </PickerOption>
          {!hasSource && (
            <p className="text-[10px] ml-5" style={{ color: "#c4820e" }}>
              {isListening ? t("createModal.noMediaHint") : t("createModal.noSourceHint")}
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
                /* Label only. The instruction is the worksheet line ("transform
                   according to the pattern below") and reads identically for every
                   type, so it belongs above the sentences, not in the picker. */
                <PickerOption key={gt.id} selected={grammarType === gt.id}
                  onClick={() => setGrammarType(gt.id)}>
                  <span className="block font-semibold">{gt.label}</span>
                </PickerOption>
              ))}
            </div>
          </>
        )}

        {/* Count */}
        <div className="text-[9px] font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{isGrammar ? t("createModal.sentenceCountHeading") : t("createModal.countHeading")}</div>
        <div className="flex gap-1.5 mb-4">
          {[5, 10, 15].map((n) => (
            <button key={n} type="button" onClick={() => setCount(n)}
              className={`flex-1 py-2 rounded-lg text-xs font-semibold text-center ${PICK_BOX} ${
                count === n ? `${PICK_ON} text-kb dark:text-foreground` : `${PICK_OFF} text-foreground`}`}>
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
