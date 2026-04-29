import React from "react";
import { _chunkLabel, _getChipIcon } from "../../_utils";
import type { ChatMessage } from "../../_types";


export type CitationChipClickHandler = (
  sourceUuid: string,
  page: number,
  filename: string,
  sourceText?: string,
  startTime?: number,
  isExact?: boolean,
) => void;


// Renders a single citation chip that links back to the source viewer.
function CitationChip({
  filename, displayQNum, label, clickUuid, clickPage, clickSeconds, clickHighlight, isExactSelection, onChipClick,
}: {
  filename: string;
  displayQNum: number | null;
  label: string;
  clickUuid: string;
  clickPage: number;
  clickSeconds: number | undefined;
  clickHighlight: string | undefined;
  isExactSelection: boolean;
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
  );
  return (
    <span role="button" tabIndex={0}
      onPointerDown={(e) => { if (e.button === 0) activate(); }}
      onKeyDown={(e) => { if (e.key === "Enter") activate(); }}
      className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium chip-cite align-middle mx-0.5 cursor-pointer"
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
): React.ReactNode[] {
  const msgSourcePages = msg.source_pages ?? [];
  const msgQmap = msg.source_qmap ?? [];
  // Matches [1, S. 2 | kw], [Q1, S. 2 | kw], [S. 2], [1, 05:32 | kw] (Q prefix optional for backwards compat).
  // Optional :uuid suffix on Q-prefix lets notes embed source UUIDs verbatim, so they survive even when
  // the active source selection changes after the note was saved.
  // Also accept CJK lenticular brackets 【】 (U+3010/U+3011): some LLMs emit those instead of [] despite
  // the prompt — render them as chips rather than raw text.
  const pattern = /[[【](?:Q?(\d+)(?::([a-f0-9]{6,64}))?,\s*)?(?:S\.\s*(\d+)|(\d{1,2}:\d{2}(?::\d{2})?))(?:\s*[|❘]\s*([^\]】]+))?\s*[\]】]/g;
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let chipKeyCounter = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const qNum = m[1] ? parseInt(m[1]) : null;
    const embeddedUuid = m[2] || null;
    const pageNum = m[3] ? parseInt(m[3]) : 0;
    const timestamp = m[4] || null;
    const keywords = m[5]?.trim().replace(/^["']+|["']+$/g, "").trim() || null;
    const qEntry = qNum ? msgQmap.find(q => q.qnum === qNum) : null;
    const sourceUuid = embeddedUuid ?? qEntry?.uuid ?? msgSourcePages[0]?.source_uuid ?? activeSourceIds[0] ?? "";
    const filename = qEntry?.filename ?? getFilename(sourceUuid);
    // Fallback: qnum from qmap via sourceUuid (e.g. popup actions without Q-prefix)
    const displayQNum = qNum ?? msgQmap.find(q => q.uuid === sourceUuid)?.qnum ?? null;
    const label = timestamp || _chunkLabel(filename, pageNum);
    const ck = `${keyPrefix}${chipKeyCounter++}`;
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
    const clickSeconds = timestamp ? seconds : undefined;
    nodes.push(
      <CitationChip
        key={ck}
        filename={filename}
        displayQNum={displayQNum}
        label={label}
        clickUuid={sourceUuid}
        clickPage={pageNum}
        clickSeconds={clickSeconds}
        clickHighlight={clickHighlight}
        isExactSelection={isExactSelection}
        onChipClick={onChipClick}
      />,
    );
    last = pattern.lastIndex;
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
): React.ReactNode {
  const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
  return arr.flatMap((child, idx) =>
    typeof child === "string"
      ? parseCitations(child, msg, activeSourceIds, getFilename, onChipClick, `c${idx}-`)
      : [child],
  );
}


// Strips citation markers and copies the cleaned text to the clipboard.
// Falls back to a hidden textarea for non-secure contexts.
export async function copyMessageText(content: string): Promise<void> {
  const text = content.replace(/[[【](?:Q?\d+(?::[a-f0-9]{6,64})?,\s*)?(?:S\.\s*\d+|\d{1,2}:\d{2}(?::\d{2})?)(?:\s*\|[^\]】]+)?[\]】]/g, "").trim();
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
