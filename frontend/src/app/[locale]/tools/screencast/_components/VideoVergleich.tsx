"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import { usePermissions } from "@/hooks/usePermissions";
import { hasPerm, PERM } from "@/lib/permissions";
import { langLabel } from "@/app/[locale]/workspace/[uuid]/_types";

export interface DemoStimme {
  id: string;
  anbieter: string;
  eigen: boolean;
  stimmen: Record<string, string>;
  kennungen: Record<string, string>;
  videos: string[];
}

const vergleichUrl = (sprache: string, id: string) => `/api/screencast-demo/vergleich/${sprache}/${id}`;

/** A shorter version of the demo voiced by every service, one player with a tab per service and per language. */
export default function VideoVergleich({ stimmen, sprache }: { stimmen: DemoStimme[]; sprache: string }) {
  const t = useTranslations("tools.screencastDemo");
  const tScreencast = useTranslations("tools.screencast");
  const locale = useLocale();
  const { loaded, permissions } = usePermissions();
  const sprachen = [...new Set(stimmen.flatMap((s) => Object.keys(s.stimmen)))];
  const [gewaehlteSprache, setGewaehlteSprache] = useState<string | null>(null);
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stand = useRef<{ zeit: number; laeuft: boolean } | null>(null);

  const aktiveSprache = gewaehlteSprache ?? (sprachen.includes(sprache) ? sprache : sprachen[0]);
  const aktiv = stimmen.find((s) => s.id === gewaehlt) ?? stimmen[0];
  const quelle = aktiv?.videos.includes(aktiveSprache) ? vergleichUrl(aktiveSprache, aktiv.id) : null;

  // Another service starts where the last one stopped, so the voices compare on the same sentence.
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

  const merken = () => {
    const video = videoRef.current;
    if (video) stand.current = { zeit: video.currentTime, laeuft: !video.paused && !video.ended };
  };

  if (!aktiv) return null;
  const name = aktiv.stimmen[aktiveSprache];

  return (
    <section className="mt-4 border-t border-border pt-8">
      <h3 className="text-base font-semibold mb-1">{t("vergleichTitel")}</h3>
      <p className="text-sm text-muted mb-5">{t("vergleichText")}</p>
      {/* Only those allowed to connect their own account get pointed there. */}
      {loaded && hasPerm(permissions, PERM.interfaces) && (
        <p className="text-sm text-muted -mt-3 mb-5">
          {t.rich("anbinden", {
            link: (teil) => (
              <a href="/interfaces" target="_blank" rel="noopener noreferrer" className="font-bold text-kb underline underline-offset-2">
                {teil}
              </a>
            ),
          })}
        </p>
      )}
      {sprachen.length > 1 && (
        <Tabs
          className="mb-4"
          items={sprachen.map((s) => ({ key: s, label: langLabel(s, locale) }))}
          active={aktiveSprache}
          onChange={(s) => { merken(); setGewaehlteSprache(s); }}
        />
      )}
      <div className="overflow-x-auto">
        <Tabs items={stimmen.map((s) => ({ key: s.id, label: s.anbieter }))} active={aktiv.id} onChange={(id) => { merken(); setGewaehlt(id); }} />
      </div>
      <p className="mt-3 mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-foreground-soft">
        {name && <span>{t("stimme", { name })}</span>}
        {aktiv.eigen && (
          <span className="rounded-full bg-kb20 px-2.5 py-0.5 text-xs font-medium text-kb-dark">{t("selbstGehostet")}</span>
        )}
      </p>
      <div className="rounded-lg overflow-hidden border border-border-soft">
        {quelle ? (
          <video ref={videoRef} src={quelle} controls preload="metadata" className="w-full">
            {tScreencast("done.browserNoVideo")}
          </video>
        ) : (
          <div className="aspect-video flex items-center justify-center bg-surface-dim px-6 text-center text-sm text-muted">
            {t("platzhalter", { anbieter: aktiv.anbieter })}
          </div>
        )}
      </div>
    </section>
  );
}
