import React from "react";
import { _chunkLabel, type ChipLabelT } from "../../_utils";
import type { ChatMessage } from "../../_types";
import { citationPattern, citationsAreAdjacentSameTarget, stripCitations, type CitationFields } from "./_citation_parse";


// The target just jumped to, at module scope so it survives a redraw.
let _activeChipTarget: string | null = null;
const _activeChipSubs = new Set<() => void>();

// The id of a chip: source plus page or second.
export function chipTargetKey(uuid: string, page: number, seconds: number | undefined): string {
  return seconds != null ? `${uuid}@t${seconds}` : `${uuid}@p${page}`;
}

export function setActiveChipTarget(key: string): void {
  if (_activeChipTarget === key) return;
  _activeChipTarget = key;
  _activeChipSubs.forEach((fn) => fn());
}

// For chips outside React, the mindmap draws its own frame from this.
export function getActiveChipTarget(): string | null {
  return _activeChipTarget;
}

export function subscribeActiveChip(cb: () => void): () => void {
  _activeChipSubs.add(cb);
  return () => { _activeChipSubs.delete(cb); };
}

// Takes the frame off the active chip when the viewer drops its own frame.
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
  // The end of the chunk so the transcript marks the whole spot.
  endTime?: number,
  // The start of the chunk, in case the guess wobbles.
  chunkStart?: number,
) => void;


// The finished data of a chip, possibly from several citations.
interface ChipDesc {
  key: string;
  filename: string;
  displayQNum: number | null;
  label: string;
  clickUuid: string;
  clickPage: number;
  clickSeconds: number | undefined;
  clickEndSeconds: number | undefined;
  clickChunkStart: number | undefined;
  clickHighlight: string | undefined;
  isExactSelection: boolean;
  // The section of answer text this chip backs up.
  claim?: string;
  start: number;   // token span start in the answer text
  end: number;     // token span end in the answer text
}


// What a click passes on, extracted because of the zero trap at 00:00.
export function chipClickArgs(desc: {
  clickPage: number;
  clickSeconds: number | undefined;
  clickEndSeconds: number | undefined;
  clickChunkStart: number | undefined;
  clickHighlight: string | undefined;
  claim?: string;
}) {
  const istMedien = desc.clickSeconds != null;
  return {
    istMedien,
    page: istMedien ? 0 : desc.clickPage,
    // The verbatim text of a selection of your own, otherwise the backed answer text.
    sourceText: istMedien ? desc.claim : (desc.clickHighlight ?? desc.claim),
    endTime: istMedien ? desc.clickEndSeconds : undefined,
    chunkStart: istMedien ? desc.clickChunkStart : undefined,
  };
}


// Draws a single chip that leads back to the source.
function CitationChip({ desc, onChipClick, onPin }: { desc: ChipDesc; onChipClick: CitationChipClickHandler; onPin?: () => void }) {
  const { filename, displayQNum, label, clickUuid, clickSeconds, isExactSelection } = desc;
  const args = chipClickArgs(desc);
  const targetKey = chipTargetKey(clickUuid, args.page, clickSeconds);
  const isActive = useIsActiveChip(targetKey);
  // onPointerDown, otherwise the click is lost during the stream.
  const activate = () => {
    // Marks this chip as active, matching the frame in the viewer.
    setActiveChipTarget(targetKey);
    // Picking a chip keeps its group open, hovering away must not hide the one just picked.
    onPin?.();
    onChipClick(clickUuid, args.page, filename, args.sourceText, clickSeconds,
                isExactSelection, args.endTime, args.chunkStart);
  };
  return (
    <span role="button" tabIndex={0}
      onPointerDown={(e) => { if (e.button === 0) activate(); }}
      onKeyDown={(e) => { if (e.key === "Enter") activate(); }}
      // Deliberately smaller than the text, a chip is a marginal note.
      className={`inline-flex items-center whitespace-nowrap text-3xs px-[0.3125rem] py-px rounded-full font-medium chip-cite align-middle mx-px cursor-pointer`}
      // The active chip carries the same frame as on hover, only filled in.
      style={{
        backgroundColor: "rgba(var(--kb-rgb),0.12)",
        color: "var(--kb)",
        outlineColor: isActive ? "var(--cite-border)" : undefined,
      }}
      title={`${filename}, ${label}`}
    >{displayQNum ? `[${displayQNum}] ` : ""}{label}</span>
  );
}


