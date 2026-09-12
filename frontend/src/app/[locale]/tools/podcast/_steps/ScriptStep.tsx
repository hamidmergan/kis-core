"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowsClockwise, PencilSimple, Plus, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import Speaker from "../_components/Speaker";
import StepFooter from "../_components/StepFooter";
import { linesToVoice, minutesOf, wordCount, wordsOf } from "../_logic";
import { FIELD } from "./ContentStep";
import type { Line, Person, PersonCount, Run } from "../_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";
const REPHRASE_MS = 700;

interface ScriptStepProps {
  lines: Line[];
  persons: Person[];
  count: PersonCount;
  generating: boolean;
  run: Run;
  onUpdate: (id: string, text: string) => void;
  onRephrase: (id: string) => void;
  onDelete: (id: string) => void;
  onAdd: () => void;
  onBack: () => void;
  onVoice: () => void;
  onToDone: () => void;
}

export default function ScriptStep(props: ScriptStepProps) {
  const { lines, persons, count, generating, run, onUpdate, onRephrase, onDelete, onAdd, onBack, onVoice, onToDone } = props;
  const t = useTranslations("tools.podcast.script");
  const tVoicing = useTranslations("tools.podcast.voicing");
  const tCast = useTranslations("tools.podcast.cast");
  const tCommon = useTranslations("tools.podcast.common");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [buffer, setBuffer] = useState("");
  const [rephrasingId, setRephrasingId] = useState<string | null>(null);

  if (generating) {
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
        <Spinner size="lg" className="justify-center mb-4" />
        <p className="text-sm text-foreground-soft animate-pulse">{t("generating")}</p>
        <p className="text-xs text-muted-soft mt-2">{t("generatingSubtle", { n: count })}</p>
      </section>
    );
  }

  const toVoice = linesToVoice(lines).length;
  const anyVoiced = lines.some((l) => l.audioOf !== null);
  const allDone = toVoice === 0 && run.status === "done";
  const nextLabel = allDone ? t("nextDone") : anyVoiced ? t("nextChanged", { n: toVoice }) : t("next");
  const incomplete = lines.length === 0 || lines.some((l) => !l.text.trim());

  const rephrase = (id: string) => {
    setRephrasingId(id);
    window.setTimeout(() => {
      onRephrase(id);
      setRephrasingId(null);
    }, REPHRASE_MS);
  };

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-2">{t("heading")}</h2>
      <p className="text-sm text-muted mb-4">{t("intro")}</p>

      <div className="mb-4 rounded-lg bg-surface px-4 py-3 text-sm text-foreground-soft">
        {t("summary", { lines: lines.length, words: wordsOf(lines), minutes: minutesOf(lines) })}
      </div>
      {run.cancelled && (
        <p className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {tVoicing("cancelled")}
        </p>
      )}

      <div className="space-y-2 mb-4">
        {lines.map((line, i) => {
          const person = persons[line.speaker] ?? persons[0];
          const isEditing = editingId === line.id;
          const changed = line.audioOf !== null && line.audioOf !== line.text;
          return (
            <div key={line.id} className="border border-border-soft rounded-lg p-4">
              <div className="flex items-center gap-3 mb-2">
                <span className="text-xs text-muted-soft w-5 shrink-0">{i + 1}</span>
                <Speaker person={person} role={tCast(`roles.${person.role}`)} />
                {changed && <StatusMark tone="warn" className="text-xs">{t("changed")}</StatusMark>}
                {!changed && line.audioOf !== null && <StatusMark tone="success" className="text-xs">{t("voiced")}</StatusMark>}
                <span className="flex-1" />
                {!isEditing && (
                  <>
                    <IconButton
                      size="sm"
                      aria-label={t("edit", { n: i + 1 })}
                      title={t("edit", { n: i + 1 })}
                      onClick={() => {
                        setEditingId(line.id);
                        setBuffer(line.text);
                      }}
                    >
                      <PencilSimple size={12} weight="bold" />
                    </IconButton>
                    <IconButton size="sm" aria-label={t("regen", { n: i + 1 })} title={t("regen", { n: i + 1 })} disabled={rephrasingId !== null} onClick={() => rephrase(line.id)}>
                      {rephrasingId === line.id ? <Spinner size="xs" color="current" /> : <ArrowsClockwise size={12} weight="bold" />}
                    </IconButton>
                    <IconButton size="sm" aria-label={t("delete", { n: i + 1 })} title={t("delete", { n: i + 1 })} onClick={() => onDelete(line.id)}>
                      <Trash size={12} weight="bold" />
                    </IconButton>
                  </>
                )}
              </div>
              {isEditing ? (
                <>
                  <textarea value={buffer} onChange={(e) => setBuffer(e.target.value)} rows={4} className={`${FIELD} resize-y`} aria-label={t("editAria", { n: i + 1 })} autoFocus />
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-muted-soft">{t("wordsApprox", { n: wordCount(buffer) })}</span>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setEditingId(null)} className="btn-cancel px-3 py-1 text-xs text-foreground-soft border border-border rounded transition-colors">
                        {tCommon("cancel")}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          onUpdate(line.id, buffer.trim());
                          setEditingId(null);
                        }}
                        className="px-3 py-1 text-xs btn-primary rounded transition-colors"
                      >
                        {tCommon("save")}
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">{line.text}</p>
              )}
            </div>
          );
        })}
      </div>

      <button type="button" onClick={onAdd} className={ACTION}>
        <Plus size={14} weight="bold" />
        {t("add")}
      </button>

      <StepFooter onBack={onBack} nextLabel={nextLabel} onNext={allDone ? onToDone : onVoice} nextDisabled={incomplete || editingId !== null} />
    </section>
  );
}
