import React, { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowDown, ArrowsClockwise, ArrowUp, Check, NavigationArrow, NotePencil, X } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { langLabel, type TranscriptDefaultLang } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { cueIndexAtTime } from "./_transcript";
import { CITATION_HL_COLOR } from "./_highlight";

interface Cue {
  start: number;
  end: number;
  text: string;
}

// Which transcript spurs are shown. "source" = original media language,
// "target" = the owner-chosen translation, "both" = stacked.
type ViewMode = "source" | "target" | "both";

interface LangInfo {
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
  canManage = false,
  onSaveNote,
  defaultLang = "both",
  citationTime,
  citationNonce,
}: {
  mediaRef: React.RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  workspaceUuid: string;
  sourceUuid: string;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  defaultLang?: TranscriptDefaultLang;
  // The cited segment's start time (set only on a citation-chip jump) and the jump's
  // nonce, used to pin a navigable "citation highlight" the way the PDF viewer frames
  // the cited page.
  citationTime?: number;
  citationNonce?: number;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  // Cues keyed by ISO language code (e.g. { de: [...], en: [...] }).
  const [cues, setCues] = useState<Record<string, Cue[]>>({});
  const [sourceLang, setSourceLang] = useState<string | null>(null);
  const [targetLang, setTargetLang] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<ViewMode>(defaultLang);
  const [currentIdx, setCurrentIdx] = useState<number>(-1);
  const [followCurrent, setFollowCurrent] = useState(true);
  const [jumpHover, setJumpHover] = useState(false);
  // Pinned citation segment: index of the cue a citation chip jumped to (-1 = none),
  // whether it is currently scrolled into view, and which way it lies relative to the
  // viewport (so the jump-back button can point an arrow at it).
  const [citationIdx, setCitationIdx] = useState<number>(-1);
  const [citationInView, setCitationInView] = useState(true);
  const [citationDir, setCitationDir] = useState<"up" | "down">("down");
  const citationNonceRef = useRef<number | undefined>(undefined);
  const [savedCueIdx, setSavedCueIdx] = useState<number | null>(null);
  const [savingCueIdx, setSavingCueIdx] = useState<number | null>(null);
  const [regen, setRegen] = useState<"idle" | "running" | "error">("idle");
  const [regenError, setRegenError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({});
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
    setLoading(true);
    setCues({});
    setSourceLang(null);
    setTargetLang(null);

    const fetchVtt = async (lang: string): Promise<Cue[] | null> => {
      try {
        const res = await fetch(transcriptUrl(lang), { credentials: "include" });
        if (!res.ok) return null;
        return parseVtt(await res.text());
      } catch {
        return null;
      }
    };

    (async () => {
      let info: LangInfo = { source_lang: null, target_lang: null, available: [] };
      try {
        const res = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript/langs`,
          { credentials: "include" },
        );
        if (res.ok) info = await res.json();
      } catch { /* no transcript */ }
      if (cancelled) return;

      const entries = await Promise.all(
        info.available.map(async (lang) => [lang, await fetchVtt(lang)] as const),
      );
      if (cancelled) return;

      const map: Record<string, Cue[]> = {};
      for (const [lang, c] of entries) if (c) map[lang] = c;
      setCues(map);
      setSourceLang(info.source_lang);
      setTargetLang(info.target_lang);
      setLoading(false);

      const hasSource = !!(info.source_lang && map[info.source_lang]);
      const hasTarget = !!(info.target_lang && map[info.target_lang] && info.target_lang !== info.source_lang);
      if (hasSource && hasTarget) setMode(defaultLang);
      else if (hasSource) setMode("source");
      else if (hasTarget) setMode("target");

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

    return () => { cancelled = true; };
  }, [workspaceUuid, sourceUuid, regenStorageKey, defaultLang]);

  // Source-language track is the timing master (identical timestamps to the
  // translation — both derive from Whisper on the same audio).
  const masterCues = useMemo(() => {
    if (sourceLang && cues[sourceLang]) return cues[sourceLang];
    const first = Object.values(cues)[0];
    return first ?? [];
  }, [cues, sourceLang]);

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
  }, [currentIdx, followCurrent]);

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
  useEffect(() => {
    if (citationTime == null || masterCues.length === 0) { setCitationIdx(-1); return; }
    const idx = cueIndexAtTime(masterCues, citationTime);
    setCitationIdx(idx);
    if (idx >= 0 && citationNonceRef.current !== citationNonce) {
      citationNonceRef.current = citationNonce;
      requestAnimationFrame(() => {
        itemRefs.current[idx]?.scrollIntoView({ block: "center", behavior: "instant" });
      });
    }
  }, [citationNonce, citationTime, masterCues]);

  // Track whether the pinned cue is on-screen so the jump-back button only shows once
  // it has scrolled out of view (like the PDF jump button appearing after you page away).
  // Programmatic follow-scrolls fire scroll events too, so this stays in sync with both.
  useEffect(() => {
    if (citationIdx < 0) { setCitationInView(true); return; }
    const list = listRef.current;
    if (!list) return;
    const check = () => {
      const el = itemRefs.current[citationIdx];
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
  }, [citationIdx]);

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

  // Jump back to the pinned citation: replay from its timestamp and scroll to it.
  const jumpToCitation = () => {
    if (citationIdx < 0) return;
    const cue = masterCues[citationIdx];
    const media = mediaRef.current;
    if (media && cue) {
      media.currentTime = cue.start;
      media.play().catch(() => { });
    }
    itemRefs.current[citationIdx]?.scrollIntoView({ block: "center", behavior: "smooth" });
    setFollowCurrent(true);
  };

  const dismissCitation = () => setCitationIdx(-1);

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
          if (sourceLang && cues[sourceLang]) setMode("both");
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

  const onCueClick = (cue: Cue) => {
    const media = mediaRef.current;
    if (!media) return;
    media.currentTime = cue.start;
    media.play().catch(() => { });
  };

  const onSaveCue = async (idx: number) => {
    if (!onSaveNote || savingCueIdx !== null) return;
    const master = masterCues[idx];
    if (!master) return;
    const srcText = sourceLang ? cues[sourceLang]?.[idx]?.text : undefined;
    const tgtText = targetLang ? cues[targetLang]?.[idx]?.text : undefined;
    const wantSource = (mode === "source" || mode === "both") && !!srcText;
    const wantTarget = (mode === "target" || mode === "both") && !!tgtText;
    const parts: string[] = [];
    if (wantSource) parts.push(srcText!);
    if (wantTarget) parts.push(`*${tgtText!}*`);
    const body = parts.join("\n\n");
    if (!body) return;
    const primary = wantSource ? srcText! : tgtText!;
    const keyword = primary.slice(0, 40).replace(/\s+/g, " ").trim();
    const citation = `[Q1:${sourceUuid}, ${fmtTs(master.start)} | ${keyword}]`;
    setSavingCueIdx(idx);
    try {
      await onSaveNote(`${body} ${citation}`, [sourceUuid]);
      setSavedCueIdx(idx);
      setTimeout(() => setSavedCueIdx((cur) => (cur === idx ? null : cur)), 1500);
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

  const hasBoth = !!sourceCues && !!targetCues && sourceLang !== targetLang;
  const showSource = (mode === "source" || mode === "both") && !!sourceCues;
  const showTarget = (mode === "target" || mode === "both") && !!targetCues;
  // The single visible language label when only one spur exists.
  const soleLang = sourceCues ? sourceLang : targetLang;
  const canTranslate = canManage && !!sourceCues && !!sourceLang
    && !!targetLang && targetLang !== sourceLang && !targetCues;

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
        <div className="flex-1" />
        {hasBoth ? (
          <div className="flex gap-1">
            <TabButton active={mode === "source"} onClick={() => setMode("source")}>{langLabel(sourceLang!, locale)}</TabButton>
            <TabButton active={mode === "target"} onClick={() => setMode("target")}>{langLabel(targetLang!, locale)}</TabButton>
            <TabButton active={mode === "both"} onClick={() => setMode("both")}>{t("tabBoth")}</TabButton>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              {soleLang ? langLabel(soleLang, locale) : ""}
            </span>
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
        )}
      </div>

      {/* Cue list */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {masterCues.map((c, idx) => {
          const isCurrent = idx === currentIdx;
          const isCitation = idx === citationIdx;
          const isPast = currentIdx >= 0 && idx < currentIdx;
          const citationTint = `${CITATION_HL_COLOR}33`;  // ~20% amber, the pinned-segment tint
          const srcText = sourceLang ? cues[sourceLang]?.[idx]?.text : undefined;
          const tgtText = targetLang ? cues[targetLang]?.[idx]?.text : undefined;
          return (
            <div
              key={idx}
              ref={(el) => { itemRefs.current[idx] = el; }}
              className="group mb-2"
              style={{ opacity: !isCurrent && !isCitation && isPast ? 0.55 : 1 }}
            >
              <div
                onClick={() => onCueClick(c)}
                className="px-3 py-2 rounded-md cursor-pointer transition-colors"
                style={{
                  // The amber citation pin ALWAYS wins the background so the yellow marking is
                  // reliably visible even while that same cue is the one playing (which would
                  // otherwise paint it blue and hide the pin behind a thin border). Once
                  // playback moves on, the pinned cue stays amber and the new current cue
                  // takes the blue.
                  backgroundColor: isCitation
                    ? citationTint
                    : isCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
                  borderLeft: isCitation
                    ? `3px solid ${CITATION_HL_COLOR}`
                    : isCurrent ? "3px solid var(--kb)" : "3px solid transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isCurrent && !isCitation) e.currentTarget.style.backgroundColor = "var(--surface-dim)";
                }}
                onMouseLeave={(e) => {
                  if (!isCurrent && !isCitation) e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <div
                  className="text-[10px] font-mono mb-1"
                  style={{ color: "var(--muted)" }}
                >
                  {fmtTs(c.start)} - {fmtTs(c.end)}
                </div>
                {showSource && srcText && (
                  <div
                    className="text-sm leading-snug"
                    style={{
                      color: "var(--foreground)",
                      fontWeight: isCurrent ? 600 : 400,
                    }}
                  >
                    {srcText}
                  </div>
                )}
                {showTarget && tgtText && (
                  <div
                    className="text-sm italic leading-snug mt-0.5"
                    style={{ color: "var(--muted)" }}
                  >
                    {tgtText}
                  </div>
                )}
              </div>
              {onSaveNote && (
                <div className="flex justify-end pr-1 mt-0.5 h-5">
                  <button
                    type="button"
                    disabled={savingCueIdx === idx}
                    onClick={(e) => { e.stopPropagation(); onSaveCue(idx); }}
                    title={t("saveAsNote")}
                    className={`[@media(hover:hover)]:opacity-0 [@media(hover:hover)]:group-hover:opacity-100 p-1 rounded-full ${savedCueIdx === idx ? "" : "btn-icon"}`}
                    style={savedCueIdx === idx ? { color: "var(--success)" } : undefined}
                  >
                    {savingCueIdx === idx
                      ? <Spinner size="xs" color="current" />
                      : savedCueIdx === idx ? <Check size={13} weight="bold" /> : <NotePencil size={13} />}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Citation pin controls — same corner + pill design as the PDF viewer's page-frame
          bar. Icon-only with full text in title/aria. Shown while a citation is pinned. */}
      {citationIdx >= 0 && masterCues[citationIdx] && (
        <div className="absolute bottom-6 right-4 z-10 flex items-center gap-1.5">
          {/* Jump-back: only after the pinned cue scrolled off-screen. Arrow points toward
              it, label is its timestamp. Click replays from there. */}
          {!citationInView && (
            <button
              type="button"
              onClick={jumpToCitation}
              className="flex items-center gap-1 pl-2 pr-2.5 py-1.5 rounded-full text-xs font-medium shadow-md btn-icon"
              style={{ backgroundColor: "var(--surface)", color: "var(--kb)", border: "1px solid var(--kb)" }}
              title={t("jumpToHighlightTime", { time: fmtTs(masterCues[citationIdx].start) })}
              aria-label={t("jumpToHighlightTime", { time: fmtTs(masterCues[citationIdx].start) })}
            >
              {citationDir === "down" ? <ArrowDown size={13} weight="bold" /> : <ArrowUp size={13} weight="bold" />}
              <span className="tabular-nums">{fmtTs(masterCues[citationIdx].start)}</span>
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

function TabButton({
  active, onClick, children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const [hover, setHover] = useState(false);
  const showHover = hover && !active;
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
      style={{
        backgroundColor: active ? "var(--kb)" : "transparent",
        color: active ? "#fff" : showHover ? "var(--kb)" : "var(--muted)",
        border: `2px solid ${active || showHover ? "var(--kb)" : "var(--border)"}`,
      }}
    >
      {children}
    </button>
  );
}
