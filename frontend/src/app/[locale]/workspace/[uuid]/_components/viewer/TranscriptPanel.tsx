import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowDown, ArrowsClockwise, ArrowUp, Check, NavigationArrow, NotePencil, X } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import { langLabel } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { buildTranscriptModes, groupCues, resolveCitationFocus, type TranscriptMode } from "./_transcript";
import { CITATION_HL_COLOR } from "./_highlight";
import { clearActiveChipTarget } from "../chat/_citations";

interface Cue {
  start: number;
  end: number;
  text: string;
}

// The switcher's modes live in _transcript.ts so their order can be unit-tested.
type ViewMode = TranscriptMode;

export interface LangInfo {
  source_lang: string | null;
  target_lang: string | null;
  available: string[];
}

function parseVtt(raw: string): Cue[] {
  const cues: Cue[] = [];
  const lines = raw.replace(/\r/g, "").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i].trim();
    const arrow = line.indexOf("-->");
    if (arrow === -1) { i++; continue; }
    const start = parseTs(line.slice(0, arrow).trim());
    const end = parseTs(line.slice(arrow + 3).trim().split(" ")[0]);
    i++;
    const textLines: string[] = [];
    while (i < lines.length && lines[i].trim() !== "") {
      textLines.push(lines[i]);
      i++;
    }
    if (!Number.isNaN(start) && !Number.isNaN(end) && textLines.length) {
      cues.push({ start, end, text: textLines.join(" ").trim() });
    }
    i++;
  }
  return cues;
}

function parseTs(s: string): number {
  const parts = s.split(":");
  if (parts.length < 2) return NaN;
  const sec = parts[parts.length - 1].replace(",", ".");
  const m = parseInt(parts[parts.length - 2] || "0", 10);
  const h = parts.length >= 3 ? parseInt(parts[0], 10) : 0;
  return h * 3600 + m * 60 + parseFloat(sec);
}

