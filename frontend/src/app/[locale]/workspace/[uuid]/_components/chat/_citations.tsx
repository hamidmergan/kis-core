import React from "react";
import { _chunkLabel, type ChipLabelT } from "../../_utils";
import type { ChatMessage } from "../../_types";
import { citationPattern, citationsAreAdjacentSameTarget, stripCitations, type CitationFields } from "./_citation_parse";
import { CITATION_HL_COLOR } from "../viewer/_highlight";


// The single citation target (source + page/timestamp) currently framed in the viewer,
// i.e. the last clicked chip. Mirrors the viewer's one-frame-at-a-time behaviour so the
// active chip wears the SAME yellow border as the page frame. Module scope (like
// _openChipGroups below) so the active state survives the remount churn of streaming /
// the 15s poll. Chips subscribe individually, so a click re-renders only the
// previously- and newly-active chip, not the whole message tree.
let _activeChipTarget: string | null = null;
const _activeChipSubs = new Set<() => void>();

// A chip's identity for "active" matching: source + page (PDF) or source + seconds
// (media). Two chips for the same target light up together — consistent, since the
// viewer frames exactly that one page either way.
function chipTargetKey(uuid: string, page: number, seconds: number | undefined): string {
  return seconds != null ? `${uuid}@t${seconds}` : `${uuid}@p${page}`;
}

function setActiveChipTarget(key: string): void {
  if (_activeChipTarget === key) return;
  _activeChipTarget = key;
  _activeChipSubs.forEach((fn) => fn());
}

// Drop the active chip's yellow border. Called when the viewer's page frame is
// dismissed (the X button bottom-right of the PDF), so the chip in the chat loses its
// frame in lock-step with the page. No-op when no chip is active.
export function clearActiveChipTarget(): void {
  if (_activeChipTarget === null) return;
  _activeChipTarget = null;
  _activeChipSubs.forEach((fn) => fn());
}

function useIsActiveChip(key: string): boolean {
  const subscribe = React.useCallback((cb: () => void) => {
    _activeChipSubs.add(cb);
    return () => { _activeChipSubs.delete(cb); };
  }, []);
  const getSnapshot = React.useCallback(() => _activeChipTarget === key, [key]);
  return React.useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}


export type CitationChipClickHandler = (
  sourceUuid: string,
  page: number,
  filename: string,
  sourceText?: string,
  startTime?: number,
  isExact?: boolean,
  // End of the cited chunk, so the transcript can mark the WHOLE cited passage instead
  // of just the subtitle cue that happens to start at startTime.
  endTime?: number,
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
  clickEndSeconds: number | undefined;
  clickHighlight: string | undefined;
  isExactSelection: boolean;
  // The stretch of ANSWER text this chip backs up: everything between the previous chip stop
  // and this one. Sent along on a media click so the transcript can weight the line that
  // carries it inside the roughly minute-long marked span. Filled in when the chips are
  // grouped, since only there is the previous stop known.
  claim?: string;
  start: number;   // token span start in the answer text
  end: number;     // token span end in the answer text
}


// Renders a single citation chip that links back to the source viewer.
// Clicking a chip only scrolls to the page/timestamp — no highlight — UNLESS it is a
// popup/action-bar exact selection, which still passes its verbatim text to highlight.
function CitationChip({ desc, onChipClick }: { desc: ChipDesc; onChipClick: CitationChipClickHandler }) {
  const { filename, displayQNum, label, clickUuid, clickPage, clickSeconds, clickEndSeconds, clickHighlight, isExactSelection, claim } = desc;
  const targetKey = chipTargetKey(clickUuid, clickSeconds ? 0 : clickPage, clickSeconds);
  const isActive = useIsActiveChip(targetKey);
  // onPointerDown (not onClick) so chips remain clickable during active token stream:
  // with onClick, react-markdown often unmounts the chip between down and up, so the
  // native click lands on an ancestor. Pointer (not Mouse) so touch devices trigger it.
  const activate = () => {
    // Mark this chip as the active one so it wears the same yellow border as the page
    // frame the click is about to draw in the viewer.
    setActiveChipTarget(targetKey);
    onChipClick(
      clickUuid,
      clickSeconds ? 0 : clickPage,
      filename,
      // PDF: verbatim text to highlight (popup selections only). Media: the answer text this
      // chip backs up — the transcript ranks the lines of the marked span against it. Both
      // are "the text belonging to this citation", which is what this slot has always meant.
      clickSeconds ? claim : clickHighlight,
      clickSeconds,
      isExactSelection,
      clickSeconds ? clickEndSeconds : undefined,
    );
  };
  return (
    <span role="button" tabIndex={0}
      onPointerDown={(e) => { if (e.button === 0) activate(); }}
      onKeyDown={(e) => { if (e.key === "Enter") activate(); }}
      // Deliberately smaller than the surrounding prose (9px, tight padding, 1px margin):
      // chips are a side note, not a headline — at text-xs with 2px padding they dominated
      // the answer.
      className="inline-flex items-center whitespace-nowrap text-3xs px-[0.3125rem] py-px rounded-full font-medium chip-cite align-middle mx-px cursor-pointer"
      // Transparent border by default so the active state adds the yellow frame without
      // shifting layout. Yellow matches the viewer page frame (CITATION_HL_COLOR).
      style={{
        backgroundColor: "rgba(var(--kb-rgb),0.12)",
        color: "var(--kb)",
        border: `1px solid ${isActive ? CITATION_HL_COLOR : "transparent"}`,
      }}
      title={`${filename}, ${label}`}
    >{displayQNum ? `[${displayQNum}] ` : ""}{label}</span>
  );
}


