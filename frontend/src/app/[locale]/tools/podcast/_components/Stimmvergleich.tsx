"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import DienstKarten from "@/components/tools/DienstKarten";
import { useStelleBehalten } from "@/hooks/useStelleBehalten";
import { usePermissions } from "@/hooks/usePermissions";
import { hasPerm, PERM } from "@/lib/permissions";
import { langLabel } from "@/app/[locale]/workspace/[uuid]/_types";
import { stimmprobeUrl, type Stimmprobe } from "../_api";

/** The start of the demo script voiced by several services, one player, a tab per language and a card per service. */
export default function Stimmvergleich({ proben }: { proben: Stimmprobe[] }) {
  const t = useTranslations("tools.podcastDemo");
  const locale = useLocale();
  const { loaded, permissions } = usePermissions();
  const sprachen = [...new Set(proben.map((p) => p.sprache))];
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const [gewaehlteProbe, setGewaehlteProbe] = useState<string | null>(null);
  const aktiv = gewaehlt ?? (sprachen.includes(locale) ? locale : sprachen[0]);
  const hier = proben.filter((p) => p.sprache === aktiv);
  // The same service stays chosen across languages, the ids only differ by their language ending.
  const dienst = (p: Stimmprobe) => p.id.replace(/-[a-z]{2}$/, "");
  const probe = hier.find((p) => dienst(p) === gewaehlteProbe) ?? hier[0];
  const quelle = probe?.ton ? stimmprobeUrl(probe.id) : null;
  const { ref: tonRef, merken } = useStelleBehalten<HTMLAudioElement>(quelle);
  if (!probe) return null;

  return (
    <section className="mt-4 border-t border-border pt-8">
      <h3 className="text-base font-semibold mb-1">{t("vergleichTitel")}</h3>
      <p className="text-sm text-muted mb-5">{t("vergleichText")}</p>
      {/* Only those allowed to connect their own account get pointed there. */}
      {loaded && hasPerm(permissions, PERM.interfaces) && (
        <p className="text-sm text-muted -mt-3 mb-5">
          {t.rich("vergleichAnbinden", {
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
          active={aktiv}
          onChange={(s) => { merken(); setGewaehlt(s); }}
        />
      )}
      <DienstKarten
        karten={hier.map((p) => ({
          id: dienst(p),
          anbieter: p.anbieter,
          stimme: t("vergleichStimmen", { stimmen: p.stimmen.join(", ") }),
          selbst: p.selbst ? t("vergleichSelbst") : "",
        }))}
        aktiv={dienst(probe)}
        onWahl={(id) => { merken(); setGewaehlteProbe(id); }}
        ariaLabel={t("vergleichTitel")}
      />
      {quelle ? (
        <audio ref={tonRef} controls preload="metadata" className="mx-auto block w-full max-w-md" src={quelle} />
      ) : (
        <p className="mx-auto flex h-[54px] w-full max-w-md items-center justify-center rounded-full bg-surface-dim text-sm text-muted">
          {t("vergleichFolgt")}
        </p>
      )}
    </section>
  );
}
