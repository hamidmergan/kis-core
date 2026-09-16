import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretLeft, SidebarSimple, SpeakerHigh } from "@phosphor-icons/react";
import { type ViewerState } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { FileIcon } from "../sources/FileIcon";
import { TranscriptPanel, type LangInfo } from "./TranscriptPanel";
import { htmlMediaController, type MediaController } from "./mediaController";
import { YoutubeEmbed } from "./YoutubeEmbed";

// Without a language list the transcript leaves the loading state instead of waiting.
const EMPTY_LANGS: LangInfo = { source_lang: null, target_lang: null, available: [] };

export function MediaPlayer({
  source, onClose, workspaceUuid, onMinimize, canManage = false, onSaveNote,
  youtubeConsent = false, onYoutubeConsent = () => { },
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onMinimize?: () => void;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
  // One click, ever, per browser: the page reads it from localStorage.
  youtubeConsent?: boolean;
  onYoutubeConsent?: () => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const tPanels = useTranslations("workspace.detail.panels");
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const isYoutube = !!source.youtubeId;
  const mediaUrl = `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`;

  // The element exists only after the render and changes with the kind of source.
  const [controller, setController] = useState<MediaController | null>(null);
  useEffect(() => {
    // A YouTube source gets its controller from the embed, never from a leftover element.
    const el = isYoutube ? null : mediaRef.current;
    setController(el ? htmlMediaController(el) : null);
  }, [isVideo, isYoutube, source.uuid]);

  // The languages are fetched once per source and passed on.
  const [langInfo, setLangInfo] = useState<LangInfo | null>(null);
  // In listening comprehension the panel starts off, but it is not locked.
  const startTranscriptOff = Boolean(source.hideTranscript);
  useEffect(() => {
    // Abort running requests, otherwise the connections run out.
    setLangInfo(null);
    const ac = new AbortController();
    fetch(
      `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/transcript/langs`,
      { credentials: "include", signal: ac.signal },
    )
      // Non-2xx (e.g. no transcript) resolves to "no languages" so the panel leaves loading.
      .then((res) => (res.ok ? res.json() : EMPTY_LANGS))
      .then((data: LangInfo) => setLangInfo(data))
      .catch((e) => { if (e?.name !== "AbortError") setLangInfo(EMPTY_LANGS); });
    return () => ac.abort();
  }, [workspaceUuid, source.uuid]);

  // Where the transcript puts the highlight, only the panel knows the lines.
  const [focus, setFocus] = useState<{ nonce?: number; time: number } | null>(null);
  const onCitationFocusTime = useCallback((time: number, nonce?: number) => {
    // Bail out on an unchanged value, otherwise the effect loops forever.
    setFocus((prev) => (prev && prev.nonce === nonce && prev.time === time ? prev : { nonce, time }));
  }, []);
  const seekTarget = source.isCitation && focus && focus.nonce === source.nonce
    ? focus.time
    : source.startTime;

  // Only seek once the new source is loaded and really seekable.
  useEffect(() => {
    if (isYoutube) return;
    const media = mediaRef.current;
    if (seekTarget === undefined || !media) return;
    const target = seekTarget;
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
      // Watches that the play position does not snap back, only downwards.
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
    // The refined time arrives one round later, hence this value.
  }, [isYoutube, seekTarget, source.nonce, source.uuid]);

  return (
    <div className="flex flex-col h-full">
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
        {isYoutube ? (
          <YoutubeEmbed
            videoId={source.youtubeId as string}
            title={source.filename}
            consent={youtubeConsent}
            onConsent={onYoutubeConsent}
            seekTarget={seekTarget}
            seekNonce={source.nonce}
            onController={setController}
          />
        ) : isVideo ? (
          // No subtitle tracks and no download in the player menu.
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={mediaUrl}
            controls
            controlsList="nodownload"
            onContextMenu={(e) => e.preventDefault()}
            className="w-full max-h-full rounded-lg"
            style={{ backgroundColor: "#000" }}
          />
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
              controlsList="nodownload"
              onContextMenu={(e) => e.preventDefault()}
              className="w-full"
            />
          </div>
        )}
      </div>
      <TranscriptPanel
        controller={controller}
        workspaceUuid={workspaceUuid}
        sourceUuid={source.uuid}
        langInfo={langInfo}
        canManage={canManage}
        onSaveNote={onSaveNote}
        citationTime={source.isCitation ? source.startTime : undefined}
        citationEndTime={source.isCitation ? source.endTime : undefined}
        citationChunkStart={source.isCitation ? source.chunkStart : undefined}
        citationClaim={source.isCitation ? source.citationClaim : undefined}
        citationNonce={source.nonce}
        onCitationFocusTime={onCitationFocusTime}
        startOff={startTranscriptOff}
      />
    </div>
  );
}
