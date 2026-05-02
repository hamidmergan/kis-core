import React, { useEffect, useRef, useState } from "react";
import { CaretLeft, SidebarSimple, SpeakerHigh } from "@phosphor-icons/react";
import type { ViewerState } from "../../_types";
import type { AddNoteExtras } from "../../_hooks/useNotes";
import { FileIcon } from "../sources/FileIcon";
import { TranscriptPanel } from "./TranscriptPanel";

export function MediaPlayer({
  source, onClose, workspaceUuid, onMinimize, canDownload = false, canManage = false, onSaveNote,
}: {
  source: ViewerState;
  onClose: () => void;
  workspaceUuid: string;
  onMinimize?: () => void;
  canDownload?: boolean;
  canManage?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[], extras?: AddNoteExtras) => void | Promise<void>;
}) {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const mediaUrl = `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/file`;
  const transcriptUrl = (lang: "de" | "en") =>
    `/api/ai-assistant/workspaces/${workspaceUuid}/sources/${source.uuid}/transcript?lang=${lang}`;

  // Detect which VTT languages exist so we only attach available <track> elements.
  const [availableLangs, setAvailableLangs] = useState<("de" | "en")[]>([]);
  useEffect(() => {
    let cancelled = false;
    const check = async (lang: "de" | "en") => {
      try {
        const res = await fetch(transcriptUrl(lang), { credentials: "include" });
        return res.ok ? lang : null;
      } catch {
        return null;
      }
    };
    Promise.all([check("de"), check("en")]).then((results) => {
      if (cancelled) return;
      setAvailableLangs(results.filter((l): l is "de" | "en" => l !== null));
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceUuid, source.uuid]);

  // Seek to timestamp when source changes
  useEffect(() => {
    if (source.startTime !== undefined && mediaRef.current) {
      mediaRef.current.currentTime = source.startTime;
      mediaRef.current.play().catch(() => { });
    }
  }, [source.startTime, source.nonce]);

  return (
    <div className="flex flex-col h-full viewer-short">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 flex-shrink-0"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <button type="button" onClick={onClose}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon"
          style={{ backgroundColor: "var(--surface-dim)" }} title="Zurück">
          <CaretLeft size={13} weight="bold" />
        </button>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--foreground)" }}>{source.filename}</span>
        {onMinimize && (
          <button type="button" onClick={onMinimize}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full btn-icon ml-2"
            style={{ backgroundColor: "var(--surface-dim)" }} title="Panel minimieren">
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
                label={lang === "de" ? "Deutsch" : "English"}
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
      />
    </div>
  );
}
