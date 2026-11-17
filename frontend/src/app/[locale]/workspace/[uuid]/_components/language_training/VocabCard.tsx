import React from "react";
import { Chat, SpeakerHigh } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import HelpTooltip from "@/components/ui/HelpTooltip";
import IconButton from "@/components/ui/IconButton";
import type { ExerciseItem } from "../../_types";
import { splitExample } from "./_termHighlight";
import { ItemSourceChips } from "./ItemSourceChips";

/** State of the pronunciation player, it lives in the view so the audio survives paging. */
export interface SpeechControl {
  playingId: string | null;
  loadingId: string | null;
  failedId: string | null;
  /** Missing when the set has no pronunciation. */
  play?: (itemId: number) => void;
}

function FormRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-1.5 text-sm">
      <span className="font-semibold shrink-0" style={{ color: "var(--foreground)" }}>{label}</span>
      {children}
    </div>
  );
}

/** A vocabulary term on one page: definition, word parts, forms, example, sources. */
export function VocabCard({ card, showTranslation, speech, numbers, onSourceClick, onLearnMore }: {
  card: ExerciseItem;
  showTranslation?: boolean;
  speech: SpeechControl;
  numbers: Record<string, number>;
  onSourceClick?: (filename: string, page: number, startTime?: number, claim?: string) => void;
  onLearnMore?: () => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const definition = (card.back || "").trim();
  const wordParts = card.extras?.word_parts?.trim() || "";
  const wordPartsExplained = card.extras?.word_parts_explained?.trim() || "";
  const exampleSentence = card.extras?.example_sentence?.trim() || "";
  const wordClass = card.extras?.word_class?.trim() || "";
  const singular = card.extras?.singular?.trim() || "";
  const plural = card.extras?.plural?.trim() || "";
  const verbPresent = card.extras?.verb_present?.trim() || "";
  const verbPast = card.extras?.verb_past?.trim() || "";
  const verbPerfect = card.extras?.verb_perfect?.trim() || "";
  const verbPreposition = card.extras?.verb_preposition?.trim() || "";
  // Every line on its own so a half-filled card shows no empty rows.
  const hasVerbForms = Boolean(verbPresent || verbPast || verbPerfect);
  const speechKey = String(card.id);
  const running = speech.playingId === speechKey;
  const speechLabel = running ? t("flashcardsLearn.stopExample") : t("flashcardsLearn.playExample");
  const explainedParts = wordPartsExplained.split("|").map(p => p.trim()).filter(Boolean);

  return (
    <div className="rounded-2xl overflow-hidden" style={{ backgroundColor: "var(--surface)", boxShadow: "0 4px 20px rgba(0,0,0,0.07)" }}>
      <div className="p-5 flex flex-col gap-4">
        {/* Term */}
        <div className="text-center">
          <p className="text-lg leading-relaxed font-semibold" style={{ color: "var(--foreground)" }}>
            {card.front}
            {/* The fixed preposition is learned together with the verb, so it sits right next to it. */}
            {verbPreposition && <span className="font-normal"> ({verbPreposition})</span>}
          </p>
          {showTranslation && card.back_en && (
            <p className="text-sm italic mt-0.5" >{t("flashcardsLearn.translationPrefix")} {card.back_en}</p>
          )}
        </div>
        {/* Definition */}
        <div>
          <span className="inline-flex items-center gap-1">
            <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.definition")}</span>
            {/* Says the wording is the model's, not a quote from the material. */}
            <HelpTooltip text={t("common.aiKnowledgeHint")} />
          </span>
          <p className="text-base leading-relaxed mt-1" style={{ color: "var(--foreground)" }}>{definition}</p>
        </div>
        {/* Word parts */}
        {wordParts && (
          <div className="px-3 py-2.5 rounded-xl" style={{ backgroundColor: "var(--surface-dim)" }}>
            <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.wordParts")}</span>
            <p className="text-base font-semibold mt-1.5" style={{ color: "var(--foreground)" }}>{wordParts}</p>
            {explainedParts.length > 0 && (
              <div className="flex flex-col gap-1 mt-2">
                {explainedParts.map((part, pi) => {
                  const [term, ...rest] = part.split("=");
                  const explanation = rest.join("=").trim();
                  // The colon comes from the view and never twice.
                  const label = term.trim().replace(/[:=]+$/, "");
                  return (
                    <FormRow key={pi} label={`${label}:`}>
                      {explanation && <span >{explanation}</span>}
                    </FormRow>
                  );
                })}
              </div>
            )}
          </div>
        )}
        {/* Word class first, then the number forms when present, no box */}
        {(wordClass || singular || hasVerbForms) && (
          <div className="flex flex-col gap-1 px-1">
            {wordClass && <FormRow label={t("flashcardsLearn.wordClass")}><span >{wordClass}</span></FormRow>}
            {singular && (
              <>
                <FormRow label={t("flashcardsLearn.singular")}><span >{singular}</span></FormRow>
                {/* A noun without a plural still shows the row so every card reads the same. */}
                <FormRow label={t("flashcardsLearn.plural")}>
                  {plural ? <span >{plural}</span> : <span className="italic">{t("flashcardsLearn.noPlural")}</span>}
                </FormRow>
              </>
            )}
            {verbPresent && <FormRow label={t("flashcardsLearn.verbPresent")}><span>{verbPresent}</span></FormRow>}
            {verbPast && <FormRow label={t("flashcardsLearn.verbPast")}><span>{verbPast}</span></FormRow>}
            {verbPerfect && <FormRow label={t("flashcardsLearn.verbPerfect")}><span>{verbPerfect}</span></FormRow>}
          </div>
        )}
        {/* Context sentence */}
        {exampleSentence && (
          <div className="px-3 py-2.5 rounded-xl" style={{ border: "1px solid var(--border)" }}>
            <div className="flex items-center justify-between gap-2">
              <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.example")}</span>
              {speech.play && (
                <IconButton
                  size="sm"
                  onClick={() => speech.play?.(card.id)}
                  title={speechLabel}
                  aria-label={speechLabel}
                >
                  {speech.loadingId === speechKey ? <Spinner size="sm" /> : (
                    <SpeakerHigh size={12} weight="bold" style={{ color: running ? "var(--kb)" : undefined }} />
                  )}
                </IconButton>
              )}
            </div>
            <p className="text-sm italic leading-relaxed mt-1" style={{ color: "var(--foreground)" }}>
              {/* The learned word is bold so the topic is visible at once. */}
              {splitExample(exampleSentence, [card.front, singular, plural, verbPresent, verbPast, verbPerfect]).map((seg, si) => (
                seg.focus
                  ? <strong key={si} className="font-bold">{seg.text}</strong>
                  : <React.Fragment key={si}>{seg.text}</React.Fragment>
              ))}
            </p>
            {/* No box, no expand: a plain line that disappears on the next speaker click. */}
            {speech.failedId === speechKey && (
              <p className="text-3xs mt-1.5" style={{ color: "var(--muted)" }}>{t("flashcardsLearn.speechFailed")}</p>
            )}
          </div>
        )}
        {/* Sources + Chat */}
        <ItemSourceChips card={card} numbers={numbers} onSourceClick={onSourceClick} firstPageDefault />
        <div className="flex items-center justify-end">
          {onLearnMore && (
            <button type="button" onClick={onLearnMore}
              className="btn-soft-accent inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-full transition-colors">
              <Chat size={12} weight="bold" /> {t("common.learnMore")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
