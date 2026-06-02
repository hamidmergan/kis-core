import React from "react";
import { _chunkLabel, _getChipIcon, type ChipLabelT } from "../../_utils";
import type { ChatMessage, CitationHighlightSpan } from "../../_types";
import { citationPattern, citationsAreAdjacentSameTarget, stripCitations, type CitationFields } from "./_citation_parse";


export type CitationChipClickHandler = (
  sourceUuid: string,
  page: number,
  filename: string,
  sourceText?: string,
  startTime?: number,
  isExact?: boolean,
  offsets?: [number, number],
  spans?: CitationHighlightSpan[],
) => void;


// Renders a single citation chip that links back to the source viewer. A chip may
// stand for several merged citations of the same source+page (clickSpans), in which
// case one click marks every cited region on that page.
function CitationChip({
  filename, displayQNum, label, clickUuid, clickPage, clickSeconds, clickHighlight, isExactSelection, clickOffsets, clickSpans, onChipClick,
}: {
  filename: string;
  displayQNum: number | null;
  label: string;
  clickUuid: string;
  clickPage: number;
  clickSeconds: number | undefined;
  clickHighlight: string | undefined;
  isExactSelection: boolean;
  clickOffsets: [number, number] | undefined;
  clickSpans: CitationHighlightSpan[] | undefined;
  onChipClick: CitationChipClickHandler;
}) {
  const ChipIcon = _getChipIcon(filename);
  // onPointerDown (not onClick) so chips remain clickable during active token stream:
  // with onClick, react-markdown often unmounts the chip between down and up, so the
  // native click lands on an ancestor. Pointer (not Mouse) so touch devices trigger it.
  const activate = () => onChipClick(
    clickUuid,
    clickSeconds ? 0 : clickPage,
    filename,
    clickSeconds ? undefined : clickHighlight,
    clickSeconds,
    isExactSelection,
    clickSeconds ? undefined : clickOffsets,
    clickSeconds ? undefined : clickSpans,
  );
  return (
    <span role="button" tabIndex={0}
      onPointerDown={(e) => { if (e.button === 0) activate(); }}
      onKeyDown={(e) => { if (e.key === "Enter") activate(); }}
      className="inline-flex items-center gap-0.5 whitespace-nowrap text-xs px-1.5 py-0.5 rounded-full font-medium chip-cite align-middle mx-0.5 cursor-pointer"
      style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
      title={`${filename}, ${label}`}
    ><ChipIcon size={8} weight="bold" />{displayQNum ? `[${displayQNum}] ` : ""}{label}</span>
  );
}


