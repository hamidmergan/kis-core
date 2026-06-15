import React, { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretLeft, SidebarSimple, SpeakerHigh } from "@phosphor-icons/react";
import { langLabel, type ViewerState, type TranscriptDefaultLang } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { FileIcon } from "../sources/FileIcon";
import { TranscriptPanel } from "./TranscriptPanel";

export function MediaPlayer({
  source, onClose, workspaceUuid, onMinimize, canDownload = false, canManage = false, onSaveNote, defaultTranscriptLang = "both",
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onMinimize?: () => void;
  canDownload?: boolean;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  defaultTranscriptLang?: TranscriptDefaultLang;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const tPanels = useTranslations("workspace.detail.panels");
  const locale = useLocale();
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const mediaUrl = `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`;
  const transcriptUrl = (lang: string) =>
    `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/transcript?lang=${lang}`;

  // Ask the backend which transcript languages exist so we only attach available
  // <track> elements — works for any source/target language pair, not just de/en.
  const [availableLangs, setAvailableLangs] = useState<string[]>([]);
  useEffect(() => {
    // Abort (not just ignore) on source switch: an in-flight request that is never
    // cancelled keeps holding one of the browser's few per-origin connections, and a
    // few rapid source switches exhaust them and freeze the page.
    const ac = new AbortController();
    fetch(
      `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/transcript/langs`,
      { credentials: "include", signal: ac.signal },
    )
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (data) setAvailableLangs(data.available ?? []); })
      .catch(() => { /* aborted or no tracks */ });
    return () => ac.abort();
  }, [workspaceUuid, source.uuid]);

  // Seek to the cited timestamp when the source changes — robust against Safari, which is the
  // only browser that misbehaves here (Chrome seeks fine).
  //
  // Two Safari quirks: (1) on a source SWITCH the element still has the OLD resource loaded for
  // a tick, so an immediate seek hits the wrong media; (2) right after a (re)load Safari SNAPS
  // currentTime back toward 0 until the resource is really seekable, so a one-shot seek sticks
  // only "sometimes". So we seek only once `currentSrc` is the NEW source AND `seekable` covers
  // the target, then for a short window keep watching and re-apply if Safari snaps it back to
  // ~0. Forward playback (currentTime >= target) is never disturbed.
  useEffect(() => {
    const media = mediaRef.current;
    if (source.startTime === undefined || !media) return;
    const target = source.startTime;
    const uuid = source.uuid;
    const deadline = Date.now() + 8000; // stop watching once the load has settled
    let seeked = false;
    const reachable = () =>
      media.currentSrc.includes(uuid) &&
      media.seekable.length > 0 &&
      media.seekable.end(media.seekable.length - 1) >= target - 0.25;
    const tick = () => {
      if (Date.now() > deadline) { stop(); return; }
      if (!reachable()) return;
      if (!seeked) {
        try { media.currentTime = target; } catch { return; }
        media.play().catch(() => { });
        if (Math.abs(media.currentTime - target) < 0.5) seeked = true; // stuck (else retry next event)
        return;
      }
      // Watchdog: undo Safari snapping currentTime back toward 0 after the seek — downward only,
      // so playing forward past the target is left alone.
      if (target > 1 && media.currentTime < target - 0.5) {
        try { media.currentTime = target; } catch { /* ignore */ }
        media.play().catch(() => { });
      }
    };
    const events = ["loadedmetadata", "loadeddata", "canplay", "canplaythrough", "progress", "durationchange", "seeked", "timeupdate", "playing"];
    const stop = () => events.forEach((e) => media.removeEventListener(e, tick));
    events.forEach((e) => media.addEventListener(e, tick));
    tick();
    return stop;
  }, [source.startTime, source.nonce, source.uuid]);

  return (
    <div className="flex flex-col h-full viewer-short">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <button type="button" onClick={onClose}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }} title={t("back")}>
          <CaretLeft size={13} weight="bold" />
        </button>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--foreground)" }}>{source.filename}</span>
        {onMinimize && (
          <button type="button" onClick={onMinimize}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon ml-2"
            style={{ backgroundColor: "var(--surface-dim)" }} title={tPanels("minimize")}>
            <SidebarSimple size={13} />
          </button>
        )}
      </div>
      {/* Player */}
      <div className="flex items-center justify-center p-4 flex-shrink-0" style={{ maxHeight: "55%" }}>
        {isVideo ? (
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={mediaUrl}
            controls
            controlsList={canDownload ? undefined : "nodownload"}
            onContextMenu={canDownload ? undefined : (e) => e.preventDefault()}
            className="w-full max-h-full rounded-lg"
            style={{ backgroundColor: "#000" }}
          >
            {availableLangs.map((lang) => (
              <track
                key={lang}
                kind="subtitles"
                src={transcriptUrl(lang)}
                srcLang={lang}
                label={langLabel(lang, locale)}
              />
            ))}
          </video>
        ) : (
          <div className="w-full max-w-md flex flex-col items-center gap-4">
            <div
              className="w-24 h-24 rounded-full flex items-center justify-center"
              style={{ backgroundColor: "rgba(var(--kb-rgb),0.1)" }}
            >
              <SpeakerHigh size={40} weight="bold" style={{ color: "var(--kb)" }} />
            </div>
            <span className="text-sm font-medium truncate max-w-full">{source.filename}</span>
            <audio
              ref={mediaRef as React.RefObject<HTMLAudioElement>}
              src={mediaUrl}
              controls
              controlsList={canDownload ? undefined : "nodownload"}
              onContextMenu={canDownload ? undefined : (e) => e.preventDefault()}
              className="w-full"
            />
          </div>
        )}
      </div>
      <TranscriptPanel
        mediaRef={mediaRef}
        workspaceUuid={workspaceUuid}
        sourceUuid={source.uuid}
        canManage={canManage}
        onSaveNote={onSaveNote}
        defaultLang={defaultTranscriptLang}
        citationTime={source.isCitation ? source.startTime : undefined}
        citationNonce={source.nonce}
      />
    </div>
  );
}
