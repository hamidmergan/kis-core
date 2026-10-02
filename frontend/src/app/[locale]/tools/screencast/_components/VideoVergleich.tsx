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
  /** The languages whose comparison shows this service. */
  vergleich: string[];
  videos: string[];
}

const vergleichUrl = (sprache: string, id: string) => `/api/screencast-demo/vergleich/${sprache}/${id}`;

/** A shorter version of the demo voiced by every service, one player with a tab per service and per language. */
export default function VideoVergleich({ stimmen, sprache }: { stimmen: DemoStimme[]; sprache: string }) {
  const t = useTranslations("tools.screencastDemo");
  const tScreencast = useTranslations("tools.screencast");
  const locale = useLocale();
  const { loaded, permissions } = usePermissions();
  // The order of the voice names, not of the first service, which may sit out a language.
  const sprachen = [...new Set(stimmen.flatMap((s) => Object.keys(s.stimmen)))]
    .filter((sp) => stimmen.some((s) => s.vergleich.includes(sp)));
  const [gewaehlteSprache, setGewaehlteSprache] = useState<string | null>(null);
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stand = useRef<{ zeit: number; laeuft: boolean } | null>(null);

  const aktiveSprache = gewaehlteSprache ?? (sprachen.includes(sprache) ? sprache : sprachen[0]);
  const dienste = stimmen.filter((s) => s.vergleich.includes(aktiveSprache));
  const aktiv = dienste.find((s) => s.id === gewaehlt) ?? dienste[0];
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
      {/* The language stays a tab, the services are cards that also name the voice. */}
      <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" role="radiogroup" aria-label={t("vergleichTitel")}>
        {dienste.map((s) => {
          const gewaehltHier = s.id === aktiv.id;
          return (
            <button
              key={s.id}
              type="button"
              role="radio"
              aria-checked={gewaehltHier}
              onClick={() => { merken(); setGewaehlt(s.id); }}
              className={`flex flex-col items-start justify-start text-left rounded-lg border-2 transition-colors px-3 py-2 ${gewaehltHier ? "border-kb" : "border-border hover:border-kb"}`}
            >
              <p className={`text-sm font-semibold ${gewaehltHier ? "text-kb" : "text-foreground"}`}>{s.anbieter}</p>
              {s.stimmen[aktiveSprache] && (
                <p className="text-xs text-muted">{t("stimme", { name: s.stimmen[aktiveSprache] })}</p>
              )}
              {s.eigen && <p className="mt-1 text-xs text-kb-dark">{t("selbstGehostet")}</p>}
            </button>
          );
        })}
      </div>
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
