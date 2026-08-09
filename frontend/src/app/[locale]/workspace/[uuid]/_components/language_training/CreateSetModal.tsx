import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Plus, Sparkle, Trash } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { backdropClose, newBackdropPress } from "@/components/ui/backdropClose";
import type { GrammarTopic } from "../../_types";
import { GrammarTopicForm } from "./GrammarTopicForm";
import { nextTopicId } from "./_grammarTopics";

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
      className={`group w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-2xs font-medium text-foreground ${PICK_BOX} ${selected ? PICK_ON : PICK_OFF}`}>
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
  onClose, onCreate, canManage = false,
}: {
  tool: string; glossaryCount: number; selectedSources?: { uuid: string; filename: string }[] | null;
  workspaceUuid: string;
  onClose: () => void;
  onCreate: (mode: string, count: number, grammarTopicId?: number) => void;
  /** Eigentuemer oder Tutor. Nur die duerfen Themen anlegen. */
  canManage?: boolean;
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
  // Hör- und Leseverstehen fragt zu den gewählten Quellen, im Glossar stehen nur Begriffe.
  const isListening = tool === "hoerverstehen";
  const [mode, setMode] = useState<"glossary" | "source">(
    isQuiz || isGrammar || isListening || glossaryCount === 0 ? "source" : "glossary",
  );
  const [count, setCount] = useState(isQuiz || isListening ? 5 : 10);
  const press = useRef(newBackdropPress()).current;

  // Die Themen gehoeren dem Kurs und stehen in der Datenbank, nicht im Code. Ein
  // neues Thema erscheint hier also ohne Aenderung an der Oberflaeche.
  const [topics, setTopics] = useState<GrammarTopic[]>([]);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [typesLoading, setTypesLoading] = useState(false);
  const [addingTopic, setAddingTopic] = useState(false);
  const [reload, setReload] = useState(0);
  // Das Thema, das gerade nach einer Bestaetigung fragt. Ein Thema gehoert dem
  // ganzen Kurs und nimmt seinen Aufgaben-Vorrat mit, dafuer ist ein Fehlklick zu
  // teuer. Fertige Saetze bleiben lesbar, darum kuemmert sich das Backend.
  const [confirmTopicId, setConfirmTopicId] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);

  async function removeTopic(topic: GrammarTopic) {
    setDeleting(true);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/grammar-topics/${topic.id}`,
        { method: "DELETE", credentials: "include" },
      );
      if (!res.ok) return;
      setTopicId((prev) => nextTopicId(topics, topic.id, prev));
      setTopics((prev) => prev.filter((t) => t.id !== topic.id));
      setConfirmTopicId(null);
    } catch {
      /* die Liste bleibt stehen, ein zweiter Versuch schadet nicht */
    } finally {
      setDeleting(false);
    }
  }
  useEffect(() => {
    if (!isGrammar) return;
    let cancelled = false;
    setTypesLoading(true);
    fetch(`/api/ai-assistant/workspaces/${workspaceUuid}/grammar-topics`, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data?.topics) return;
        setTopics(data.topics);
        setTopicId((prev) => prev ?? data.topics[0]?.id ?? null);
      })
      .catch(() => { /* der Erstellen-Knopf bleibt gesperrt */ })
      .finally(() => { if (!cancelled) setTypesLoading(false); });
    return () => { cancelled = true; };
  }, [isGrammar, workspaceUuid, reload]);

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

  const canCreate = isGrammar
    ? Boolean(hasSource && topicId && !addingTopic)
    : !(isListening && !hasSource);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ backgroundColor: "rgba(0,0,0,0.25)" }} {...backdropClose(press, onClose)}>
      <div className="rounded-2xl p-5 w-85 max-h-[85vh] overflow-y-auto" style={{ backgroundColor: "var(--surface)", boxShadow: "0 8px 40px rgba(0,0,0,0.12)" }}
        onClick={(e) => e.stopPropagation()}>
        <h3 className="text-sm font-semibold mb-3">{t("createModal.title", { tool: toolLabel })}</h3>

        {/* Mode */}
        <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.sourceHeading")}</div>
        <div className="flex flex-col gap-1.5 mb-3">
          {!isQuiz && !isGrammar && !isListening && (
            <PickerOption selected={mode === "glossary"} disabled={glossaryCount === 0}
              onClick={() => setMode("glossary")}>
              {t("createModal.fromGlossary")} <span className="text-3xs text-muted">{t("createModal.glossaryTermsCount", { count: glossaryCount })}</span>
            </PickerOption>
          )}
          <PickerOption selected={mode === "source"} disabled={!hasSource}
            onClick={() => setMode("source")}>
            {t("createModal.fromSelectedSource", { count: pickedSources.length })} {hasSource && <span className="text-3xs text-muted inline-block max-w-30 truncate align-bottom" title={pickedSources.map((s) => s.filename).join("\n")}>({sourceHint})</span>}
          </PickerOption>
          {!hasSource && (
            <p className="text-3xs ml-5" style={{ color: "#c4820e" }}>
              {t("createModal.noSourceHint")}
            </p>
          )}
        </div>

        {/* Grammar exercise type */}
        {isGrammar && (
          <>
            <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{t("createModal.grammarTypeHeading")}</div>
            <div className="flex flex-col gap-1.5 mb-3">
              {canManage && !addingTopic && (
                /* Anlegen ist Verwaltungsarbeit und keine Auswahl. Deshalb steht
                   der Eintrag ueber der Liste und traegt den gestrichelten
                   Hinzufuegen-Rahmen aus dem Bestand statt eines Auswahlpunkts.
                   Lernende sehen ihn nicht, waehlen duerfen sie aus derselben Liste. */
                <button type="button" onClick={() => setAddingTopic(true)}
                  className={`add-source-btn w-full flex items-center gap-2 px-3 py-2 rounded-lg text-2xs font-medium border-dashed text-[var(--kb)] border-[rgba(var(--kb-rgb),0.35)] hover:border-[var(--kb)] ${PICK_BOX}`}>
                  <Plus size={14} weight="bold" />
                  <span>{t("grammarTopics.addTopic")}</span>
                </button>
              )}
              {typesLoading && (
                <p className="text-3xs" style={{ color: "var(--muted)" }}>{t("common.loading")}</p>
              )}
              {!typesLoading && topics.length === 0 && !addingTopic && (
                <p className="text-3xs" style={{ color: "#c4820e" }}>{t("createModal.noGrammarTypes")}</p>
              )}
              {!addingTopic && topics.map((topic) => (
                confirmTopicId === topic.id ? (
                  /* Die Ruecknahme steht an der Stelle der Zeile und nicht in einem
                     eigenen Fenster: die Liste bleibt sichtbar, und die Frage steht
                     bei dem Thema, um das es geht. */
                  <div key={topic.id} className={`flex flex-col gap-1.5 px-3 py-2 rounded-lg ${PICK_BOX} border-border bg-background`}>
                    <span className="text-2xs text-foreground">
                      {t("grammarTopics.deleteAsk", { name: topic.name })}
                    </span>
                    <div className="flex gap-1.5">
                      <button type="button" disabled={deleting}
                        onClick={() => removeTopic(topic)}
                        className="px-3 py-1 rounded-full text-3xs font-semibold disabled:opacity-50"
                        style={{ backgroundColor: "var(--error)", color: "var(--on-accent)" }}>
                        {t("common.delete")}
                      </button>
                      <button type="button" onClick={() => setConfirmTopicId(null)}
                        className="btn-cancel px-3 py-1 rounded-full text-3xs font-semibold"
                        style={{ color: "var(--kb)", backgroundColor: "var(--surface)", border: "2px solid var(--border)" }}>
                        {t("common.cancel")}
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Nur der Name. Die Anweisung an den Lernenden lautet fuer jedes
                     Thema gleich und gehoert deshalb ueber die Saetze, nicht hierhin.
                     Der Papierkorb liegt ueber der Zeile statt in ihr: ein Knopf im
                     Knopf waere kein gueltiges HTML. */
                  <div key={topic.id} className="relative">
                    <PickerOption selected={topicId === topic.id}
                      onClick={() => setTopicId(topic.id)}>
                      <span className={`block font-semibold ${canManage ? "pr-6" : ""}`}>{topic.name}</span>
                    </PickerOption>
                    {canManage && (
                      <button type="button" onClick={() => setConfirmTopicId(topic.id)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center btn-icon"
                        style={{ backgroundColor: "var(--surface-dim)" }}
                        title={t("grammarTopics.deleteTopic")}>
                        <Trash size={12} />
                      </button>
                    )}
                  </div>
                )
              ))}
              {addingTopic && (
                <GrammarTopicForm
                  workspaceUuid={workspaceUuid}
                  onCancel={() => setAddingTopic(false)}
                  onSaved={(topic) => {
                    setAddingTopic(false);
                    setTopicId(topic.id);
                    setReload((n) => n + 1);
                  }}
                />
              )}
            </div>
          </>
        )}

        {/* Count */}
        <div className="text-3xs font-semibold uppercase tracking-wide mb-1.5" style={{ color: "var(--muted)" }}>{isGrammar ? t("createModal.sentenceCountHeading") : t("createModal.countHeading")}</div>
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
          <button type="button" onClick={() => onCreate(mode, count, isGrammar && topicId ? topicId : undefined)}
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
