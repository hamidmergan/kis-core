import React, { useEffect, useMemo, useRef, useState } from "react";
import { ArrowsClockwise, Check, NavigationArrow, NotePencil } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import type { AddNoteExtras } from "../../_hooks/useNotes";

interface Cue {
  start: number;
  end: number;
  text: string;
}

type Lang = "de" | "en";
type ViewMode = "de" | "en" | "both";

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
}: {
  mediaRef: React.RefObject<HTMLVideoElement | HTMLAudioElement | null>;
  workspaceUuid: string;
  sourceUuid: string;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
}) {
  const [deCues, setDeCues] = useState<Cue[] | null>(null);
  const [enCues, setEnCues] = useState<Cue[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [mode, setMode] = useState<ViewMode>("both");
  const [currentIdx, setCurrentIdx] = useState<number>(-1);
  const [followCurrent, setFollowCurrent] = useState(true);
  const [savedCueIdx, setSavedCueIdx] = useState<number | null>(null);
  const [savingCueIdx, setSavingCueIdx] = useState<number | null>(null);
  const [regenEn, setRegenEn] = useState<"idle" | "running" | "error">("idle");
  const [regenError, setRegenError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setDeCues(null);
    setEnCues(null);
    const fetchLang = async (lang: Lang): Promise<Cue[] | null> => {
      try {
        const res = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript?lang=${lang}`,
          { credentials: "include" },
        );
        if (!res.ok) return null;
        return parseVtt(await res.text());
      } catch {
        return null;
      }
    };
    Promise.all([fetchLang("de"), fetchLang("en")]).then(([de, en]) => {
      if (cancelled) return;
      setDeCues(de);
      setEnCues(en);
      setLoading(false);
      // Default mode: prefer bilingual if both exist, else whatever is available
      if (de && en) setMode("both");
      else if (de) setMode("de");
      else if (en) setMode("en");
    });
    return () => { cancelled = true; };
  }, [workspaceUuid, sourceUuid]);

  // Use the DE track as the timing master when available (identical timestamps
  // to EN because both come from Whisper on the same audio).
  const masterCues = useMemo(() => deCues ?? enCues ?? [], [deCues, enCues]);

  // Drive currentIdx from the media element's time updates.
  useEffect(() => {
    const media = mediaRef.current;
    if (!media || masterCues.length === 0) return;
    const onTime = () => {
      const t = media.currentTime;
      let lo = 0, hi = masterCues.length - 1, idx = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const c = masterCues[mid];
        if (t < c.start) hi = mid - 1;
        else if (t > c.end) lo = mid + 1;
        else { idx = mid; break; }
      }
      if (idx === -1 && masterCues.length > 0) {
        for (let j = masterCues.length - 1; j >= 0; j--) {
          if (masterCues[j].start <= t) { idx = j; break; }
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
      el.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [currentIdx, followCurrent]);

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

  // Poll for the EN VTT to appear after a translation task was dispatched.
  // The Celery task can take ~30 s for short videos up to several minutes for long
  // ones, so we poll gently and give up after the timeout instead of blocking forever.
  useEffect(() => {
    if (regenEn !== "running") return;
    const started = Date.now();
    const TIMEOUT_MS = 5 * 60 * 1000;
    const INTERVAL_MS = 5000;
    const timer = setInterval(async () => {
      if (Date.now() - started > TIMEOUT_MS) {
        clearInterval(timer);
        setRegenEn("error");
        setRegenError("Übersetzung dauert zu lange. Später prüfen oder erneut versuchen.");
        return;
      }
      try {
        const res = await fetch(
          `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/transcript?lang=en`,
          { credentials: "include" },
        );
        if (res.ok) {
          const cues = parseVtt(await res.text());
          clearInterval(timer);
          setEnCues(cues);
          if (deCues) setMode("both");
          setRegenEn("idle");
        }
      } catch {
        /* keep polling */
      }
    }, INTERVAL_MS);
    return () => clearInterval(timer);
  }, [regenEn, workspaceUuid, sourceUuid, deCues]);

  const regenerateEnTranscript = async () => {
    if (regenEn === "running") return;
    setRegenEn("running");
    setRegenError(null);
    try {
      const res = await fetch(
        `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/regenerate-en-transcript`,
        { method: "POST", credentials: "include" },
      );
      if (!res.ok) {
        const detail = (await res.json().catch(() => null))?.detail;
        throw new Error(detail || `HTTP ${res.status}`);
      }
      // Task was dispatched; polling effect takes over.
    } catch (e) {
      setRegenEn("error");
      setRegenError(e instanceof Error ? e.message : "Unbekannter Fehler");
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
    const deText = deCues?.[idx]?.text;
    const enText = enCues?.[idx]?.text;
    const wantDe = (mode === "de" || mode === "both") && !!deText;
    const wantEn = (mode === "en" || mode === "both") && !!enText;
    const parts: string[] = [];
    if (wantDe) parts.push(deText!);
    if (wantEn) parts.push(enText!);
    const body = parts.join("\n");
    if (!body) return;
    const primary = wantDe ? deText! : enText!;
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
        Transkript wird geladen...
      </div>
    );
  }

  if (!deCues && !enCues) return null;

  const showDe = (mode === "de" || mode === "both") && !!deCues;
  const showEn = (mode === "en" || mode === "both") && !!enCues;
  const hasBoth = !!deCues && !!enCues;

  return (
    <div
      className="flex flex-col min-h-0"
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
          Transkript
        </span>
        <button
          type="button"
          onClick={jumpToCurrent}
          disabled={currentIdx < 0}
          title="Zum aktuellen Transkript springen"
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          style={{
            backgroundColor: followCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
            color: followCurrent ? "var(--kb)" : "var(--muted)",
            border: "1px solid var(--border)",
          }}
        >
          <NavigationArrow size={14} weight={followCurrent ? "fill" : "regular"} />
        </button>
        <div className="flex-1" />
        {hasBoth ? (
          <div className="flex gap-1">
            <TabButton active={mode === "de"} onClick={() => setMode("de")}>Deutsch</TabButton>
            <TabButton active={mode === "en"} onClick={() => setMode("en")}>English</TabButton>
            <TabButton active={mode === "both"} onClick={() => setMode("both")}>Beide</TabButton>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs" style={{ color: "var(--muted)" }}>
              {deCues ? "Deutsch" : "English"}
            </span>
            {canManage && deCues && !enCues && (
              <button
                type="button"
                onClick={regenerateEnTranscript}
                disabled={regenEn === "running"}
                title={
                  regenEn === "error"
                    ? `EN-Übersetzung fehlgeschlagen: ${regenError}. Nochmal versuchen?`
                    : regenEn === "running"
                    ? "Übersetzung läuft im Hintergrund..."
                    : "Englische Untertitel im Hintergrund übersetzen"
                }
                className="flex-shrink-0 h-6 px-2 flex items-center gap-1 rounded-full transition-colors disabled:opacity-60 disabled:cursor-wait"
                style={{
                  backgroundColor: regenEn === "error" ? "rgba(239, 68, 68, 0.12)" : "var(--surface-dim)",
                  color: regenEn === "error" ? "rgb(239, 68, 68)" : "var(--muted)",
                  border: "1px solid var(--border)",
                  fontSize: "10px",
                }}
              >
                {regenEn === "running" ? (
                  <Spinner size="xs" color="current" />
                ) : (
                  <ArrowsClockwise size={10} weight="bold" />
                )}
                <span>{regenEn === "running" ? "läuft..." : "EN übersetzen"}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Cue list */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
        {masterCues.map((c, idx) => {
          const isCurrent = idx === currentIdx;
          const isPast = currentIdx >= 0 && idx < currentIdx;
          const deText = deCues?.[idx]?.text;
          const enText = enCues?.[idx]?.text;
          return (
            <div
              key={idx}
              ref={(el) => { itemRefs.current[idx] = el; }}
              className="group mb-2"
              style={{ opacity: !isCurrent && isPast ? 0.55 : 1 }}
            >
              <div
                onClick={() => onCueClick(c)}
                className="px-3 py-2 rounded-md cursor-pointer transition-colors"
                style={{
                  backgroundColor: isCurrent ? "rgba(var(--kb-rgb), 0.12)" : "transparent",
                  borderLeft: isCurrent ? "3px solid var(--kb)" : "3px solid transparent",
                }}
                onMouseEnter={(e) => {
                  if (!isCurrent) e.currentTarget.style.backgroundColor = "var(--surface-dim)";
                }}
                onMouseLeave={(e) => {
                  if (!isCurrent) e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <div
                  className="text-[10px] font-mono mb-1"
                  style={{ color: "var(--muted)" }}
                >
                  {fmtTs(c.start)} – {fmtTs(c.end)}
                </div>
                {showDe && deText && (
                  <div
                    className="text-sm leading-snug"
                    style={{
                      color: "var(--foreground)",
                      fontWeight: isCurrent ? 600 : 400,
                    }}
                  >
                    {deText}
                  </div>
                )}
                {showEn && enText && (
                  <div
                    className="text-sm italic leading-snug mt-0.5"
                    style={{ color: "var(--muted)" }}
                  >
                    {enText}
                  </div>
                )}
              </div>
              {onSaveNote && (
                <div className="flex justify-end pr-1 mt-0.5 h-5">
                  <button
                    type="button"
                    disabled={savingCueIdx === idx}
                    onClick={(e) => { e.stopPropagation(); onSaveCue(idx); }}
                    title="Als Notiz speichern"
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
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2.5 py-1 rounded-full text-xs font-medium transition-colors"
      style={{
        backgroundColor: active ? "var(--kb)" : "transparent",
        color: active ? "#fff" : "var(--muted)",
        border: active ? "1px solid var(--kb)" : "1px solid var(--border)",
      }}
    >
      {children}
    </button>
  );
}
