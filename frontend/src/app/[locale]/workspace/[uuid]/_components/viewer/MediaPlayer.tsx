import React, { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretLeft, SidebarSimple, SpeakerHigh } from "@phosphor-icons/react";
import { type ViewerState } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { FileIcon } from "../sources/FileIcon";
import { TranscriptPanel, type LangInfo } from "./TranscriptPanel";

// "No transcript languages" — used when the langs request is missing or fails so the
// transcript panel resolves out of its loading state instead of waiting forever.
const EMPTY_LANGS: LangInfo = { source_lang: null, target_lang: null, available: [] };

export function MediaPlayer({
  source, onClose, workspaceUuid, onMinimize, canManage = false, onSaveNote,
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onMinimize?: () => void;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const tPanels = useTranslations("workspace.detail.panels");
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const mediaUrl = `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`;

  // Ask the backend which transcript languages exist ONCE here, then hand the result to
  // the TranscriptPanel below so the langs endpoint is hit a single time per source.
  const [langInfo, setLangInfo] = useState<LangInfo | null>(null);
  // Beim Hör- und Leseverstehen startet das Panel auf "aus", damit niemand mitliest statt
  // zuzuhören. Gesperrt ist es nicht: der Umschalter im Panel stellt es jederzeit wieder an.
  const startTranscriptOff = Boolean(source.hideTranscript);
  useEffect(() => {
    // Clear on source switch (panel shows loading) and abort the in-flight request: an
    // uncancelled request keeps holding one of the browser's few per-origin connections,
    // and a few rapid switches exhaust them and freeze the page.
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

  // Where the transcript put the marking. A citation chip carries the cited CHUNK's start,
  // but the chunk runs about a minute and the sentence the answer rests on is often a line or
  // two further down — the transcript marks that line, and without this the play head stayed
  // at the chunk start, i.e. a paragraph before the marking. Only the panel can tell us: the
  // pick needs the cues, which are loaded down there. Tied to the nonce so one jump's refined
  // time can never be applied to the next one.
  const [focus, setFocus] = useState<{ nonce?: number; time: number } | null>(null);
  const onCitationFocusTime = useCallback((time: number, nonce?: number) => {
    // Bail out on an unchanged value: the panel re-reports on every re-render of its pin
    // effect, and a fresh object each time would re-run the seek effect below forever.
    setFocus((prev) => (prev && prev.nonce === nonce && prev.time === time ? prev : { nonce, time }));
  }, []);
  const seekTarget = source.isCitation && focus && focus.nonce === source.nonce
    ? focus.time
    : source.startTime;

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
    // `seekTarget` rather than `source.startTime`: the refined time arrives one render after
    // the jump (the panel has to read its cues first), and this has to run again for it.
  }, [seekTarget, source.nonce, source.uuid]);

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
          // Keine <track>-Spuren und kein Herunterladen: das Menü des Players zeigt weder
          // "Untertitel" noch "Herunterladen". Gelesen wird das Transkript unten im Panel.
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
        mediaRef={mediaRef}
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