// Expanding is a TOGGLE: a group opens to show all chips and can be collapsed back to
// just the first chip + chevron. The user's explicit open/closed choice lives at module
// scope so it survives the re-render/remount churn from streaming tokens or the 15s
// workspace poll (a fresh mount resets local state, then restores it from the stable
// groupId): NOT in the set == collapsed (default), opened groups are added, re-collapsed
// groups are removed.
const _openChipGroups = new Set<string>();

// The toggle used to be a PILL of its own: same tint, same radius, same height as a chip,
// with a caret inside. Next to every chip that reads as a SECOND chip, and with a chip on
// nearly every sentence the row of pills is what the eye sees instead of the text. So the
// pill is gone and only a mark is left: the ring always, with a dot inside while there is
// something to open. Opening empties the ring, so filled/hollow carries the state — no
// caret, no count.
//
// The mark carries neither the chips' background nor their tint — it is grey, so it
// recedes instead of competing. It still needs a real hit area, so the clickable span
// stays 16px square (w-4 h-4) around a 10px drawing.
function ChipToggleMark({ open }: { open: boolean }) {
  return (
    // Ring and dot share one opacity: at full strength the dot punched out of the ring and
    // pulled the eye to a mark that is meant to sit quietly at the end of a sentence. The
    // hover rule lifts both to 1 together.
    <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false" opacity="0.55">
      <circle cx="5" cy="5" r="4" fill="none" stroke="currentColor" strokeWidth="1" />
      {!open && <circle cx="5" cy="5" r="1.5" fill="currentColor" />}
    </svg>
  );
}


// One chip stop: EVERY chip of it, including the first, sits behind the mark. Closed, the
// sentence ends in nothing but the small ring — the text reads as text again. Clicking the
// ring reveals the source(s) and leaves the bare dot to fold them away.
//
// A stop with a single chip is wrapped exactly like one with three, otherwise lone chips
// would stay open in a text where every other stop is collapsed, which reads as noise
// rather than as a rule.
function CitationChipGroup({ groupId, chips, onChipClick }: { groupId: string; chips: ChipDesc[]; onChipClick: CitationChipClickHandler }) {
  // Two ways to be open, and they must not fight each other. PINNED is the deliberate one
  // (a click on the mark) and survives remounts via _openChipGroups. HOVERED is transient:
  // pointing at the stop reveals its sources for as long as the pointer stays, so you can
  // skim an answer's provenance without clicking 38 times.
  const [pinned, setPinned] = React.useState(() => _openChipGroups.has(groupId));
  const [hovered, setHovered] = React.useState(false);
  const open = pinned || hovered;
  const pin = () => { _openChipGroups.add(groupId); setPinned(true); };
  const unpin = () => { _openChipGroups.delete(groupId); setPinned(false); };
  // No background and no border: the mark is not a pill. mx-px matches the chips' own
  // spacing, w-4/h-4 is the hit area around the 10px drawing.
  const toggleCls = "chip-toggle inline-flex items-center justify-center w-4 h-4 align-middle mx-px cursor-pointer select-none";
  // --muted is the design's tone for secondary matter and already flips with the theme.
  // The mark is a side note next to the sentence, not a call to action, so it stays grey
  // while the chips it reveals keep the brand tint.
  const toggleStyle = { color: "var(--muted)" } as const;
  const action = pinned ? unpin : pin;
  return (
    // The hover handlers sit on the WRAPPER, not on the mark: once the chips are out, the
    // pointer travels from the mark onto a chip to click it, and that must not count as
    // leaving. flex-wrap + max-w-full so a long row wraps instead of overflowing the message
    // width; gap-y keeps the wrapped rows legible. Touch devices never fire these and keep
    // the click as their way in.
    <span
      className="chip-stop"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* The mark comes FIRST and therefore never moves: opening grows the chips to its
          right instead of pushing it along, so the pointer stays on the thing it just
          opened and the eye keeps its anchor at the end of the sentence. */}
      <span role="button" tabIndex={0}
        onPointerDown={(e) => { if (e.button === 0) { e.stopPropagation(); action(); } }}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); action(); } }}
        aria-label={`${pinned ? "−" : "+"}${chips.length}`} className={toggleCls} style={toggleStyle}
      ><ChipToggleMark open={open} /></span>
      {open && chips.map(c => <CitationChip key={c.key} desc={c} onChipClick={onChipClick} />)}
    </span>
  );
}


