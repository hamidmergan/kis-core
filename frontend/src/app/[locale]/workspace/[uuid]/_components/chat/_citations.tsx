import React from "react";
import { _chunkLabel, type ChipLabelT } from "../../_utils";
import type { ChatMessage } from "../../_types";
import { citationPattern, citationsAreAdjacentSameTarget, stripCitations, type CitationFields } from "./_citation_parse";
import { registerChipRow, scheduleChipGapPass, unregisterChipRow } from "./_chip_gap";


// The single citation target (source + page/timestamp) currently framed in the viewer,
// i.e. the last clicked chip. Mirrors the viewer's one-frame-at-a-time behaviour so the
// active chip wears the SAME blue border as the page frame. Module scope (like
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

// Drop the active chip's blue border. Called when the viewer's page frame is
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
  // Anfang des zitierten Chunks. ``startTime`` ist die BESTE VERMUTUNG, wo im Chunk die
  // Aussage faellt, und liegt deshalb meist mittendrin. Steht die Vermutung auf wackligen
  // Fuessen, markiert das Transkript lieber den ganzen Chunk, und dafuer braucht es dessen
  // Anfang: von der Vermutung bis zum Ende zu markieren liesse alles davor unmarkiert.
  chunkStart?: number,
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
  clickChunkStart: number | undefined;
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


// Was ein Klick auf einen Chip weitergibt. Ausgelagert und exportiert, damit die
// Null-Falle geprueft werden kann: ein Medien-Chip auf 00:00 hat die Sekunde 0, und die
// gilt in JavaScript als falsch. Mit einer Wahrheitspruefung fiel so ein Chip in den
// PDF-Zweig und verlor Chunk-Anfang und -Ende — ausgerechnet bei den Chips, die beides am
// noetigsten brauchen: auf den Chunk-Anfang zeigt ein Chip nur dann, wenn keine Zeile
// sicher genug war, und dann soll das Transkript den ganzen Abschnitt markieren.
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
    // PDF: verbatim text to highlight (popup selections only). Media: the answer text this
    // chip backs up — the transcript ranks the lines of the marked span against it. Both
    // are "the text belonging to this citation", which is what this slot has always meant.
    sourceText: istMedien ? desc.claim : desc.clickHighlight,
    endTime: istMedien ? desc.clickEndSeconds : undefined,
    chunkStart: istMedien ? desc.clickChunkStart : undefined,
  };
}


