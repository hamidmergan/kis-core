import React from "react";
import { CaretRight } from "@phosphor-icons/react";
import { _chunkLabel, type ChipLabelT } from "../../_utils";
import type { ChatMessage } from "../../_types";
import { citationPattern, citationsAreAdjacentSameTarget, stripCitations, type CitationFields } from "./_citation_parse";


export type CitationChipClickHandler = (
  sourceUuid: string,
  page: number,
  filename: string,
  sourceText?: string,
  startTime?: number,
  isExact?: boolean,
) => void;


// Resolved, render-ready data for one chip. A chip may stand for several merged
// citations of the same source+page (collapsed into one during parsing).
interface ChipDesc {
  key: string;
  filename: string;
  displayQNum: number | null;
  label: string;
  clickUuid: string;
  clickPage: number;
  clickSeconds: number | undefined;
  clickHighlight: string | undefined;
  isExactSelection: boolean;
  start: number;   // token span start in the answer text
  end: number;     // token span end in the answer text
}


// Renders a single citation chip that links back to the source viewer.
// Clicking a chip only scrolls to the page/timestamp — no highlight — UNLESS it is a
// popup/action-bar exact selection, which still passes its verbatim text to highlight.
function CitationChip({ desc, onChipClick }: { desc: ChipDesc; onChipClick: CitationChipClickHandler }) {
  const { filename, displayQNum, label, clickUuid, clickPage, clickSeconds, clickHighlight, isExactSelection } = desc;
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
      className="inline-flex items-center whitespace-nowrap text-xs px-1.5 py-0.5 rounded-full font-medium chip-cite align-middle mx-0.5 cursor-pointer"
      style={{ backgroundColor: "rgba(var(--kb-rgb),0.12)", color: "var(--kb)" }}
      title={`${filename}, ${label}`}
    >{displayQNum ? `[${displayQNum}] ` : ""}{label}</span>
  );
}


// Expanding is ONE-WAY and sticky: a clicked group opens and never collapses again —
// not on a second click, and not on the re-render/remount churn from streaming tokens
// or the 15s workspace poll. The open set lives at module scope so a fresh mount (which
// resets local state) restores the open state from its stable groupId.
const _openChipGroups = new Set<string>();

// A run of directly-adjacent chips (only whitespace between them). The first chip is
// always shown; the rest stay behind a minimal chevron until the user opens the group.
// Once opened, all chips show and the chevron is gone (nothing to collapse back into).
function CitationChipGroup({ groupId, chips, onChipClick }: { groupId: string; chips: ChipDesc[]; onChipClick: CitationChipClickHandler }) {
  const [open, setOpen] = React.useState(() => _openChipGroups.has(groupId));
  const reveal = () => { _openChipGroups.add(groupId); setOpen(true); };
  if (open) {
    return (
      <span className="inline-flex items-center align-middle">
        {chips.map(c => <CitationChip key={c.key} desc={c} onChipClick={onChipClick} />)}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center align-middle">
      <CitationChip desc={chips[0]} onChipClick={onChipClick} />
      <span role="button" tabIndex={0}
        onPointerDown={(e) => { if (e.button === 0) { e.stopPropagation(); reveal(); } }}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); reveal(); } }}
        aria-label={`+${chips.length - 1}`}
        className="inline-flex items-center align-middle cursor-pointer mx-0.5 text-[var(--kb)] opacity-60 hover:opacity-100 transition-opacity"
      >
        <CaretRight size={11} weight="bold" />
      </span>
    </span>
  );
}