function fmtTs(sec: number): string {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function TranscriptPanel({
  mediaRef,
  workspaceUuid,
  sourceUuid,
  langInfo,
  canManage = false,
  onSaveNote,
  onOffChange,
  citationTime,
  citationEndTime,
  citationChunkStart,
  citationClaim,
  citationNonce,
  onCitationFocusTime,
  startOff = false,
}: {
  mediaRef: React.RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  workspaceUuid: string;
  sourceUuid: string;
  // Available transcript languages, fetched once by the parent MediaPlayer and passed
  // down so the langs endpoint is hit a single time per source (not once here too).
  // null = not loaded yet.
  langInfo: LangInfo | null;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  // Reports whether the student switched the transcript OFF, so the player can drop its
  // subtitle tracks: reading along in the video would defeat listening comprehension.
  onOffChange?: (off: boolean) => void;
  // The cited segment's start time (set only on a citation-chip jump) and the jump's
  // nonce, used to pin a navigable "citation highlight" the way the PDF viewer frames
  // the cited page.
  citationTime?: number;
  // End of the CITED CHUNK, not of a cue. A chunk runs some 45 seconds and therefore
  // covers several cues; marking only the cue at citationTime leaves the rest of the
  // cited passage unmarked, and the sentence the answer rests on is regularly one cue
  // further down — just past the marking, which reads as "the source does not say it".
  citationEndTime?: number;
  // Anfang des zitierten Chunks. ``citationTime`` ist die beste Vermutung, wo im Chunk die
  // Aussage faellt, und liegt meist mittendrin: der markierte Abschnitt muss trotzdem am
  // Chunk-Anfang beginnen, sonst bleibt alles davor unmarkiert.
  citationChunkStart?: number;
  // The answer text the chip backs up. Used to find the ONE line of the passage that carries
  // it, so the marking is that line rather than the whole minute the chunk covers.
  citationClaim?: string;
  citationNonce?: number;
  // Reports the start of the line the marking actually sits on, so the player can seek THERE
  // instead of to the chip's chunk start. Only the panel knows it: the pick needs the cues,
  // which the player never loads. Called only when that line is not the chunk's first, i.e.
  // only when the seek would otherwise land in a different paragraph than the marking.
  onCitationFocusTime?: (time: number, nonce?: number) => void;
  // Beim Hör- und Leseverstehen startet das Transkript ausgeschaltet: wer mitlesen kann,
  // hört nicht zu. Es ist aber NICHT gesperrt, der Umschalter steht daneben und der
  // Lernende stellt es wieder an, wenn er will.
  startOff?: boolean;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  // Cues keyed by ISO language code (e.g. { de: [...], en: [...] }).
  const [cues, setCues] = useState<Record<string, Cue[]>>({});
  const [sourceLang, setSourceLang] = useState<string | null>(null);
  const [targetLang, setTargetLang] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Always opens on the original track. Students switch to the translation or the
  // stacked view in the panel itself. Aus einer Hörübung heraus startet es auf "aus".
  const [mode, setMode] = useState<ViewMode>(startOff ? "off" : "source");
  // Für die Ladefunktion unten, die sonst die Startvorgabe wieder überschreiben würde.
  // Als Ref, damit sie nicht wegen einer Prop-Änderung erneut läuft.
  const startOffRef = useRef(startOff);
  startOffRef.current = startOff;
  // Jede neue Aufnahme aus einer Übung fängt wieder ausgeschaltet an. Ohne das würde die
  // Wahl von der vorigen Aufgabe mitwandern.
  useEffect(() => {
    if (startOff) setMode("off");
  }, [sourceUuid, startOff]);
  const [currentIdx, setCurrentIdx] = useState<number>(-1);
  // Follow-mode (auto-scroll the transcript to the playing cue) is OFF by default: playback
  // runs without the list jumping around on every cue change. The user opts in via the
  // jump-to-current button.
  const [followCurrent, setFollowCurrent] = useState(false);
  const [jumpHover, setJumpHover] = useState(false);
  // Pinned citation segment: index of the cue a citation chip jumped to (-1 = none),
  // whether it is currently scrolled into view, and which way it lies relative to the
  // viewport (so the jump-back button can point an arrow at it).
  const [citationIdx, setCitationIdx] = useState<number>(-1);
  // Last cue of the cited passage. Only used when NO single line stands out: then the whole
  // passage is marked, because picking one would be guessing. Equal to citationIdx when the
  // chunk fits in one cue or when no end is known (older messages carry no end_time).
  const [citationEndIdx, setCitationEndIdx] = useState<number>(-1);
  // Which line INSIDE the passage carries the claim, or -1 when none stands out clearly. It is
  // both the marked line and the scroll target: centring the passage's first line would put a
  // claim in the last one back at the bottom edge, which is the whole complaint.
  const [citationClaimIdx, setCitationClaimIdx] = useState<number>(-1);
  // ALLE tragenden Zeilen, nicht nur die staerkste. Ein Antwortsatz nennt oft zwei Dinge
  // aus zwei Momenten; nur eine zu markieren laesst die zweite unmarkiert daneben stehen.
  const [citationClaimIdxs, setCitationClaimIdxs] = useState<number[]>([]);
  const [citationInView, setCitationInView] = useState(true);
  const [citationDir, setCitationDir] = useState<"up" | "down">("down");
  const citationNonceRef = useRef<number | undefined>(undefined);
  // Which source the loaded cues belong to. On a document switch the cues briefly still hold
  // the OLD source's data; this lets the citation pin ignore those stale cues so it does not
  // scroll to a wrong position (and burn the one-shot scroll) before the new cues arrive.
  const cuesUuidRef = useRef<string | null>(null);
  const [savedCueIdx, setSavedCueIdx] = useState<number | null>(null);
  const [savingCueIdx, setSavingCueIdx] = useState<number | null>(null);
  const [regen, setRegen] = useState<"idle" | "running" | "error">("idle");
  const [regenError, setRegenError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  // Keyed by CUE index and attached to the sentence itself, not to its paragraph: the scroll
  // and the in-view check must keep landing on the cited sentence now that several of them
  // share a block.
  const itemRefs = useRef<Record<number, HTMLElement | null>>({});
  const lastScrolledIdx = useRef<number>(-1);

  // Persist a "translation dispatched at" marker so the running state survives
  // reloads / source switches. Backend Celery task is idempotent, so re-mounting
  // and resuming the poll is safe even if the task has already finished.
  const regenStorageKey = `kis:transcript-translate:${sourceUuid}`;
  const REGEN_TTL_MS = 10 * 60 * 1000;

  const transcriptUrl = (lang: string) =>
    `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript?lang=${lang}`;

  useEffect(() => {
    let cancelled = false;
    // Abort the in-flight VTT requests on a source switch. Without this they keep holding
    // scarce per-origin browser connections; a few quick switches exhaust the pool and the
    // whole page freezes while every new request waits for a free slot.
    const ac = new AbortController();
    setLoading(true);
    setCues({});
    setSourceLang(null);
    setTargetLang(null);
    cuesUuidRef.current = null; // cues are now stale until this source's transcript loads

    // Languages come from the parent (one shared /transcript/langs fetch). Until they
    // arrive we stay in loading; once present we pull only the VTT spurs themselves.
    if (!langInfo) return () => { cancelled = true; ac.abort(); };
    const info = langInfo;

    const fetchVtt = async (lang: string): Promise<Cue[] | null> => {
      try {
        const res = await fetch(transcriptUrl(lang), { credentials: "include", signal: ac.signal });
        if (!res.ok) return null;
        return parseVtt(await res.text());
      } catch {
        return null;
      }
    };

    (async () => {
      const entries = await Promise.all(
        info.available.map(async (lang) => [lang, await fetchVtt(lang)] as const),
      );
      if (cancelled) return;

      const map: Record<string, Cue[]> = {};
      for (const [lang, c] of entries) if (c) map[lang] = c;
      setCues(map);
      cuesUuidRef.current = sourceUuid; // cues now belong to this source
      setSourceLang(info.source_lang);
      setTargetLang(info.target_lang);
      setLoading(false);

      const hasSource = !!(info.source_lang && map[info.source_lang]);
      const hasTarget = !!(info.target_lang && map[info.target_lang] && info.target_lang !== info.source_lang);
      // The original always wins; the translation is only preselected when there is
      // no original track at all. Ein aus der Übung heraus ausgeschaltetes Transkript
      // bleibt aus, sonst schaltet das fertige Laden es hinter dem Rücken wieder an.
      const keep = (next: ViewMode) => (m: ViewMode) =>
        (m === "off" && startOffRef.current ? m : next);
      if (hasSource) setMode(keep("source"));
      else if (hasTarget) setMode(keep("target"));

      // Resume "running" state if a translation was dispatched recently and the
      // target is still missing — the backend task may still be working.
      if (!hasTarget && info.target_lang && info.target_lang !== info.source_lang) {
        const tsRaw = typeof window !== "undefined" ? window.localStorage.getItem(regenStorageKey) : null;
        const ts = Number(tsRaw || 0);
        if (ts > 0 && Date.now() - ts <= REGEN_TTL_MS) setRegen("running");
        else if (ts > 0) window.localStorage.removeItem(regenStorageKey);
      } else if (typeof window !== "undefined") {
        window.localStorage.removeItem(regenStorageKey);
      }
    })();

    return () => { cancelled = true; ac.abort(); };
  }, [workspaceUuid, sourceUuid, langInfo, regenStorageKey]);

  // Source-language track is the timing master (identical timestamps to the
  // translation — both derive from Whisper on the same audio).
  const masterCues = useMemo(() => {
    if (sourceLang && cues[sourceLang]) return cues[sourceLang];
    const first = Object.values(cues)[0];
    return first ?? [];
  }, [cues, sourceLang]);

  // Paragraphs to read, built from the sentence-sized cues the provider returns. The cues stay
  // the unit of everything that POINTS at the text — the seek, the citation jump, the playing
  // marker — and a block only decides where the paragraph breaks are. See groupCues.
  const blocks = useMemo(() => groupCues(masterCues), [masterCues]);

  // The whole recording, both tracks, one entry per cue. It is the yardstick for how common a
  // word is HERE, which is what decides whether that word may point at a line further down.
  const claimCorpus = useMemo(() => {
    const src = sourceLang ? cues[sourceLang] : undefined;
    const tgt = targetLang ? cues[targetLang] : undefined;
    const n = Math.max(src?.length ?? 0, tgt?.length ?? 0);
    const out: string[] = [];
    for (let i = 0; i < n; i++) out.push(`${src?.[i]?.text ?? ""} ${tgt?.[i]?.text ?? ""}`);
    return out;
  }, [cues, sourceLang, targetLang]);

  // The line the marking is actually on: the claim line when one was found, else the start of
  // the span. Everything that points AT the marking uses this — the scroll, the jump-back
  // button and its timestamp — so the button always names the place it takes you to.
  const citationFocusIdx = citationClaimIdx >= 0 ? citationClaimIdx : citationIdx;

  // Drive currentIdx from the media element's time updates.
  useEffect(() => {
    const media = mediaRef.current;
    if (!media || masterCues.length === 0) return;
    const onTime = () => {
      const time = media.currentTime;
      let lo = 0, hi = masterCues.length - 1, idx = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const c = masterCues[mid];
        if (time < c.start) hi = mid - 1;
        else if (time > c.end) lo = mid + 1;
        else { idx = mid; break; }
      }
      if (idx === -1 && masterCues.length > 0) {
        for (let j = masterCues.length - 1; j >= 0; j--) {
          if (masterCues[j].start <= time) { idx = j; break; }
        }
      }
      setCurrentIdx((prev) => (prev === idx ? prev : idx));
    };
    media.addEventListener("timeupdate", onTime);
    onTime();
    return () => media.removeEventListener("timeupdate", onTime);
  }, [mediaRef, masterCues]);

  // Auto-scroll the current cue into view while follow mode is active.
  useEffect(() => {
    if (!followCurrent) return;
    const el = itemRefs.current[currentIdx];
    if (el && listRef.current) {
      const prev = lastScrolledIdx.current;
      const isJump = prev < 0 || Math.abs(currentIdx - prev) > 1;
      el.scrollIntoView({ block: "center", behavior: isJump ? "instant" : "smooth" });
      lastScrolledIdx.current = currentIdx;
    }
    // `mode` is a dep (unused in the body) because the list this scrolls unmounts entirely
    // in "off" mode: coming back needs a fresh re-centre against the newly mounted list.
  }, [currentIdx, followCurrent, mode]);

  // A new source clears any pinned citation before its cues load.
  useEffect(() => { setCitationIdx(-1); }, [sourceUuid]);

  // Pin the cited segment and scroll to it once per jump.
  //
  // The MARK (setCitationIdx) runs UNCONDITIONALLY whenever there is a citation time and the
  // cues are loaded — no consumable guard in front of it — so it can never be "eaten": it
  // re-pins on the FIRST click even when the media is already open, and re-pins the same chip
  // after a dismiss (the nonce is a dep, so an identical re-click still re-evaluates).
  //
  // The SCROLL is gated to once per jump via the nonce ref, but uses the LOCALLY computed
  // `idx` — never the `citationIdx` state, which lags a render behind and previously made the
  // scroll race to a stale/old cue (e.g. jumping to the top) while consuming the nonce.
  //
  // In "off" mode the cue list is unmounted, so there is nothing to scroll: the nonce is left
  // UNconsumed (guarded by `mode !== "off"`, not just the optional-chained scrollIntoView,
  // which would silently no-op and burn the one-shot). `mode` is a dep so switching the
  // transcript back on re-runs this and the deferred scroll finally lands.
  useEffect(() => {
    // Ignore cues that still belong to the previous source (mid document-switch): acting on
    // them would scroll to the wrong place and consume the one-shot scroll before the new
    // cues load. We act once the loaded cues match the current source.
    if (cuesUuidRef.current !== sourceUuid) return;
    if (citationTime == null || masterCues.length === 0) {
      setCitationIdx(-1); setCitationEndIdx(-1); setCitationClaimIdx(-1);
      setCitationClaimIdxs([]);
      return;
    }
    // One resolver for the pin, the scroll and the play head. Both language tracks go into
    // the line comparison (claimCorpus), so a German answer still finds its line when the
    // lecture is English and only the translation shares its wording. Computed HERE, not in
    // a memo, because the scroll below needs it in the same pass — a memo would still hold
    // the previous jump's value.
    const focus = resolveCitationFocus(masterCues, citationTime, citationEndTime, citationClaim, claimCorpus, citationChunkStart);
    setCitationIdx(focus.idx);
    setCitationEndIdx(focus.endIdx);
    setCitationClaimIdx(focus.claimIdx);
    setCitationClaimIdxs(focus.claimIdxs);
    // Steht eine tragende Zeile fest, spielt der Player von DORT, nicht von der Zeitmarke des
    // Chips. Verglichen wird gegen `citationTime`, nicht gegen `focus.idx`: der ist seit der
    // Verbreiterung der Chunk-Anfang, waehrend der Player von der Zeitmarke ausgeht. Ohne
    // tragende Zeile bleibt es bei der Zeitmarke, unserer besten Vermutung. NOT gated on
    // `mode`: with the transcript switched off there is no marking to see, but the sentence
    // to play is still that one.
    if (focus.claimIdx >= 0 && focus.focusTime != null
        && Math.abs(focus.focusTime - citationTime) > 0.05) {
      onCitationFocusTime?.(focus.focusTime, citationNonce);
    }
    if (focus.idx >= 0 && mode !== "off" && citationNonceRef.current !== citationNonce) {
      citationNonceRef.current = citationNonce;
      const target = focus.focusIdx;
      requestAnimationFrame(() => {
        itemRefs.current[target]?.scrollIntoView({ block: "center", behavior: "instant" });
      });
    }
  }, [citationNonce, citationTime, citationEndTime, citationChunkStart, citationClaim, masterCues, claimCorpus, sourceUuid, mode, onCitationFocusTime]);

  // Track whether the pinned cue is on-screen so the jump-back button only shows once
  // it has scrolled out of view (like the PDF jump button appearing after you page away).
  // Programmatic follow-scrolls fire scroll events too, so this stays in sync with both.
  useEffect(() => {
    if (citationFocusIdx < 0) { setCitationInView(true); return; }
    const list = listRef.current;
    if (!list) return;
    const check = () => {
      const el = itemRefs.current[citationFocusIdx];
      if (!el) return;
      const er = el.getBoundingClientRect();
      const lr = list.getBoundingClientRect();
      const inView = er.bottom > lr.top && er.top < lr.bottom;
      setCitationInView(inView);
      if (!inView) setCitationDir(er.top >= lr.bottom ? "down" : "up");
    };
    check();
    list.addEventListener("scroll", check, { passive: true });
    return () => list.removeEventListener("scroll", check);
    // `mode` is a dep (unused in the body) because the list unmounts entirely in "off" mode:
    // its scroll listener goes with it, and coming back needs a fresh listener on the new list
    // plus a re-check, or `citationInView` would stay frozen at whatever it last was.
  }, [citationFocusIdx, mode]);

  // User-initiated scroll disables follow mode until jump button is pressed.
  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    const disable = () => setFollowCurrent(false);
    el.addEventListener("wheel", disable, { passive: true });
    el.addEventListener("touchstart", disable, { passive: true });
    el.addEventListener("keydown", disable);
    return () => {
      el.removeEventListener("wheel", disable);
      el.removeEventListener("touchstart", disable);
      el.removeEventListener("keydown", disable);
    };
  }, []);

  const jumpToCurrent = () => {
    const el = itemRefs.current[currentIdx];
    if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
    setFollowCurrent(true);
  };

  // Push the off-state up so the player can drop its <track> elements in lockstep. Gated on
  // an actual boolean transition (not just a dep-array change) because `onOffChange` is a
  // caller-supplied prop of unknown stability: an inline arrow re-fires this every render, and
  // if the caller stores the flag non-primitively (e.g. into an array or object) that produces
  // a new reference each time and never bails out on its own, i.e. an infinite render loop.
  const lastOffReportedRef = useRef<boolean | null>(null);
  useEffect(() => {
    const off = mode === "off";
    if (lastOffReportedRef.current === off) return;
    lastOffReportedRef.current = off;
    onOffChange?.(off);
  }, [mode, onOffChange]);

  // Jump back to the pinned citation: ONLY scroll the transcript to the marking. The play
  // head and ongoing playback are left exactly where they are — no seek, no pause, no play.
  const jumpToCitation = () => {
    if (citationFocusIdx < 0) return;
    // Same target as the original jump, so pressing the button twice never lands differently.
    itemRefs.current[citationFocusIdx]?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  // Drop the pin AND the cited chip's yellow border in lockstep, exactly like the PDF
  // viewer's dismiss button (clearActiveChipTarget), so the chat chip stops looking active.
  const dismissCitation = () => {
    setCitationIdx(-1); setCitationEndIdx(-1); setCitationClaimIdx(-1); setCitationClaimIdxs([]);
    clearActiveChipTarget();
  };

  // Poll for the target VTT to appear after a translation task was dispatched.
  useEffect(() => {
    if (regen !== "running" || !targetLang) return;
    const started = Date.now();
    const TIMEOUT_MS = 5 * 60 * 1000;
    const INTERVAL_MS = 5000;
    const timer = setInterval(async () => {
      if (Date.now() - started > TIMEOUT_MS) {
        clearInterval(timer);
        if (typeof window !== "undefined") window.localStorage.removeItem(regenStorageKey);
        setRegen("error");
        setRegenError(t("regenEnTimeout"));
        return;
      }
      try {
        const probe = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript/exists?lang=${targetLang}`,
          { credentials: "include" },
        );
        if (!probe.ok) return;
        const { exists } = (await probe.json()) as { exists: boolean };
        if (!exists) return;
        const res = await fetch(transcriptUrl(targetLang), { credentials: "include" });
        if (res.ok) {
          const parsed = parseVtt(await res.text());
          clearInterval(timer);
          if (typeof window !== "undefined") window.localStorage.removeItem(regenStorageKey);
          setCues((prev) => ({ ...prev, [targetLang]: parsed }));
          // A finished translation reveals both spurs — unless the student deliberately
          // switched the transcript off, in which case yanking it back on would be rude.
          if (sourceLang && cues[sourceLang]) setMode((m) => (m === "off" ? m : "both"));
          setRegen("idle");
        }
      } catch {
        /* keep polling */
      }
    }, INTERVAL_MS);
    return () => clearInterval(timer);
  }, [regen, workspaceUuid, sourceUuid, targetLang, sourceLang, cues, regenStorageKey, t]);

  const regenerateTranscript = async () => {
    if (regen === "running") return;
    setRegen("running");
    setRegenError(null);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/regenerate-transcript`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail || `HTTP ${res.status}`);
      }
      if (typeof window !== "undefined") {
        window.localStorage.setItem(regenStorageKey, String(Date.now()));
      }
    } catch (e) {
      setRegen("error");
      setRegenError(e instanceof Error ? e.message : t("regenEnUnknownError"));
    }
  };

  // Ein Klick spielt immer ab der Zeitmarke der Karte, egal wo in der Karte er landet.
  const onBlockClick = (start: number) => {
    const media = mediaRef.current;
    if (!media) return;
    media.currentTime = start;
    media.play().catch(() => { });
  };

  // One track's text for a block, its sentences joined back into a paragraph.
  const blockText = (lang: string | null, from: number, to: number): string => {
    if (!lang) return "";
    const track = cues[lang];
    if (!track) return "";
    const parts: string[] = [];
    for (let i = from; i <= to; i++) {
      const text = track[i]?.text?.trim();
      if (text) parts.push(text);
    }
    return parts.join(" ");
  };

  // Saving takes the whole paragraph, which is the unit on screen. Keyed by the block's
  // first cue index so the button state keeps working off one number.
  const onSaveBlock = async (from: number, to: number) => {
    if (!onSaveNote || savingCueIdx !== null) return;
    const master = masterCues[from];
    if (!master) return;
    const srcText = blockText(sourceLang, from, to);
    const tgtText = blockText(targetLang, from, to);
    const wantSource = (mode === "source" || mode === "both") && !!srcText;
    const wantTarget = (mode === "target" || mode === "both") && !!tgtText;
    const parts: string[] = [];
    if (wantSource) parts.push(srcText);
    if (wantTarget) parts.push(`*${tgtText}*`);
    const body = parts.join("\n\n");
    if (!body) return;
    const primary = wantSource ? srcText : tgtText;
    const keyword = primary.slice(0, 40).replace(/\s+/g, " ").trim();
    const citation = `[Q1:${sourceUuid}, ${fmtTs(master.start)} | ${keyword}]`;
    setSavingCueIdx(from);
    try {
      await onSaveNote(`${body} ${citation}`, [sourceUuid]);
      setSavedCueIdx(from);
      setTimeout(() => setSavedCueIdx((cur) => (cur === from ? null : cur)), 1500);
    } finally {
      setSavingCueIdx(null);
    }
  };

  if (loading) {
    return (
      <div className="px-4 py-3 text-xs" style={{ color: "var(--muted)" }}>
        {t("transcriptLoading")}
      </div>
    );
  }

  const sourceCues = sourceLang ? cues[sourceLang] : undefined;
  const targetCues = targetLang ? cues[targetLang] : undefined;
  if (!sourceCues && !targetCues) return null;

  // A target spur only counts as its own entry when it is a different language than the
  // original (same-language "translations" would just duplicate the source track).
  const hasSourceTrack = !!sourceCues;
  const hasTargetTrack = !!targetCues && sourceLang !== targetLang;
  const showSource = (mode === "source" || mode === "both") && !!sourceCues;
  const showTarget = (mode === "target" || mode === "both") && !!targetCues;
  const canTranslate = canManage && !!sourceCues && !!sourceLang
    && !!targetLang && targetLang !== sourceLang && !targetCues;

  const modeLabel = (m: ViewMode): string => {
    if (m === "off") return t("tabOff");
    if (m === "both") return t("tabBoth");
    // hasSourceTrack / hasTargetTrack guarantee the matching lang code is set.
    return m === "source" ? langLabel(sourceLang!, locale) : langLabel(targetLang!, locale);
  };
  const modeOptions = buildTranscriptModes({ hasSource: hasSourceTrack, hasTarget: hasTargetTrack })
    .map((m) => ({ value: m, label: modeLabel(m) }));

  return (
    <div
      className="flex flex-col min-h-0 relative"
      style={{ borderTop: "1px solid var(--border)" }}
    >
      {/* Toolbar */}
      <div
        className="flex items-center gap-2 px-4 py-2 flex-shrink-0"
        style={{ backgroundColor: "var(--surface-dim)" }}
      >
        <span
          className="text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--muted)" }}
        >
          {t("transcriptLabel")}
        </span>
        {mode !== "off" && (
          <button
            type="button"
            onClick={jumpToCurrent}
            onMouseEnter={() => setJumpHover(true)}
            onMouseLeave={() => setJumpHover(false)}
            disabled={currentIdx < 0}
            title={t("jumpToCurrent")}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              backgroundColor: followCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
              color: followCurrent || jumpHover ? "var(--kb)" : "var(--muted)",
              border: `2px solid ${jumpHover ? "var(--kb)" : "var(--border)"}`,
            }}
          >
            <NavigationArrow size={14} weight={followCurrent ? "fill" : "regular"} />
          </button>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          {/* The pill buttons this replaced were named by their own text; role="combobox"
              isn't, so it needs an explicit accessible name. */}
          <label htmlFor={`transcript-mode-${sourceUuid}`} className="sr-only">
            {t("transcriptModeLabel")}
          </label>
          <Select<ViewMode>
            id={`transcript-mode-${sourceUuid}`}
            size="sm"
            value={mode}
            onChange={setMode}
            options={modeOptions}
          />
          {canTranslate && (
            <button
              type="button"
              onClick={regenerateTranscript}
              disabled={regen === "running"}
              title={
                regen === "error"
                  ? t("regenEnErrorTitle", { error: regenError ?? "" })
                  : regen === "running"
                  ? t("regenEnRunningTitle")
                  : t("regenEnIdleTitle")
              }
              className="flex-shrink-0 h-6 px-2 flex items-center gap-1 rounded-full transition-colors disabled:opacity-60 disabled:cursor-wait"
              style={{
                backgroundColor: regen === "error" ? "rgba(239, 68, 68, 0.12)" : "var(--surface-dim)",
                color: regen === "error" ? "rgb(239, 68, 68)" : "var(--muted)",
                border: "1px solid var(--border)",
                fontSize: "10px",
              }}
            >
              {regen === "running" ? (
                <Spinner size="xs" color="current" />
              ) : (
                <ArrowsClockwise size={10} weight="bold" />
              )}
              <span>{regen === "running" ? t("regenEnRunning") : t("regenEnButton")}</span>
            </button>
          )}
        </div>
      </div>

      {/* Cue list — hidden entirely when the student switched the transcript off. */}
      {mode !== "off" && (
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {blocks.map((b) => {
          // The paragraph the play head is in. The sentence itself is marked inside it (bold),
          // so grouping does not cost the "where am I" resolution the cues gave us.
          const isCurrent = currentIdx >= b.from && currentIdx <= b.to;
          const isPast = currentIdx >= 0 && b.to < currentIdx;
          const citationTint = `${CITATION_HL_COLOR}33`;  // ~20% amber, the pinned-segment tint
          // The marking is the paragraph's BACKGROUND, a filled surface. It once sat on the
          // sentences themselves, which is more precise on paper and unreadable in practice: an
          // inline span only paints the boxes around its glyphs, so a wrapped sentence came out
          // as stripes with gaps between the lines and ragged ends.
          //
          // ONE marking, never two shades of it. Markiert werden die Absaetze, auf denen der
          // Antwortsatz ruht — meist einer, bei einem Satz aus zwei Momenten beide (siehe
          // claimLineIndices). Der Rest des Chunks ist Implementierungsdetail, nach dem der
          // Leser nie gefragt hat. Sticht KEINE Zeile heraus, wird der ganze Abschnitt
          // markiert, weil eine geratene Zeile neben dem belegenden Satz landet und sich das
          // liest, als stuende er nicht in der Quelle.
          const hasCitation = citationClaimIdxs.length > 0
            ? citationClaimIdxs.some((i) => i >= b.from && i <= b.to)
            : citationIdx >= 0 && b.from <= citationEndIdx && b.to >= citationIdx;
          // Only ONE of the two tracks may own the scroll anchors, or the second would
          // overwrite the first and the citation jump would land on the wrong track's line.
          const anchorTrack = showSource ? sourceLang : targetLang;

          const sentences = (lang: string | null, italic: boolean) => {
            if (!lang) return null;
            const track = cues[lang];
            if (!track) return null;
            const out: React.ReactNode[] = [];
            for (let i = b.from; i <= b.to; i++) {
              const text = track[i]?.text?.trim();
              if (!text) continue;
              out.push(
                <span
                  key={i}
                  ref={lang === anchorTrack ? (el) => { itemRefs.current[i] = el; } : undefined}
                  style={{ fontWeight: !italic && i === currentIdx ? 600 : undefined }}
                >
                  {text}{i < b.to ? " " : ""}
                </span>,
              );
            }
            return out;
          };

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
                  // The amber ALWAYS wins the background so the marking stays visible even
                  // while that same paragraph is the one playing, which would otherwise paint
                  // it blue and leave the marking as a thin border. Once playback moves on, the
                  // marked paragraph stays amber and the new current one takes the blue.
                  backgroundColor: hasCitation
                    ? citationTint
                    : isCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
                  // Der laufende Absatz bekommt rundum den blauen Rahmen, weil der linke
                  // Streifen allein unter der gelben Markierung nicht mehr zu sehen war.
                  border: isCurrent ? "2px solid var(--kb)" : "2px solid transparent",
                  borderLeft: isCurrent
                    ? "3px solid var(--kb)"
                    : hasCitation ? `3px solid ${CITATION_HL_COLOR}` : "3px solid transparent",
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
                    {sentences(sourceLang, false)}
                  </div>
                )}
                {showTarget && (
                  <div
                    className="text-sm italic leading-snug mt-0.5"
                    style={{ color: "var(--muted)" }}
                  >
                    {sentences(targetLang, true)}
                  </div>
                )}
              </div>
              {onSaveNote && (
                <div className="flex justify-end pr-1 mt-0.5 h-5">
                  <button
                    type="button"
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
                </div>
              )}
            </div>
          );
        })}
      </div>
      )}

      {/* Citation pin controls — same corner + pill design as the PDF viewer's page-frame
          bar. Icon-only with full text in title/aria. Shown while a citation is pinned. */}
      {mode !== "off" && citationFocusIdx >= 0 && masterCues[citationFocusIdx] && (
        <div className="absolute bottom-6 right-4 z-10 flex items-center gap-1.5">
          {/* Jump-back: only after the pinned cue scrolled off-screen. Arrow points toward
              it, label is its timestamp. Click replays from there. */}
          {!citationInView && (
            <button
              type="button"
              onClick={jumpToCitation}
              className="flex items-center gap-1 pl-2 pr-2.5 py-1.5 rounded-full text-xs font-medium shadow-md btn-icon"
              style={{ backgroundColor: "var(--surface)", color: "var(--kb)", border: "1px solid var(--kb)" }}
              title={t("jumpToHighlightTime", { time: fmtTs(masterCues[citationFocusIdx].start) })}
              aria-label={t("jumpToHighlightTime", { time: fmtTs(masterCues[citationFocusIdx].start) })}
            >
              {citationDir === "down" ? <ArrowDown size={13} weight="bold" /> : <ArrowUp size={13} weight="bold" />}
              <span className="tabular-nums">{fmtTs(masterCues[citationFocusIdx].start)}</span>
            </button>
          )}
          <button
            type="button"
            onClick={dismissCitation}
            className="flex items-center justify-center w-7 h-7 rounded-full shadow-md btn-icon"
            style={{ backgroundColor: "var(--surface)", color: "var(--foreground)", border: "1px solid var(--border)" }}
            title={t("dismissHighlight")}
            aria-label={t("dismissHighlight")}
          >
            <X size={13} weight="bold" />
          </button>
        </div>
      )}
    </div>
  );
}