// Renders a single citation chip that links back to the source viewer.
// Clicking a chip only scrolls to the page/timestamp — no highlight — UNLESS it is a
// popup/action-bar exact selection, which still passes its verbatim text to highlight.
//
// `reserved` renders the chip as pure layout: Tailwind's `invisible` is visibility:hidden,
// which keeps the box in the line but takes it out of the paint, out of hit-testing and out
// of the accessibility tree. That is what makes a stop free to open on hover without moving
// a single word — the room was already taken.
function CitationChip({ desc, onChipClick, reserved }: { desc: ChipDesc; onChipClick: CitationChipClickHandler; reserved?: boolean }) {
  const { filename, displayQNum, label, clickUuid, clickSeconds, isExactSelection } = desc;
  const args = chipClickArgs(desc);
  const targetKey = chipTargetKey(clickUuid, args.page, clickSeconds);
  const isActive = useIsActiveChip(targetKey);
  // onPointerDown (not onClick) so chips remain clickable during active token stream:
  // with onClick, react-markdown often unmounts the chip between down and up, so the
  // native click lands on an ancestor. Pointer (not Mouse) so touch devices trigger it.
  const activate = () => {
    // Mark this chip as the active one so it wears the same blue border as the page
    // frame the click is about to draw in the viewer.
    setActiveChipTarget(targetKey);
    onChipClick(clickUuid, args.page, filename, args.sourceText, clickSeconds,
                isExactSelection, args.endTime, args.chunkStart);
  };
  return (
    <span role="button" tabIndex={0}
      onPointerDown={(e) => { if (e.button === 0) activate(); }}
      onKeyDown={(e) => { if (e.key === "Enter") activate(); }}
      // Deliberately smaller than the surrounding prose (9px, tight padding, 1px margin):
      // chips are a side note, not a headline — at text-xs with 2px padding they dominated
      // the answer.
      className={`inline-flex items-center whitespace-nowrap text-3xs px-[0.3125rem] py-px rounded-full font-medium chip-cite align-middle mx-px cursor-pointer${reserved ? " invisible" : ""}`}
      // Der aktive Chip traegt exakt denselben Rahmen wie beim Zeigen: die 2px-Outline aus
      // .chip-cite, hier nur eingefaerbt, damit nichts verrutscht.
      style={{
        backgroundColor: "rgba(var(--kb-rgb),0.12)",
        color: "var(--kb)",
        outlineColor: isActive ? "var(--cite-border)" : undefined,
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

// Every stop of one message starts its group id with that message's name plus '#' (see
// the groupId comment below), so ONE entry here speaks for all of them: the switch in the
// message's action row that shows every stop at once. Module scope for the same reason as
// _openChipGroups — streaming and the 15s poll remount the tree, the choice must survive.
const _openAllOwners = new Set<string>();

// One subscriber list for BOTH sets. A stop has to re-read after either changed, because
// the message switch closes stops it never touched — so a stop's open state can no longer
// live in its own useState.
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

// The message (or note) a stop belongs to: everything ahead of the '#' that ChatMessage and
// NotesStudio put at the head of every prefix they hand to withCitations.
function chipOwnerOf(groupId: string): string {
  const i = groupId.indexOf("#");
  return i < 0 ? groupId : groupId.slice(0, i);
}

/** Is the "show every stop" switch of this message on? For the switch itself and for
 * every stop under it. */
export function useAllChipsOpen(owner: string): boolean {
  return useChipFlag(React.useCallback(() => _openAllOwners.has(owner), [owner]));
}

/** Flip the message-level switch. On shows every stop of the message; off closes ALL of
 * them, the ones opened one by one included — off means nothing is left showing. */
export function toggleAllChips(owner: string): void {
  if (_openAllOwners.has(owner)) {
    _openAllOwners.delete(owner);
    // Deleting while iterating is safe: a Set's forEach skips entries removed before it
    // reaches them, and these are exactly the ones being removed.
    const prefix = `${owner}#`;
    _openChipGroups.forEach((id) => { if (id.startsWith(prefix)) _openChipGroups.delete(id); });
  } else {
    _openAllOwners.add(owner);
  }
  notifyChipState();
}

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
// size/opacity/strokeWidth carry the mark to the message's action row, where it stands
// among the copy and note buttons rather than inside a sentence: there it is a button of
// its own, so it matches their 13px and needs none of the restraint that keeps it quiet in
// running text. The stroke has to be re-set for that: 1 in a 10-box is 10% of the drawing,
// while a Phosphor icon at regular weight draws 16 in a 256-box, i.e. 6.25%. Left at 1 the
// ring came out half again as thick as its neighbours and read as the darker icon of the
// three, though all of them are var(--muted).
export function ChipToggleMark({ open, size = 10, opacity = 0.55, strokeWidth = 1 }: { open: boolean; size?: number; opacity?: number; strokeWidth?: number }) {
  return (
    // Ring and dot share one opacity: at full strength the dot punched out of the ring and
    // pulled the eye to a mark that is meant to sit quietly at the end of a sentence. The
    // hover rule lifts both to 1 together.
    <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden="true" focusable="false" opacity={opacity}>
      <circle cx="5" cy="5" r="4" fill="none" stroke="currentColor" strokeWidth={strokeWidth} />
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
//
// `ownRow` haengt dem Vorrat eine freie Zeile an: er faengt im Zeilenrest hinter der Marke an
// und darunter bleibt immer eine Zeile frei (chip-row in globals.css). Ohne diese Zeile
// entschied ueber Satzlaenge und Chipbreite der Zufall, ob unter einem Satz Platz blieb, mit
// ihr ist der Abstand nach JEDER Stelle derselbe.
// Tabellenzellen setzen die Flagge nicht: dort laeuft der Vorrat ohne freie Zeile mit und
// verbreitert die Spalte, eine Zelle hat keinen Satzfluss zum Umbrechen.
function CitationChipGroup({ groupId, chips, onChipClick, tail, ownRow }: { groupId: string; chips: ChipDesc[]; onChipClick: CitationChipClickHandler; tail?: string; ownRow?: boolean }) {
  // Two ways to be open, and they must not fight each other. PINNED is the deliberate one
  // (a click on the mark) and survives remounts via _openChipGroups. HOVERED is transient:
  // pointing at the stop reveals its sources for as long as the pointer stays, so you can
  // skim an answer's provenance without clicking 38 times.
  // A third way, and it outranks both: the message's own switch. While it is on every stop
  // stands open, so a click on a single mark changes only what lies underneath — and that
  // is never seen, because switching off wipes the pins of the whole message with it.
  const owner = chipOwnerOf(groupId);
  const allOpen = useAllChipsOpen(owner);
  const pinned = useChipFlag(React.useCallback(() => _openChipGroups.has(groupId), [groupId]));
  const [hovered, setHovered] = React.useState(false);
  const open = allOpen || pinned || hovered;
  const pin = () => { _openChipGroups.add(groupId); notifyChipState(); };
  const unpin = () => { _openChipGroups.delete(groupId); notifyChipState(); };
  // No background and no border: the mark is not a pill. mx-px matches the chips' own
  // spacing, w-4/h-4 is the hit area around the 10px drawing.
  const toggleCls = "chip-toggle inline-flex items-center justify-center w-4 h-4 align-middle mx-px cursor-pointer select-none";
  // --muted is the design's tone for secondary matter and already flips with the theme.
  // The mark is a side note next to the sentence, not a call to action, so it stays grey
  // while the chips it reveals keep the brand tint.
  const toggleStyle = { color: "var(--muted)" } as const;
  const action = pinned ? unpin : pin;
  // Die Chipzeile meldet sich zum Messen an, sobald sie im Dokument steht: nur die Messung
  // weiss, ob der Vorrat noch in den Zeilenrest gepasst hat, und danach richtet sich, ob unter
  // ihm noch eine freie Zeile kommt (siehe _chip_gap). Anmelden einmal, nachmessen bei jedem
  // Durchlauf: waehrend des Streams wachsen die Saetze, und ein Wort mehr verschiebt den
  // Zeilenrest. Der rAF im Modul fasst die Durchlaeufe zu einem zusammen.
  const rowRef = React.useRef<HTMLSpanElement>(null);
  React.useLayoutEffect(() => {
    const row = rowRef.current;
    registerChipRow(row);
    return () => unregisterChipRow(row);
  }, []);
  React.useLayoutEffect(() => { scheduleChipGapPass(); });
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
          opened and the eye keeps its anchor at the end of the sentence.

          The punctuation that closes the sentence rides along right behind the mark, ahead
          of the reserved room. Left in the text it landed BEHIND that room and hung alone in
          the middle of the line, a lost period a hand's width from its sentence. head is
          nowrap so the two never break apart. */}
      <span className="chip-stop-head">
        <span role="button" tabIndex={0}
          onPointerDown={(e) => { if (e.button === 0) { e.stopPropagation(); action(); } }}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.stopPropagation(); action(); } }}
          aria-label={`${pinned ? "−" : "+"}${chips.length}`} className={toggleCls} style={toggleStyle}
        ><ChipToggleMark open={open} /></span>{tail}
      </span>
      {/* The chips are ALWAYS in the layout, hidden until the stop opens. Rendering them
          only while open made every hover re-wrap the paragraph under the pointer: measured
          on one answer, pointing at a single stop moved 54 of 58 text runs, pushed 25 of
          them onto another line and shifted table columns by up to 460px.

          Der Preis dafuer ist eine freie Zeile pro Stelle. Die Chips selbst starten aber im
          Zeilenrest hinter der Marke, frei bleibt nur die Zeile darunter: chip-row ist inline
          und setzt den Block erst hinter die Chips. Der bricht die Zeile, deshalb braucht der
          Text danach kein <br> mehr. */}
      {ownRow
        ? <span className="chip-row" ref={rowRef}>{chips.map(c => <CitationChip key={c.key} desc={c} onChipClick={onChipClick} reserved={!open} />)}</span>
        : chips.map(c => <CitationChip key={c.key} desc={c} onChipClick={onChipClick} reserved={!open} />)}
    </span>
  );
}


// Hard ceiling per group: one visible chip plus at most two behind the caret. Beyond that
// an opened group unrolls into a wall of pills that says no more than the first three —
// chips arrive closest-first, so the ones past the cap are the weakest matches anyway.
// Kept here as well as in the backend gate, so a longer run from ANY producer (chat,
// notes) is trimmed at render time rather than reaching the reader.
const MAX_CHIPS_PER_GROUP = 3;

// What may still follow a stop on its own line: the characters that CLOSE the sentence it
// belongs to. A period pushed onto the next line reads as a typo, so the break waits for
// them. Listed by character, not by language — sentence ends look different per script, and
// the answer's language is not ours to assume: Latin terminals and brackets, the CJK forms
// (。、！？；：）】」』), and the Arabic full stop/comma/semicolon/question mark.
const CLOSING_PUNCT = /^[^\S\n]*[.,;:!?…·。、！？；：）〕】」』»”’)\]}۔،؛؟]*/u;

