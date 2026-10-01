"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import { usePermissions } from "@/hooks/usePermissions";
import { hasPerm, PERM } from "@/lib/permissions";

export interface DemoStimme {
  id: string;
  anbieter: string;
  eigen: boolean;
  stimmen: Record<string, string>;
  kennungen: Record<string, string>;
  videos: string[];
}

/** One player for the demo video, one tab per voice service; switching keeps the playback position. */
export default function StimmenVideo({
  stimmen,
  sprache,
  aktiv,
  onAktiv,
  videoUrl,
}: {
  stimmen: DemoStimme[];
  sprache: string;
  aktiv: string;
  onAktiv: (id: string) => void;
  videoUrl: (id: string) => string;
}) {
  const t = useTranslations("tools.screencastDemo");
  const tScreencast = useTranslations("tools.screencast");
  const { loaded, permissions } = usePermissions();
  const videoRef = useRef<HTMLVideoElement>(null);
  const stand = useRef<{ zeit: number; laeuft: boolean } | null>(null);
  const gewaehlt = stimmen.find((s) => s.id === aktiv) ?? stimmen[0];
  const hatVideo = !!gewaehlt?.videos.includes(sprache);
  const quelle = hatVideo ? videoUrl(gewaehlt.id) : null;

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !quelle || !stand.current) return;
    const { zeit, laeuft } = stand.current;
    stand.current = null;
    const weiter = () => {
      video.currentTime = Math.min(zeit, video.duration || zeit);
      if (laeuft) video.play().catch(() => {});
    };
    if (video.readyState >= 1) weiter();
    else video.addEventListener("loadedmetadata", weiter, { once: true });
    return () => video.removeEventListener("loadedmetadata", weiter);
  }, [quelle]);

  const wechseln = (id: string) => {
    const video = videoRef.current;
    if (video) stand.current = { zeit: video.currentTime, laeuft: !video.paused && !video.ended };
    onAktiv(id);
  };

  if (!gewaehlt) return null;
  const name = gewaehlt.stimmen[sprache];

  return (
    <div className="mb-6">
      <p className="text-sm text-muted mb-3 text-center">{t("stimmenHinweis")}</p>
      <div className="overflow-x-auto">
        <Tabs items={stimmen.map((s) => ({ key: s.id, label: s.anbieter }))} active={gewaehlt.id} onChange={wechseln} />
      </div>
      <p className="mt-3 mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-foreground-soft">
        {name && <span>{t("stimme", { name })}</span>}
        {gewaehlt.eigen && (
          <span className="rounded-full bg-kb20 px-2.5 py-0.5 text-xs font-medium text-kb-dark">{t("selbstGehostet")}</span>
        )}
      </p>
      <div className="rounded-lg overflow-hidden border border-border-soft">
        {quelle ? (
          <video ref={videoRef} src={quelle} controls className="w-full">
            {tScreencast("done.browserNoVideo")}
          </video>
        ) : (
          <div className="aspect-video flex items-center justify-center bg-surface-dim px-6 text-center text-sm text-muted">
            {t("platzhalter", { anbieter: gewaehlt.anbieter })}
          </div>
        )}
      </div>
      {/* Only those allowed to connect their own account get pointed there. */}
      {!gewaehlt.eigen && loaded && hasPerm(permissions, PERM.interfaces) && (
        <p className="mt-3 text-sm text-muted">
          {t.rich("anbinden", {
            link: (teil) => (
              <a href="/interfaces" target="_blank" rel="noopener noreferrer" className="font-bold text-kb underline underline-offset-2">
                {teil}
              </a>
            ),
          })}
        </p>
      )}
    </div>
  );
}