// Hard ceiling per group: one visible chip plus at most two behind the caret. Beyond that
// an opened group unrolls into a wall of pills that says no more than the first three —
// chips arrive closest-first, so the ones past the cap are the weakest matches anyway.
// Kept here as well as in the backend gate, so a longer run from ANY producer (chat,
// notes) is trimmed at render time rather than reaching the reader.
const MAX_CHIPS_PER_GROUP = 3;

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
    clickEndSeconds: number | undefined;
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
    // End of the cited chunk. A chunk runs ~45s and covers SEVERAL subtitle cues, so the
    // timestamp alone marks only its first cue: the sentence the answer actually rests on
    // frequently sits in the next cue, just past the marking, and reads as missing from the
    // source. Carried along so the transcript can mark the whole cited passage.
    let endSeconds: number | undefined;
    if (timestamp) {
      const tp = timestamp.split(":").map(Number);
      seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
      // The MM:SS token is the chunk start floored to whole seconds (backend int()). Recover
      // the EXACT float start from source_pages, so the viewer pins the precise transcript
      // cue instead of re-deriving from the lossy second. Matched by source + same floored
      // second; chunks of one source are seconds apart, so that floor is unique.
      const exact = msgSourcePages.find(
        (s) => s.source_uuid === sourceUuid && s.start_time != null && Math.floor(s.start_time) === seconds,
      );
      if (exact?.start_time != null) seconds = exact.start_time;
      if (exact?.end_time != null) endSeconds = exact.end_time;
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
      clickEndSeconds: timestamp ? endSeconds : undefined,
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
      clickEndSeconds: head.clickEndSeconds,
      clickHighlight: head.clickHighlight,
      isExactSelection: head.isExactSelection,
      start: head.fields.index,
      end: tail.index + tail.length,
    });
    i = j;
  }

  // Phase 2: emit text + chips. A maximal run of chips separated only by whitespace becomes
  // ONE CitationChipGroup, which shows just its mark until opened — a run of one is wrapped
  // the same way, so no chip stays open in a text where all the others are folded. Exact
  // (popup) chips are the exception: they are the user's OWN selection, shown on demand and
  // expected to be visible, so they render directly.
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

    // What this stop backs up: the answer text since the previous stop. Not a sentence split
    // — a period is not a sentence end in every language, and in German it is not even one in
    // "22. April". The stretch between two chips is the claim by construction.
    const claim = text.slice(last, first.start).trim();
    const kept = run.slice(0, MAX_CHIPS_PER_GROUP).map(c => ({ ...c, claim }));
    nodes.push(
      first.isExactSelection
        ? <CitationChip key={first.key} desc={first} onChipClick={onChipClick} />
        : <CitationChipGroup
            key={first.key}
            // The id names the PLACE, never the content: message + markdown node (both in
            // keyPrefix) + the character offset of the stop inside this node. An id built
            // from source+page instead collapsed whole answers into a handful of ids —
            // messages carry no id, so every node fell back to the same prefix, and a media
            // chip has no page (0 for all of them), so its second never entered the id. One
            // measured answer had 126 stops on 56 ids, the worst shared by 34. They share
            // one open/closed choice as well, so a chip click, which rebuilds the tree to
            // fit in the viewer, unfolded all 34 at once.
            //
            // Position survives that rebuild just as well, and it survives streaming too:
            // text only grows at the end, so a stop already on screen keeps its offset.
            groupId={`${keyPrefix}${first.start}`}
            chips={kept}
            onChipClick={onChipClick}
          />,
    );

    // Advance past the WHOLE run, not just the kept chips: a chip dropped by the cap must
    // not leave its raw "[4, S. 12]" token behind as text.
    last = run[run.length - 1].end;
    k = n;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}


// nodePrefix names the message and the markdown node this text sits in. Without it the
// chip keys and the group ids of two paragraphs would collide, because each node parses on
// its own and its offsets start at 0 again. Callers build it from the message key plus the
// node's offset in the markdown source (see ChatMessage/NotesStudio).
export function withCitations(
  children: React.ReactNode,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  tChip?: ChipLabelT,
  nodePrefix: string = "",
): React.ReactNode {
  const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
  return arr.flatMap((child, idx) =>
    typeof child === "string"
      ? parseCitations(child, msg, activeSourceIds, getFilename, onChipClick, `${nodePrefix}c${idx}-`, tChip)
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