// Reads the closing punctuation off the text that follows a stop. `tail` is what the stop
// takes along, `consumed` how much of the text that eats. Leading blanks are consumed but
// not kept: they would only hang at the end of the closed line.
function splitAfterStop(chunk: string): { tail: string; consumed: number } {
  const m = CLOSING_PUNCT.exec(chunk);
  const matched = m ? m[0] : "";
  return { tail: matched.replace(/^\s+/u, ""), consumed: matched.length };
}

// Parses inline citations like [Q1, S. 2], [1, 05:32], [S. 2] and replaces them with
// CitationChip elements. Text outside matches is returned as-is. Chips are nav-only;
// legacy tokens with a trailing offset/keyword still parse to their page/timestamp.
//
// breakAfterStops gibt jeder Stelle eine eigene Chipzeile unter dem Satz, damit der Abstand
// nach jeder Stelle derselbe ist. Tabellenzellen uebergeben false: eine Zelle hat keinen
// Satzfluss zum Umbrechen, dort verbreitert der reservierte Platz einfach die Spalte.
export function parseCitations(
  text: string,
  msg: ChatMessage,
  activeSourceIds: string[],
  getFilename: (uuid: string) => string,
  onChipClick: CitationChipClickHandler,
  keyPrefix: string = "c",
  tChip?: ChipLabelT,
  breakAfterStops: boolean = true,
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
    // End of the cited chunk. A chunk runs ~45s and covers SEVERAL subtitle cues, so the
    // timestamp alone marks only its first cue: the sentence the answer actually rests on
    // frequently sits in the next cue, just past the marking, and reads as missing from the
    // source. Carried along so the transcript can mark the whole cited passage.
    let endSeconds: number | undefined;
    let chunkStart: number | undefined;
    if (timestamp) {
      const tp = timestamp.split(":").map(Number);
      seconds = tp.length === 3 ? tp[0] * 3600 + tp[1] * 60 + tp[2] : tp[0] * 60 + tp[1];
      // Der MM:SS-Wert im Chip ist NICHT mehr der Chunk-Anfang: das Backend rueckt ihn auf
      // das Segment mit der zitierten Aussage vor (aia_segment_pick). Die alte Zuordnung
      // suchte den Chunk mit GLEICHEM abgerundeten Anfang und fand deshalb keinen, sobald
      // die Zeitmarke vorgerueckt war. Ohne Fund blieb `endSeconds` leer, und ohne Ende
      // markierte das Transkript nur die EINE Untertitelzeile an der Zeitmarke — die ganze
      // Logik "bei Unsicherheit den Abschnitt markieren" lief nie an.
      //
      // Gesucht wird jetzt der Chunk, der die Zeitmarke ENTHAELT. Die Chunks einer Quelle
      // ueberschneiden sich nicht, der Treffer ist also eindeutig. Die halbe Sekunde
      // Toleranz faengt die Rundung auf ganze Sekunden im Chip ab.
      // Auf eine Sekunde genau kann die Zeitmarke an einer Chunk-Grenze auf zwei passen.
      // Dann gilt der spaeter beginnende: das ist der, in dem sie wirklich liegt.
      const owner = msgSourcePages
        .filter((s) => s.source_uuid === sourceUuid && s.start_time != null && s.end_time != null
          && s.start_time - 1 <= seconds && seconds <= s.end_time + 1)
        .sort((a, b) => (b.start_time ?? 0) - (a.start_time ?? 0))[0];
      if (owner?.start_time != null) {
        chunkStart = owner.start_time;
        endSeconds = owner.end_time ?? undefined;
        // Zeigt der Chip auf den Chunk-Anfang, ist die genaue Gleitkommazeit besser als die
        // abgerundete Sekunde aus dem Text. Sonst behaelt er seine eigene, vorgerueckte Zeit.
        if (Math.floor(owner.start_time) === seconds) seconds = owner.start_time;
      }
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
      clickChunkStart: timestamp ? chunkStart : undefined,
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
      clickChunkStart: head.clickChunkStart,
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
  // Gesetzt, sobald eine Stelle mit eigener Chipzeile ausgegeben wurde. Umbrechen muss hier
  // nichts mehr, das erledigt der Block der Chipzeile. Zu tun bleibt nur, die Leerzeichen
  // zwischen Stelle und naechstem Satz zu schlucken, sonst faengt die neue Zeile mit einem an.
  let stripPending = false;
  const pushText = (chunk: string) => {
    const rest = stripPending ? chunk.replace(/^\s+/u, "") : chunk;
    stripPending = false;
    if (rest) nodes.push(rest);
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

    // What this stop backs up: the answer text since the previous stop. Not a sentence split
    // — a period is not a sentence end in every language, and in German it is not even one in
    // "22. April". The stretch between two chips is the claim by construction.
    const claim = text.slice(last, first.start).trim();
    const kept = run.slice(0, MAX_CHIPS_PER_GROUP).map(c => ({ ...c, claim }));
    // Only a folded stop closes its line and takes the sentence's punctuation with it. An
    // exact (popup) chip is the user's own selection: visible from the start, holding no
    // hidden room, so it moves nothing on hover and needs neither.
    const folded = breakAfterStops && !first.isExactSelection;
    const runEnd = run[run.length - 1].end;
    const following = text.slice(runEnd, chips[n]?.start ?? text.length);
    const { tail, consumed } = folded ? splitAfterStop(following) : { tail: "", consumed: 0 };
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
            tail={tail}
            ownRow={folded}
          />,
    );

    stripPending = folded;

    // Advance past the WHOLE run, not just the kept chips: a chip dropped by the cap must
    // not leave its raw "[4, S. 12]" token behind as text. The punctuation the stop took
    // along is consumed too, so it is not written a second time as text.
    last = runEnd + consumed;
    k = n;
  }
  if (last < text.length) pushText(text.slice(last));
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
  breakAfterStops: boolean = true,
): React.ReactNode {
  const arr: React.ReactNode[] = Array.isArray(children) ? children : [children];
  return arr.flatMap((child, idx) =>
    typeof child === "string"
      ? parseCitations(child, msg, activeSourceIds, getFilename, onChipClick, `${nodePrefix}c${idx}-`, tChip, breakAfterStops)
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
