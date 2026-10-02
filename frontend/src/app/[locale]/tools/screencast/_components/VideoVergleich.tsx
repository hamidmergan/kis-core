"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import DienstKarten from "@/components/tools/DienstKarten";
import { useStelleBehalten } from "@/hooks/useStelleBehalten";
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

/** A shorter version of the demo voiced by every service, one player, a tab per language and a card per service. */
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
  const aktiveSprache = gewaehlteSprache ?? (sprachen.includes(sprache) ? sprache : sprachen[0]);
  const dienste = stimmen.filter((s) => s.vergleich.includes(aktiveSprache));
  const aktiv = dienste.find((s) => s.id === gewaehlt) ?? dienste[0];
  const quelle = aktiv?.videos.includes(aktiveSprache) ? vergleichUrl(aktiveSprache, aktiv.id) : null;

  const { ref: videoRef, merken } = useStelleBehalten<HTMLVideoElement>(quelle);

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
      <DienstKarten
        karten={dienste.map((s) => ({
          id: s.id,
          anbieter: s.anbieter,
          stimme: s.stimmen[aktiveSprache] ? t("stimme", { name: s.stimmen[aktiveSprache] }) : "",
          selbst: s.eigen ? t("selbstGehostet") : "",
        }))}
        aktiv={aktiv.id}
        onWahl={(id) => { merken(); setGewaehlt(id); }}
        ariaLabel={t("vergleichTitel")}
      />
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
