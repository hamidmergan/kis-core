import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowDown, ArrowsClockwise, ArrowUp, Check, NavigationArrow, NotePencil, X } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import { genericErrorMessage, parseDetail } from "@/lib/api";
import { langLabel } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { buildTranscriptModes, groupCues, resolveCitationFocus, type TranscriptMode } from "./_transcript";
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
  // The languages come from the player, null means not loaded yet.
  langInfo: LangInfo | null;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  // Reports a switched-off transcript so the player drops its tracks.
  onOffChange?: (off: boolean) => void;
  // The timestamp of the citation and the id of the jump.
  citationTime?: number;
  // The end of the cited chunk, not of a single line.
  citationEndTime?: number;
  // The start of the chunk, otherwise everything before it stays unmarked.
  citationChunkStart?: number;
  // The backed answer text, used to find the carrying line.
  citationClaim?: string;
  citationNonce?: number;
  // Reports the highlighted line so the player jumps there.
  onCitationFocusTime?: (time: number, nonce?: number) => void;
  // In listening comprehension the transcript starts off, but it is not locked.
  startOff?: boolean;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  // Cues keyed by ISO language code (e.g. { de: [...], en: [...] }).
  const [cues, setCues] = useState<Record<string, Cue[]>>({});
  const [sourceLang, setSourceLang] = useState<string | null>(null);
  const [targetLang, setTargetLang] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Always opens on the original track, coming from a listening exercise it opens off.
  const [mode, setMode] = useState<ViewMode>(startOff ? "off" : "source");
  // As a ref so a prop change does not trigger the loading again.
  const startOffRef = useRef(startOff);
  startOffRef.current = startOff;
  // Every new recording from an exercise starts switched off again.
  useEffect(() => {
    if (startOff) setMode("off");
  }, [sourceUuid, startOff]);
  const [currentIdx, setCurrentIdx] = useState<number>(-1);
  // Following along is off by default, the user turns it on.
  const [followCurrent, setFollowCurrent] = useState(false);
  const [jumpHover, setJumpHover] = useState(false);
  // The pinned spot, whether it is visible and in which direction it lies.
  const [citationIdx, setCitationIdx] = useState<number>(-1);
  // The last line of the cited spot, only when no single one stands out.
  const [citationEndIdx, setCitationEndIdx] = useState<number>(-1);
  // Which line carries the claim, it is highlight and jump target at once.
  const [citationClaimIdx, setCitationClaimIdx] = useState<number>(-1);
  // All carrying lines, one answer sentence often names two moments.
  const [citationClaimIdxs, setCitationClaimIdxs] = useState<number[]>([]);
  const [citationInView, setCitationInView] = useState(true);
  const [citationDir, setCitationDir] = useState<"up" | "down">("down");
  const citationNonceRef = useRef<number | undefined>(undefined);
  // Which source the loaded lines belong to, guarding against stale data on a switch.
  const cuesUuidRef = useRef<string | null>(null);
  const [savedCueIdx, setSavedCueIdx] = useState<number | null>(null);
  const [savingCueIdx, setSavingCueIdx] = useState<number | null>(null);
  const [regen, setRegen] = useState<"idle" | "running" | "error">("idle");
  const [regenError, setRegenError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  // The anchors hang off the sentence, not off the paragraph.
  const itemRefs = useRef<Record<number, HTMLElement | null>>({});
  const lastScrolledIdx = useRef<number>(-1);

  // Records the start of a translation so the state survives a reload.
  const regenStorageKey = `kis:transcript-translate:${sourceUuid}`;
  const REGEN_TTL_MS = 10 * 60 * 1000;

  const transcriptUrl = (lang: string) =>
    `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript?lang=${lang}`;

  useEffect(() => {
    let cancelled = false;
    // Abort running requests, otherwise the connections run out.
    const ac = new AbortController();
    setLoading(true);
    setCues({});
    setSourceLang(null);
    setTargetLang(null);
    cuesUuidRef.current = null; // cues are now stale until this source's transcript loads

    // The languages come from the player, only the tracks themselves are fetched.
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
      // The original wins, a switched-off transcript stays off.
      const keep = (next: ViewMode) => (m: ViewMode) =>
        (m === "off" && startOffRef.current ? m : next);
      if (hasSource) setMode(keep("source"));
      else if (hasTarget) setMode(keep("target"));

      // Reattaches to a running translation job.
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

  // The original track sets the times, both come from the same recognition.
  const masterCues = useMemo(() => {
    if (sourceLang && cues[sourceLang]) return cues[sourceLang];
    const first = Object.values(cues)[0];
    return first ?? [];
  }, [cues, sourceLang]);

  // Paragraphs for reading, the lines stay the unit for everything that points.
  const blocks = useMemo(() => groupCues(masterCues), [masterCues]);

  // The whole recording as the yardstick for how common a word is here.
  const claimCorpus = useMemo(() => {
    const src = sourceLang ? cues[sourceLang] : undefined;
    const tgt = targetLang ? cues[targetLang] : undefined;
    const n = Math.max(src?.length ?? 0, tgt?.length ?? 0);
    const out: string[] = [];
    for (let i = 0; i < n; i++) out.push(`${src?.[i]?.text ?? ""} ${tgt?.[i]?.text ?? ""}`);
    return out;
  }, [cues, sourceLang, targetLang]);

  // The highlighted line, everything pointing at it uses this value.
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
    // The list is unmounted in off mode, coming back needs a fresh centring.
  }, [currentIdx, followCurrent, mode]);

  // A new source clears any pinned citation before its cues load.
  useEffect(() => { setCitationIdx(-1); }, [sourceUuid]);

  // The highlight is always set, the scrolling exactly once per jump.
  useEffect(() => {
    // Ignore lines of the previous source, otherwise it jumps to the wrong place.
    if (cuesUuidRef.current !== sourceUuid) return;
    if (citationTime == null || masterCues.length === 0) {
      setCitationIdx(-1); setCitationEndIdx(-1); setCitationClaimIdx(-1);
      setCitationClaimIdxs([]);
      return;
    }
    // One resolver for highlight, jump and play head, here instead of in a memo.
    const focus = resolveCitationFocus(masterCues, citationTime, citationEndTime, citationClaim, claimCorpus, citationChunkStart);
    setCitationIdx(focus.idx);
    setCitationEndIdx(focus.endIdx);
    setCitationClaimIdx(focus.claimIdx);
    setCitationClaimIdxs(focus.claimIdxs);
    // Once a carrying line is fixed, the player starts from there.
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

  // The back button only appears when the highlight is out of view.
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
    // In off mode the observer goes with the list, coming back needs a new one.
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

  // Report only on a real change, otherwise an endless loop looms.
  const lastOffReportedRef = useRef<boolean | null>(null);
  useEffect(() => {
    const off = mode === "off";
    if (lastOffReportedRef.current === off) return;
    lastOffReportedRef.current = off;
    onOffChange?.(off);
  }, [mode, onOffChange]);

  // The jump back only scrolls, the playback stays untouched.
  const jumpToCitation = () => {
    if (citationFocusIdx < 0) return;
    // Same target as the original jump, so pressing the button twice never lands differently.
    itemRefs.current[citationFocusIdx]?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  // Highlight and chip frame go away together.
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
          // A finished translation shows both tracks, unless the transcript is off.
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
        throw new Error(parseDetail(detail, genericErrorMessage()));
      }
      if (typeof window !== "undefined") {
        window.localStorage.setItem(regenStorageKey, String(Date.now()));
      }
    } catch (e) {
      setRegen("error");
      setRegenError(e instanceof Error ? e.message : t("regenEnUnknownError"));
    }
  };

  // A click always plays from the card's timestamp, wherever in the card it lands.
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

  // The whole paragraph is saved, named after its first line.
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

  // A target track only counts when it has a different language.
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
          // The running paragraph, the sentence inside it stays separately emphasised.
          const isCurrent = currentIdx >= b.from && currentIdx <= b.to;
          const isPast = currentIdx >= 0 && b.to < currentIdx;
          const citationTint = "var(--cite-bg)";  // dezentes CD-Blau, abgesetzt vom Panel-Hintergrund
          // The paragraph area is highlighted, and only one shade.
          const hasCitation = citationClaimIdxs.length > 0
            ? citationClaimIdxs.some((i) => i >= b.from && i <= b.to)
            : citationIdx >= 0 && b.from <= citationEndIdx && b.to >= citationIdx;
          // Only one of the two tracks carries the scroll anchors.
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
                  // The highlight always wins the background.
                  backgroundColor: hasCitation
                    ? citationTint
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