// Expanding is a toggle, the choice lives at module scope so it survives.
const _openChipGroups = new Set<string>();

// One entry per message drives the toggle for all its sites.
const _openAllOwners = new Set<string>();

// One subscriber list for both sets, a site has to re-read after either.
const _chipStateSubs = new Set<() => void>();
function notifyChipState(): void {
  _chipStateSubs.forEach((fn) => fn());
}

function useChipFlag(getSnapshot: () => boolean): boolean {
  const subscribe = React.useCallback((cb: () => void) => {
    _chipStateSubs.add(cb);
    return () => { _chipStateSubs.delete(cb); };
  }, []);
  return React.useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

// The message a site belongs to, everything before the hash.
function chipOwnerOf(groupId: string): string {
  const i = groupId.indexOf("#");
  return i < 0 ? groupId : groupId.slice(0, i);
}

/** Is the toggle of this message on? */
export function useAllChipsOpen(owner: string): boolean {
  return useChipFlag(React.useCallback(() => _openAllOwners.has(owner), [owner]));
}

/** Toggles the message, off really closes everything. */
export function toggleAllChips(owner: string): void {
  if (_openAllOwners.has(owner)) {
    _openAllOwners.delete(owner);
    // Deleting during the iteration is safe here.
    const prefix = `${owner}#`;
    _openChipGroups.forEach((id) => { if (id.startsWith(prefix)) _openChipGroups.delete(id); });
  } else {
    _openAllOwners.add(owner);
  }
  notifyChipState();
}

// Instead of a second pill just one mark: the ring always, the dot while something can open.
export function ChipToggleMark({ open, size = 10, opacity = 0.55, strokeWidth = 1 }: { open: boolean; size?: number; opacity?: number; strokeWidth?: number }) {
  return (
    // Ring and dot share one opacity, otherwise the dot stands out.
    <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden="true" focusable="false" opacity={opacity}>
      <circle cx="5" cy="5" r="4" fill="none" stroke="currentColor" strokeWidth={strokeWidth} />
      {!open && <circle cx="5" cy="5" r="1.5" fill="currentColor" />}
    </svg>
  );
}


// How far the hand has to travel before a hovered stop may close, and how much slack
// the stop keeps around itself while the pointer is still on it.
const CLOSE_TRAVEL_PX = 24;
const CLOSE_PAD_PX = 8;


// One chip site: all chips sit behind the mark and run along in the sentence.
function CitationChipGroup({ groupId, chips, onChipClick, tail }: { groupId: string; chips: ChipDesc[]; onChipClick: CitationChipClickHandler; tail?: string }) {
  // Three ways to be open: pinned, hovered, and the message toggle.
  const owner = chipOwnerOf(groupId);
  const allOpen = useAllChipsOpen(owner);
  const pinned = useChipFlag(React.useCallback(() => _openChipGroups.has(groupId), [groupId]));
  const [hovered, setHovered] = React.useState(false);
  const open = allOpen || pinned || hovered;
  const pin = () => { _openChipGroups.add(groupId); notifyChipState(); };
  const unpin = () => { _openChipGroups.delete(groupId); notifyChipState(); };
  // Opening rewraps the line and in a table cell even widens the column, so the mark
  // slides out from under a pointer that never moved: mouseleave then closed the stop,
  // the old layout put the mark right back under the pointer and both states flipped
  // ~70 times a second. Closing therefore waits for the hand to travel, never for the
  // layout to move, and mouseleave is deliberately not listened to at all.
  const stopRef = React.useRef<HTMLSpanElement>(null);
  const openedAt = React.useRef<{ x: number; y: number } | null>(null);
  const handleEnter = (e: React.MouseEvent) => {
    openedAt.current = { x: e.clientX, y: e.clientY };
    setHovered(true);
  };
  React.useEffect(() => {
    if (!hovered) return;
    const onMove = (e: PointerEvent) => {
      const from = openedAt.current;
      if (from && Math.hypot(e.clientX - from.x, e.clientY - from.y) < CLOSE_TRAVEL_PX) return;
      const rects = stopRef.current?.getClientRects();
      if (!rects) return;
      // An inline stop has one rect per line, the pointer only has to be on one of them.
      const onStop = Array.from(rects).some((r) =>
        e.clientX >= r.left - CLOSE_PAD_PX && e.clientX <= r.right + CLOSE_PAD_PX
        && e.clientY >= r.top - CLOSE_PAD_PX && e.clientY <= r.bottom + CLOSE_PAD_PX);
      if (!onStop) setHovered(false);
    };
    document.addEventListener("pointermove", onMove);
    return () => document.removeEventListener("pointermove", onMove);
  }, [hovered]);
  // No background and no border, the mark is not a pill.
  const toggleCls = "chip-toggle inline-flex items-center justify-center w-4 h-4 align-middle mx-px cursor-pointer select-none";
  // The mark stays grey, the chips keep the house colour.
  const toggleStyle = { color: "var(--muted)" } as const;
  const action = pinned ? unpin : pin;
  return (
    // Enter sits on the frame, so a pointer moving on to a chip is still on the stop.
    <span
      ref={stopRef}
      className="chip-stop"
      onMouseEnter={handleEnter}
    >
      {/* The mark comes FIRST and therefore never moves: opening grows the chips to its
          right instead of pushing it along, so the pointer stays on the thing it just
          opened and the eye keeps its anchor at the end of the sentence.

          The punctuation that closes the sentence rides along right behind the mark, ahead
          of the chips. Left in the text it landed BEHIND them and hung alone in the middle
          of the line, a lost period a hand's width from its sentence. head is nowrap so the
          two never break apart. */}
      <span className="chip-stop-head">
        <span role="button" tabIndex={0}
          onPointerDown={(e) => { if (e.button === 0) { e.stopPropagation(); action(); } }}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); action(); } }}
          aria-label={`${pinned ? "−" : "+"}${chips.length}`} className={toggleCls} style={toggleStyle}
        ><ChipToggleMark open={open} /></span>{tail}
      </span>
      {/* Die Chips gibt es nur, solange die Stelle offen ist. Zu ist der Satz reiner Text,
          kein reservierter Platz und keine Luecke darin. Der Preis ist bekannt und so
          gewollt: die Chips brauchen beim Aufklappen Platz und schieben den Text weiter. */}
      {open && chips.map(c => <CitationChip key={c.key} desc={c} onChipClick={onChipClick} onPin={pin} />)}
    </span>
  );
}


