"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { PencilSimple, Plus, Trash } from "@phosphor-icons/react";
import IconButton from "@/components/ui/IconButton";
import SparkleIcon from "@/components/ui/SparkleIcon";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import Speaker from "../_components/Speaker";
import StepFooter from "../_components/StepFooter";
import { speakerColor } from "../_colors";
import { linesToVoice, minutesOf, needsVoice, wordCount, wordsOf } from "../_logic";
import { FIELD } from "./ContentStep";
import type { Line, Person, PersonCount } from "../_types";

const ACTION = "px-3 py-2 text-sm border-2 border-border rounded-md hover:border-[var(--kb)] hover:text-[var(--kb)] flex items-center gap-1 whitespace-nowrap";

interface ScriptStepProps {
  lines: Line[];
  persons: Person[];
  count: PersonCount;
  voicedIds: string[];
  busy: boolean;
  error: string;
  allDone: boolean;
  /** Written by hand, so the script step offers no model anywhere. */
  selfWritten: boolean;
  /** The instruction named something the material does not cover. */
  instructionUnmatched: boolean;
  /** The contribution whose text is marked, so the chat can work on that spot. */
  regenAnchorIndex: number | null;
  regenAnchorText: string;
  onUpdate: (id: string, text: string) => void;
  onSpeaker: (id: string, speaker: number) => void;
  onRegenAnchor: (index: number | null, text: string) => void;
  onOpenRegen: (index: number) => void;
  onDelete: (id: string) => void;
  onAdd: () => void;
  onBack: (() => void) | null;
  onVoice: () => void;
  onToDone: () => void;
}

export default function ScriptStep(props: ScriptStepProps) {
  const { lines, persons, count, voicedIds, busy, error, allDone, selfWritten,
          instructionUnmatched, regenAnchorIndex, regenAnchorText,
          onUpdate, onSpeaker, onRegenAnchor, onOpenRegen, onDelete, onAdd, onBack, onVoice, onToDone } = props;
  const t = useTranslations("tools.podcast.script");
  const tCast = useTranslations("tools.podcast.cast");
  const tCommon = useTranslations("tools.podcast.common");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [buffer, setBuffer] = useState("");

  if (busy && lines.length === 0 && !selfWritten) {
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20" role="status" aria-live="polite">
        <Spinner size="lg" className="justify-center mb-4" />
        <p className="text-sm text-foreground-soft animate-pulse">{t("generating")}</p>
        <p className="text-xs text-muted-soft mt-2">{t("generatingSubtle", { n: count })}</p>
      </section>
    );
  }

  if (!lines.length) {
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] text-center py-20">
        {selfWritten ? (
          <>
            <p className="text-sm text-muted mb-4">{t("blankEmpty")}</p>
            <button type="button" onClick={onAdd} className={`${ACTION} mx-auto`}>
              <Plus size={14} weight="bold" />
              {t("add")}
            </button>
          </>
        ) : (
          <p className="text-sm text-error">{error || t("generating")}</p>
        )}
      </section>
    );
  }

  const besetzung = persons.slice(0, count).map((p, i) => ({ value: String(i), label: p.name.trim() || t("speakerFallback", { n: i + 1 }) }));
  const offen = linesToVoice(lines, voicedIds).length;
  const schonVertont = voicedIds.length > 0;
  const fertig = offen === 0 && allDone;
  const nextLabel = fertig ? t("nextDone") : schonVertont ? t("nextChanged", { n: offen }) : t("next");
  const unvollstaendig = lines.some((l) => !l.text.trim());

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-2">{t(selfWritten ? "blankHeading" : "heading")}</h2>
      <p className="text-sm text-muted mb-4">{t(selfWritten ? "blankIntro" : "intro")}</p>

      <div className="mb-4 rounded-lg bg-surface px-4 py-3 text-sm text-foreground-soft">
        {t("summary", { lines: lines.length, words: wordsOf(lines), minutes: minutesOf(lines) })}
      </div>

      {instructionUnmatched && (
        <p className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {t("instructionUnmatched")}
        </p>
      )}

      <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label={t("castLegend")}>
        {persons.slice(0, count).map((person, i) => (
          <span key={i} className="rounded-full py-1 pl-1 pr-3" style={{ backgroundColor: speakerColor(i).bg }}>
            <Speaker person={person} role={tCast(`roles.${person.role}`)} index={i} />
          </span>
        ))}
      </div>
      {error && (
        <p className="mb-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {error}
        </p>
      )}

      <div className="space-y-2 mb-4">
        {lines.map((line, i) => {
          const sprecherIdx = persons[line.speaker] ? line.speaker : 0;
          const person = persons[sprecherIdx];
          const farbe = speakerColor(sprecherIdx);
          const isEditing = editingId === line.id;
          const offenerBeitrag = needsVoice(line, voicedIds);
          return (
            <div key={line.id} className="border-2 border-border-soft rounded-lg p-4" style={{ backgroundColor: farbe.bg }}>
              <div className="flex items-center gap-3 mb-2">
                <span className="text-xs text-muted-soft w-5 shrink-0">{i + 1}</span>
                {isEditing && besetzung.length > 1 ? (
                  <Select
                    size="sm"
                    value={String(Math.min(line.speaker, count - 1))}
                    onChange={(wert) => onSpeaker(line.id, Number(wert))}
                    options={besetzung}
                    ariaLabel={t("speakerAria", { n: i + 1 })}
                  />
                ) : (
                  <Speaker person={person} role={tCast(`roles.${person.role}`)} index={sprecherIdx} />
                )}
                {schonVertont && offenerBeitrag && <StatusMark tone="warn" className="text-xs">{t("changed")}</StatusMark>}
                {!offenerBeitrag && <StatusMark tone="success" className="text-xs">{t("voiced")}</StatusMark>}
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
                    {!selfWritten && (
                      <IconButton
                        size="sm"
                        aria-label={t("regen", { n: i + 1 })}
                        title={t("regen", { n: i + 1 })}
                        className={regenAnchorIndex === i && regenAnchorText ? "text-kb" : undefined}
                        onClick={() => onOpenRegen(i)}
                      >
                        <SparkleIcon className="w-3 h-3" />
                      </IconButton>
                    )}
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
                <p
                  className={`text-sm leading-relaxed whitespace-pre-wrap ${line.text ? "text-foreground" : "text-muted-soft italic"}`}
                  onMouseUp={() => {
                    const markiert = window.getSelection()?.toString().trim();
                    onRegenAnchor(markiert ? i : null, markiert || "");
                  }}
                >
                  {line.text || t("emptyLine")}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <button type="button" onClick={onAdd} className={ACTION}>
        <Plus size={14} weight="bold" />
        {t("add")}
      </button>

      <StepFooter
        onBack={onBack}
        nextLabel={nextLabel}
        onNext={fertig ? onToDone : onVoice}
        nextDisabled={busy || unvollstaendig || editingId !== null || (!fertig && offen === 0)}
      />
    </section>
  );
}
