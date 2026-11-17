import { Chat, Lightbulb } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import type { ExerciseItem } from "../../_types";
import { _chunkLabel, _getChipIcon, _md } from "../../_utils";
import { sourceTag } from "./SetSourceLegend";
import { itemSources } from "./_itemSources";

/** The two-sided card: question in front, answer with its sources on the back. */
export function FlipCard({ card, flipped, showHint, numbers, onHint, onLearnMore, onSourceClick }: {
  card: ExerciseItem;
  flipped: boolean;
  showHint: boolean;
  numbers: Record<string, number>;
  /** Missing when the card has no hint and no chat to ask. */
  onHint?: () => void;
  onLearnMore?: () => void;
  onSourceClick?: (filename: string, page: number, startTime?: number, claim?: string) => void;
}) {
  const t = useTranslations("workspace.detail.languageTraining");
  const tChip = useTranslations("sourceChip");
  const srcs = itemSources(card);
  return (
    <div className="w-full" style={{ perspective: 1200, userSelect: "none" }}>
      <div style={{
        position: "relative", width: "100%", minHeight: 300, transformStyle: "preserve-3d",
        transition: "transform 0.5s cubic-bezier(0.4,0,0.2,1)",
        transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)",
      }}>
        {/* Front */}
        <div style={{
          position: "absolute", inset: 0, backfaceVisibility: "hidden", borderRadius: 16,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          padding: "36px 20px", gap: 8, backgroundColor: "var(--surface)",
          border: "1px solid var(--border)",
          boxShadow: "0 4px 20px rgba(0,0,0,0.07)",
        }}>
          <span className="text-3xs font-bold uppercase tracking-widest" >{t("flashcardsLearn.questionLabel")}</span>
          <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "var(--foreground)" }} dangerouslySetInnerHTML={{ __html: _md(card.front) }} />
          <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
            <span />
            {onHint && (
              <button type="button" aria-expanded={showHint}
                title={showHint ? t("common.hintHide") : t("common.hint")}
                onClick={(e) => { e.stopPropagation(); onHint(); }}
                className="btn-soft-accent flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-colors">
                <Lightbulb size={13} weight="bold" /> {t("common.hint")}
              </button>
            )}
          </div>
        </div>
        {/* Back */}
        <div style={{
          position: "absolute", inset: 0, backfaceVisibility: "hidden", transform: "rotateY(180deg)",
          borderRadius: 16, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          padding: "36px 20px 56px", gap: 8,
          backgroundColor: "var(--kb)",
          boxShadow: "0 4px 20px rgba(var(--kb-rgb),0.2)",
        }}>
          <span className="text-3xs font-bold uppercase tracking-widest" style={{ color: "rgba(255,255,255,0.35)" }}>{t("flashcardsLearn.answerLabel")}</span>
          <p className="text-sm text-center leading-relaxed font-semibold" style={{ color: "white" }} dangerouslySetInnerHTML={{ __html: _md(card.back) }} />
          {/* Source left, chat right. The chip sits on the card as part of the answer, hence the light variant. */}
          <div className="absolute bottom-3 left-4 right-4 flex items-end justify-between gap-2">
            <div className="flex items-center gap-1 flex-wrap min-w-0" style={{ maxWidth: "60%" }}>
              {srcs.map((s, si) => {
                const ChipIcon = _getChipIcon(s.source_label);
                return (
                  <button key={si} type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onSourceClick) onSourceClick(s.source_label, s.page_number ?? 1, s.start_time, s.highlight_text || `${card.front} ${card.back}`);
                    }}
                    className="inline-flex items-center gap-0.5 text-3xs font-medium px-2 py-1 rounded-full border-none cursor-pointer transition-all text-white/75 bg-white/15 hover:text-white hover:bg-white/25">
                    <ChipIcon size={10} weight="bold" /> {sourceTag(s.source_label, numbers)}{_chunkLabel(s.source_label, s.page_number ?? 1, s.start_time, (key, vals) => tChip(key, vals))}
                  </button>
                );
              })}
            </div>
            {onLearnMore && (
              <button type="button" onClick={(e) => { e.stopPropagation(); onLearnMore(); }}
                className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border-none cursor-pointer transition-all shrink-0 text-white/55 bg-white/10 hover:text-white hover:bg-white/20">
                <Chat size={13} weight="bold" /> {t("common.learnMore")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