// At most three chips per site, further ones are the weakest hits anyway.
const MAX_CHIPS_PER_GROUP = 3;

// The punctuation a site takes along, listed instead of guessed by language.
const CLOSING_PUNCT = /^[^\S\n]*[.,;:!?…·。、！？；：）〕】」』»”’)\]}۔،؛؟]+/u;

// Reads the punctuation behind a site, without one nothing is swallowed.
function splitAfterStop(chunk: string): { tail: string; consumed: number } {
  const m = CLOSING_PUNCT.exec(chunk);
  const matched = m ? m[0] : "";
  return { tail: matched.replace(/^\s+/u, ""), consumed: matched.length };
}

// Replaces the citation markers with chips, table cells take no punctuation along.
export function parseCitations(
  text: string,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  keyPrefix: string = "c",
  tChip?: ChipLabelT,
  takePunctuation: boolean = true,
): React.ReactNode[] {
  const msgSourcePages = msg.source_pages ?? [];
  const msgQmap = msg.source_qmap ?? [];
  // With a single source the [n] prefix is redundant — the chip is just "S. X".
  const singleSource = msgQmap.length === 1;
  // The pattern of the citation markers, old forms and CJK brackets included.
  const pattern = citationPattern();

  // The resolved data per marker so neighbours can be merged later.
  interface Parsed {
    fields: CitationFields;
    sourceUuid: string;
    filename: string;
    displayQNum: number | null;
    label: string;
    clickSeconds: number | undefined;
    clickEndSeconds: number | undefined;
    clickChunkStart: number | undefined;
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
    // The end of the chunk so the transcript marks the whole spot.
    let endSeconds: number | undefined;
    let chunkStart: number | undefined;
    if (timestamp) {
      const tp = timestamp.split(":").map(Number);
      seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
      // The chunk containing the timestamp is sought, not the one with the same start.
      const owner = msgSourcePages
        .filter((s) => s.source_uuid === sourceUuid && s.start_time != null && s.end_time != null
          && s.start_time - 1 <= seconds && seconds <= s.end_time + 1)
        .sort((a, b) => (b.start_time ?? 0) - (a.start_time ?? 0))[0];
      if (owner?.start_time != null) {
        chunkStart = owner.start_time;
        endSeconds = owner.end_time ?? undefined;
        // If the chip points at the chunk start, the exact time applies.
        if (Math.floor(owner.start_time) === seconds) seconds = owner.start_time;
      }
    }
    // Only a selection of your own still highlights text in the PDF.
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
      clickChunkStart: timestamp ? chunkStart : undefined,
      clickHighlight, isExactSelection,
    });
  }

  // First merge neighbouring citations of the same page into one chip.
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
      clickChunkStart: head.clickChunkStart,
      clickHighlight: head.clickHighlight,
      isExactSelection: head.isExactSelection,
      start: head.fields.index,
      end: tail.index + tail.length,
    });
    i = j;
  }

  // Then emit text and chips, a run of chips becomes one site.
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let k = 0;
  const pushText = (chunk: string) => {
    if (chunk) nodes.push(chunk);
  };

  while (k < chips.length) {
    const first = chips[k];
    if (first.start > last) pushText(text.slice(last, first.start));

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

    // The text since the previous site is backed, no sentence splitting.
    const claim = text.slice(last, first.start).trim();
    const kept = run.slice(0, MAX_CHIPS_PER_GROUP).map(c => ({ ...c, claim }));
    // Only a collapsed site takes the punctuation along.
    const folded = takePunctuation && !first.isExactSelection;
    const runEnd = run[run.length - 1].end;
    const following = text.slice(runEnd, chips[n]?.start ?? text.length);
    const { tail, consumed } = folded ? splitAfterStop(following) : { tail: "", consumed: 0 };
    nodes.push(
      first.isExactSelection
        ? <CitationChip key={first.key} desc={first} onChipClick={onChipClick} />
        : <CitationChipGroup
            key={first.key}
            // The id names the place, never the content, otherwise sites share a choice.
            groupId={`${keyPrefix}${first.start}`}
            chips={kept}
            onChipClick={onChipClick}
            tail={tail}
          />,
    );

    // The whole run is skipped, otherwise a raw marker stays as text.
    last = runEnd + consumed;
    k = n;
  }
  if (last < text.length) pushText(text.slice(last));
  return nodes;
}


// The prefix names message and node, otherwise the ids collide.
export function withCitations(
  children: React.ReactNode,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  tChip?: ChipLabelT,
  nodePrefix: string = "",
  takePunctuation: boolean = true,
): React.ReactNode {
  const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
  return arr.flatMap((child, idx) =>
    typeof child === "string"
      ? parseCitations(child, msg, activeSourceIds, getFilename, onChipClick, `${nodePrefix}c${idx}-`, tChip, takePunctuation)
      : [child],
  );
}


// Copies the text without citation markers, with a fallback for old browsers.
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
