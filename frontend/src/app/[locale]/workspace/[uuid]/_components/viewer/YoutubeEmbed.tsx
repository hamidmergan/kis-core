"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { YoutubeLogo } from "@phosphor-icons/react";
import { loadYoutubeIframeApi, type YTPlayer } from "@/lib/youtubeIframeApi";
import type { MediaController } from "./mediaController";

const TICK_MS = 250;
const NOCOOKIE_HOST = "https://www.youtube-nocookie.com";

/** The player as a controller, polling because the IFrame API has no time event. */
function youtubeController(player: YTPlayer): MediaController {
  return {
    currentTime: () => player.getCurrentTime(),
    seek: (seconds) => player.seekTo(seconds, true),
    play: () => player.playVideo(),
    onTime: (listener) => {
      let last = -1;
      const timer = window.setInterval(() => {
        const now = player.getCurrentTime();
        if (now !== last) {
          last = now;
          listener();
        }
      }, TICK_MS);
      return () => window.clearInterval(timer);
    },
  };
}

export function YoutubeEmbed({
  videoId, title, consent, onConsent, seekTarget, seekNonce, onController,
}: {
  videoId: string;
  title: string;
  consent: boolean;
  onConsent: () => void;
  seekTarget?: number;
  seekNonce?: number;
  onController: (controller: MediaController | null) => void;
}) {
  const t = useTranslations("workspace.detail.viewer");
  const locale = useLocale();
  const hostRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const [ready, setReady] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  // Builds the player once the person agreed and tears it down with the source.
  useEffect(() => {
    const host = hostRef.current;
    if (!consent || !host) return;
    let cancelled = false;
    setLoadFailed(false);
    const mount = document.createElement("div");
    host.appendChild(mount);
    loadYoutubeIframeApi()
      .then((YT) => {
        if (cancelled) return;
        playerRef.current = new YT.Player(mount, {
          host: NOCOOKIE_HOST,
          videoId,
          width: "100%",
          height: "100%",
          playerVars: { rel: 0, playsinline: 1, origin: window.location.origin },
          events: {
            onReady: (event) => {
              if (cancelled) return;
              onController(youtubeController(event.target));
              setReady(true);
            },
          },
        });
      })
      .catch(() => {
        if (cancelled) return;
        setLoadFailed(true);
      });
    return () => {
      cancelled = true;
      setReady(false);
      onController(null);
      playerRef.current?.destroy();
      playerRef.current = null;
      mount.remove();
    };
  }, [consent, videoId, onController]);

  // A chip or a block click lands here, the player has to be ready for it.
  useEffect(() => {
    const player = playerRef.current;
    if (!ready || !player || seekTarget === undefined) return;
    player.seekTo(seekTarget, true);
    player.playVideo();
  }, [ready, seekTarget, seekNonce]);

  if (!consent) {
    return (
      <div
        className="w-full rounded-lg flex flex-col items-center justify-center gap-3 p-6 text-center"
        style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", aspectRatio: "16 / 9", maxHeight: "100%" }}
        data-testid="youtube-consent"
      >
        <YoutubeLogo size={40} weight="fill" style={{ color: "var(--error-strong)" }} />
        <span className="text-sm font-medium truncate max-w-full">{title}</span>
        <p className="text-xs max-w-md" style={{ color: "var(--muted)" }}>{t("youtubeConsentText")}</p>
        <button
          type="button"
          onClick={onConsent}
          data-testid="youtube-consent-button"
          className="btn-primary px-4 py-2 rounded-lg text-sm font-medium"
        >
          {t("youtubeConsentButton")}
        </button>
        <a
          href={`/${locale}/privacy`}
          target="_blank"
          rel="noreferrer"
          className="text-xs underline"
          style={{ color: "var(--muted)" }}
        >
          {t("youtubeConsentPrivacy")}
        </a>
      </div>
    );
  }

  return (
    <div
      ref={hostRef}
      className={`w-full rounded-lg overflow-hidden${loadFailed ? " flex items-center justify-center" : ""}`}
      style={{ backgroundColor: "#000", aspectRatio: "16 / 9", maxHeight: "100%" }}
      data-testid="youtube-player"
    >
      {loadFailed && <p className="text-sm" style={{ color: "var(--muted)" }}>{t("youtubeLoadFailed")}</p>}
    </div>
  );
}