// Parses inline citations like [Q1, S. 2 | keyword], [1, 05:32], [S. 2] and
// replaces them with CitationChip elements. Text outside matches is returned as-is.
export function parseCitations(
  text: string,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  keyPrefix: string = "c",
  tChip?: ChipLabelT,
): React.ReactNode[] {
  const msgSourcePages = msg.source_pages ?? [];
  const msgQmap = msg.source_qmap ?? [];
  // Matches [1, S. 2 | kw], [Q1, S. 2 | kw], [S. 2], [1, 05:32 | kw] (Q prefix optional for backwards compat).
  // Optional :uuid suffix on Q-prefix lets notes embed source UUIDs verbatim, so they survive even when
  // the active source selection changes after the note was saved.
  // Optional @start-end after the page = Architecture-B exact character span into the page's pdfium text.
  // Also accept CJK lenticular brackets 【】 (U+3010/U+3011): some LLMs emit those instead of [] despite
  // the prompt — render them as chips rather than raw text.
  // Groups: 1=qnum 2=uuid 3=page 4=offStart 5=offEnd 6=timestamp 7=keyword/span (see _citation_parse).
  const pattern = citationPattern();

  // Resolved per-token data, kept with the raw parsed fields so adjacent tokens of
  // the same source+page can be merged into one chip afterwards.
  interface Parsed {
    fields: CitationFields;
    sourceUuid: string;
    filename: string;
    displayQNum: number | null;
    label: string;
    clickSeconds: number | undefined;
    clickHighlight: string | undefined;
    isExactSelection: boolean;
    clickOffsets: [number, number] | undefined;
    keyword: string | null;
  }

  const parsed: Parsed[] = [];
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    const qNum = m[1] ? parseInt(m[1]) : null;
    const embeddedUuid = m[2] || null;
    const pageNum = m[3] ? parseInt(m[3]) : 0;
    const offsets: [number, number] | undefined =
      m[4] && m[5] ? [parseInt(m[4]), parseInt(m[5])] : undefined;
    const timestamp = m[6] || null;
    const keywords = m[7]?.trim().replace(/^["']+|["']+$/g, "").trim() || null;
    const qEntry = qNum ? msgQmap.find(q => q.qnum === qNum) : null;
    const sourceUuid = embeddedUuid ?? qEntry?.uuid ?? msgSourcePages[0]?.source_uuid ?? activeSourceIds[0] ?? "";
    const filename = qEntry?.filename ?? getFilename(sourceUuid);
    // Fallback: qnum from qmap via sourceUuid (e.g. popup actions without Q-prefix)
    const displayQNum = qNum ?? msgQmap.find(q => q.uuid === sourceUuid)?.qnum ?? null;
    const label = timestamp || _chunkLabel(filename, pageNum, undefined, tChip);
    let seconds = 0;
    if (timestamp) {
      const tp = timestamp.split(":").map(Number);
      seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
    }
    // Popup action: use marked text as highlight
    const popupEntry = msgSourcePages.find(s => s.is_popup_selection && s.source_uuid === sourceUuid && s.page_number === pageNum);
    const popupSel = msg.popup_selection;
    const matchesPopupSel = popupSel && popupSel.uuid === sourceUuid && popupSel.page === pageNum;
    const clickHighlight = popupEntry?.source_text
      ? popupEntry.source_text
      : matchesPopupSel
        ? popupSel!.text
        : (keywords || undefined);
    const isExactSelection = !!(popupEntry?.source_text || matchesPopupSel);
    // A popup selection carries its own verbatim bounds, so server offsets (if any)
    // are ignored there; otherwise pass the exact span offsets through to the viewer.
    const clickOffsets = isExactSelection ? undefined : offsets;
    parsed.push({
      fields: {
        qNum, uuid: embeddedUuid, page: pageNum, offsets, timestamp,
        keyword: keywords, index: m.index, length: m[0].length,
      },
      sourceUuid, filename, displayQNum, label,
      clickSeconds: timestamp ? seconds : undefined,
      clickHighlight, isExactSelection, clickOffsets, keyword: keywords,
    });
  }

  const nodes: React.ReactNode[] = [];
  let last = 0;
  let chipKeyCounter = 0;
  let i = 0;
  while (i < parsed.length) {
    const head = parsed[i];
    if (head.fields.index > last) nodes.push(text.slice(last, head.fields.index));

    // Greedily gather directly-adjacent citations of the same source+page. Popup
    // (exact) selections keep their own chip — they carry verbatim user bounds.
    const group = [head];
    let j = i + 1;
    while (
      j < parsed.length
      && !group[group.length - 1].isExactSelection
      && !parsed[j].isExactSelection
      && citationsAreAdjacentSameTarget(
        text, group[group.length - 1].fields, parsed[j].fields,
        group[group.length - 1].sourceUuid, parsed[j].sourceUuid,
      )
    ) {
      group.push(parsed[j]);
      j++;
    }

    // Build one highlight span per cited region, de-duplicating identical ones so a
    // repeated "[1] S. 15 [1] S. 15" doesn't draw the same mark twice.
    let clickSpans: CitationHighlightSpan[] | undefined;
    if (group.length > 1) {
      const seen = new Set<string>();
      const spans: CitationHighlightSpan[] = [];
      for (const g of group) {
        const span: CitationHighlightSpan = {
          offsets: g.clickOffsets,
          keyword: g.clickHighlight,
        };
        const key = `${span.offsets ? span.offsets.join("-") : ""}|${span.keyword ?? ""}`;
        if (seen.has(key)) continue;
        seen.add(key);
        spans.push(span);
      }
      clickSpans = spans.length > 1 ? spans : undefined;
    }

    nodes.push(
      <CitationChip
        key={`${keyPrefix}${chipKeyCounter++}`}
        filename={head.filename}
        displayQNum={head.displayQNum}
        label={head.label}
        clickUuid={head.sourceUuid}
        clickPage={head.fields.page}
        clickSeconds={head.clickSeconds}
        clickHighlight={head.clickHighlight}
        isExactSelection={head.isExactSelection}
        clickOffsets={head.clickOffsets}
        clickSpans={clickSpans}
        onChipClick={onChipClick}
      />,
    );

    const tail = group[group.length - 1].fields;
    last = tail.index + tail.length;
    i = j;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}


export function withCitations(
  children: React.ReactNode,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  tChip?: ChipLabelT,
): React.ReactNode {
  const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
  return arr.flatMap((child, idx) =>
    typeof child === "string"
      ? parseCitations(child, msg, activeSourceIds, getFilename, onChipClick, `c${idx}-`, tChip)
      : [child],
  );
}


// Strips citation markers and copies the cleaned text to the clipboard.
// Falls back to a hidden textarea for non-secure contexts.
export async function copyMessageText(content: string): Promise<void> {
  const text = stripCitations(content).trim();
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  document.execCommand("copy");
  document.body.removeChild(ta);
}
