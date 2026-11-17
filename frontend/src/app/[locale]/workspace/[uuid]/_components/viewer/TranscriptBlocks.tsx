import React from "react";
import { useTranslations } from "next-intl";
import { Check, NotePencil, PencilSimple } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { CueBlock, SentenceSpan } from "./_transcript";
import { fmtTs, type Cue } from "./_vtt";

/** The paragraphs of the transcript, each one plays, saves as a note and opens for correcting. */
export function TranscriptBlocks({
  listRef,
  itemRefs,
  blocks,
  cues,
  sourceLang,
  targetLang,
  showSource,
  showTarget,
  currentIdx,
  boldSpans,
  citationIdx,
  citationEndIdx,
  citationClaimIdxs,
  onUserScroll,
  onBlockClick,
  correcting,
  onEditBlock,
  canSaveNote,
  savingCueIdx,
  savedCueIdx,
  onSaveBlock,
}: {
  listRef: React.RefObject<HTMLDivElement | null>;
  // The anchors hang off the sentence, not off the paragraph.
  itemRefs: React.RefObject<Record<number, HTMLElement | null>>;
  blocks: CueBlock[];
  cues: Record<string, Cue[]>;
  sourceLang: string | null;
  targetLang: string | null;
  showSource: boolean;
  showTarget: boolean;
  currentIdx: number;
  boldSpans: Record<string, SentenceSpan | null>;
  citationIdx: number;
  citationEndIdx: number;
  citationClaimIdxs: number[];
  // Wheel, touch or key inside the list, the person took over the scrolling.
  onUserScroll: () => void;
  onBlockClick: (start: number) => void;
  correcting: boolean;
  onEditBlock: (block: CueBlock) => void;
  canSaveNote: boolean;
  savingCueIdx: number | null;
  savedCueIdx: number | null;
  onSaveBlock: (from: number, to: number) => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  // Only one of the two tracks carries the scroll anchors.
  const anchorTrack = showSource ? sourceLang : targetLang;

  const sentences = (b: CueBlock, lang: string | null) => {
    if (!lang) return null;
    const track = cues[lang];
    if (!track) return null;
    const span = boldSpans[lang] ?? null;
    const out: React.ReactNode[] = [];
    for (let i = b.from; i <= b.to; i++) {
      const text = track[i]?.text?.trim();
      if (!text) continue;
      // The running sentence starts and ends inside a line as often as on its border.
      const marked = !!span && i >= span.fromIdx && i <= span.toIdx;
      const markFrom = marked && i === span.fromIdx ? span.fromChar : 0;
      const markTo = marked && i === span.toIdx ? span.toChar : text.length;
      out.push(
        <span
          key={i}
          ref={lang === anchorTrack ? (el) => { itemRefs.current[i] = el; } : undefined}
        >
          {marked ? (
            <>
              {text.slice(0, markFrom)}
              <span style={{ fontWeight: 600 }}>{text.slice(markFrom, markTo)}</span>
              {text.slice(markTo)}
            </>
          ) : text}
          {i < b.to ? " " : ""}
        </span>,
      );
    }
    return out;
  };

  return (
    <div
      ref={listRef}
      className="flex-1 overflow-y-auto px-4 py-3"
      onWheel={onUserScroll}
      onTouchStart={onUserScroll}
      onKeyDown={onUserScroll}
    >
      {blocks.map((b) => {
        // The running paragraph, the sentence inside it stays separately emphasised.
        const isCurrent = currentIdx >= b.from && currentIdx <= b.to;
        const isPast = currentIdx >= 0 && b.to < currentIdx;
        // The paragraph area is highlighted, and only one shade.
        const hasCitation = citationClaimIdxs.length > 0
          ? citationClaimIdxs.some((i) => i >= b.from && i <= b.to)
          : citationIdx >= 0 && b.from <= citationEndIdx && b.to >= citationIdx;

        return (
          <div
            key={b.from}
            className="group mb-2"
            style={{ opacity: !isCurrent && !hasCitation && isPast ? 0.55 : 1 }}
          >
            <div
              className="px-3 py-2 rounded-md cursor-pointer transition-colors"
              onClick={() => onBlockClick(b.start)}
              style={{
                // The highlight always wins the background.
                backgroundColor: hasCitation
                  ? "var(--cite-bg)"
                  : isCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
                // The running paragraph gets the frame, the highlight only the area.
                border: isCurrent ? "2px solid var(--kb)" : "2px solid transparent",
                borderLeft: isCurrent ? "3px solid var(--kb)" : "3px solid transparent",
              }}
              onMouseEnter={(e) => {
                if (!isCurrent && !hasCitation) e.currentTarget.style.backgroundColor = "var(--surface-dim)";
              }}
              onMouseLeave={(e) => {
                if (!isCurrent && !hasCitation) e.currentTarget.style.backgroundColor = "transparent";
              }}
            >
              <div
                className="text-3xs font-mono mb-1"
                style={{ color: "var(--muted)" }}
              >
                {fmtTs(b.start)} - {fmtTs(b.end)}
              </div>
              {showSource && (
                <div className="text-sm leading-snug" style={{ color: "var(--foreground)" }}>
                  {sentences(b, sourceLang)}
                </div>
              )}
              {showTarget && (
                <div
                  className="text-sm italic leading-snug mt-0.5"
                  style={{ color: "var(--muted)" }}
                >
                  {sentences(b, targetLang)}
                </div>
              )}
            </div>
            {(canSaveNote || correcting) && (
              <div className="flex justify-end gap-1 pr-1 mt-0.5 h-5">
                {correcting && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); onEditBlock(b); }}
                    title={t("transcriptEditTitle")}
                    aria-label={t("transcriptEditTitle")}
                    className="p-1 rounded-full btn-icon"
                    style={{ color: "var(--kb)" }}
                  >
                    <PencilSimple size={14} weight="bold" />
                  </button>
                )}
                {canSaveNote && (
                <button
                  type="button"
                  data-tour="transcript-note"
                  disabled={savingCueIdx === b.from}
                  onClick={(e) => { e.stopPropagation(); onSaveBlock(b.from, b.to); }}
                  title={t("saveAsNote")}
                  className={`[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 p-1 rounded-full ${savedCueIdx === b.from ? "" : "btn-icon"}`}
                  style={savedCueIdx === b.from ? { color: "var(--success)" } : undefined}
                >
                  {savingCueIdx === b.from
                    ? <Spinner size="xs" color="current" />
                    : savedCueIdx === b.from ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
                </button>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