// Parses inline citations like [Q1, S. 2], [1, 05:32], [S. 2] and replaces them with
// CitationChip elements. Text outside matches is returned as-is. Chips are nav-only;
// legacy tokens with a trailing offset/keyword still parse to their page/timestamp.
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
  // With a single source the [n] prefix is redundant — the chip is just "S. X".
  const singleSource = msgQmap.length === 1;
  // Matches [1, S. 2], [Q1, S. 2], [S. 2], [1, 05:32] (Q prefix optional for backwards
  // compat). Optional :uuid suffix on Q-prefix lets notes embed source UUIDs verbatim,
  // so they survive even when the active source selection changes after the note was
  // saved. Legacy trailing "@..|.." tokens are tolerated and discarded. Also accepts
  // CJK lenticular brackets 【】 (U+3010/U+3011): some LLMs emit those despite the prompt.
  // Groups: 1=qnum 2=uuid 3=page 4=timestamp (see _citation_parse).
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
  }

  const parsed: Parsed[] = [];
  let m: RegExpExecArray | null;
  while ((m = pattern.exec(text)) !== null) {
    const qNum = m[1] ? parseInt(m[1]) : null;
    const embeddedUuid = m[2] || null;
    const pageNum = m[3] ? parseInt(m[3]) : 0;
    const timestamp = m[4] || null;
    const qEntry = qNum ? msgQmap.find(q => q.qnum === qNum) : null;
    const sourceUuid = embeddedUuid ?? qEntry?.uuid ?? msgSourcePages[0]?.source_uuid ?? activeSourceIds[0] ?? "";
    const filename = qEntry?.filename ?? getFilename(sourceUuid);
    // Fallback: qnum from qmap via sourceUuid (e.g. popup actions without Q-prefix)
    const displayQNum = singleSource ? null : (qNum ?? msgQmap.find(q => q.uuid === sourceUuid)?.qnum ?? null);
    const label = timestamp || _chunkLabel(filename, pageNum, undefined, tChip);
    let seconds = 0;
    if (timestamp) {
      const tp = timestamp.split(":").map(Number);
      seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
    }
    // Popup/action-bar exact selection: the user marked this verbatim text, so the
    // chip still highlights it exactly (the ONLY remaining chip-driven highlight).
    const popupEntry = msgSourcePages.find(s => s.is_popup_selection && s.source_uuid === sourceUuid && s.page_number === pageNum);
    const popupSel = msg.popup_selection;
    const matchesPopupSel = popupSel && popupSel.uuid === sourceUuid && popupSel.page === pageNum;
    const clickHighlight = popupEntry?.source_text
      ? popupEntry.source_text
      : matchesPopupSel
        ? popupSel!.text
        : undefined;
    const isExactSelection = !!(popupEntry?.source_text || matchesPopupSel);
    parsed.push({
      fields: {
        qNum, uuid: embeddedUuid, page: pageNum, timestamp,
        index: m.index, length: m[0].length,
      },
      sourceUuid, filename, displayQNum, label,
      clickSeconds: timestamp ? seconds : undefined,
      clickHighlight, isExactSelection,
    });
  }

  // Phase 1: merge directly-adjacent citations of the same source+page into one chip
  // (e.g. "[1] S. 15 [1] S. 15"). Popup (exact) selections keep their own chip — they
  // carry verbatim user bounds for the kept highlight.
  const chips: ChipDesc[] = [];
  let chipKeyCounter = 0;
  let i = 0;
  while (i < parsed.length) {
    const head = parsed[i];
    const merged = [head];
    let j = i + 1;
    while (
      j < parsed.length
      && !merged[merged.length - 1].isExactSelection
      && !parsed[j].isExactSelection
      && citationsAreAdjacentSameTarget(
        text, merged[merged.length - 1].fields, parsed[j].fields,
        merged[merged.length - 1].sourceUuid, parsed[j].sourceUuid,
      )
    ) {
      merged.push(parsed[j]);
      j++;
    }
    const tail = merged[merged.length - 1].fields;
    chips.push({
      key: `${keyPrefix}${chipKeyCounter++}`,
      filename: head.filename,
      displayQNum: head.displayQNum,
      label: head.label,
      clickUuid: head.sourceUuid,
      clickPage: head.fields.page,
      clickSeconds: head.clickSeconds,
      clickHighlight: head.clickHighlight,
      isExactSelection: head.isExactSelection,
      start: head.fields.index,
      end: tail.index + tail.length,
    });
    i = j;
  }

  // Phase 2: emit text + chips. A maximal run of chips separated only by whitespace
  // collapses into a CitationChipGroup (first chip shown, rest behind a chevron); lone
  // chips render directly. Exact (popup) chips never fold into a group.
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let k = 0;
  while (k < chips.length) {
    const first = chips[k];
    if (first.start > last) nodes.push(text.slice(last, first.start));

    const run = [first];
    let n = k + 1;
    while (
      n < chips.length
      && !run[run.length - 1].isExactSelection
      && !chips[n].isExactSelection
      && /^\s*$/u.test(text.slice(chips[n - 1].end, chips[n].start))
    ) {
      run.push(chips[n]);
      n++;
    }

    nodes.push(
      run.length > 1
        ? <CitationChipGroup
            key={first.key}
            // Content-based id (source+pages, not text position) so the open state is
            // restored after ANY remount. A collision just re-opens an identical group,
            // which is exactly what the user wants anyway.
            groupId={`${msg.id ?? keyPrefix}#${run.map(c => `${c.clickUuid}:${c.clickPage}`).join(",")}`}
            chips={run}
            onChipClick={onChipClick}
          />
        : <CitationChip key={first.key} desc={first} onChipClick={onChipClick} />,
    );

    last = run[run.length - 1].end;
    k = n;
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
