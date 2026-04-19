import React, { useEffect, useRef, useState } from "react";
import { CaretLeft, SidebarSimple, SpeakerHigh } from "@phosphor-icons/react";
import type { ViewerState } from "../_types";
import { FileIcon } from "./FileIcon";
import { TranscriptPanel } from "./TranscriptPanel";

export function MediaPlayer({
  source, onClose, moduleUuid, onMinimize, canDownload = false, onSaveNote,
}: {
  source: ViewerState;
  onClose: () => void;
  moduleUuid: string;
  onMinimize?: () => void;
  canDownload?: boolean;
  onSaveNote?: (content: string, sourceUuids?: string[]) => void | Promise<void>;
}) {
  const mediaRef = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const ext = source.filename.slice(source.filename.lastIndexOf(".")).toLowerCase();
  const isVideo = [".mp4", ".webm"].includes(ext);
  const mediaUrl = `/api/ki-assistent/modules/${moduleUuid}/sources/${source.uuid}/file`;
  const transcriptUrl = (lang: "de" | "en") =>
    `/api/ki-assistent/modules/${moduleUuid}/sources/${source.uuid}/transcript?lang=${lang}`;

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
  }, [moduleUuid, source.uuid]);

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
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }} title="Zurück">
          <CaretLeft size={13} weight="bold" color="var(--muted)" />
        </button>
        <FileIcon filename={source.filename} />
        <span className="flex-1 text-sm font-medium truncate min-w-0" style={{ color: "var(--text)" }}>{source.filename}</span>
        {onMinimize && (
          <button type="button" onClick={onMinimize}
            className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity ml-2"
            style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }} title="Panel minimieren">
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
        moduleUuid={moduleUuid}
        sourceUuid={source.uuid}
        onSaveNote={onSaveNote}
      />
    </div>
  );
}
