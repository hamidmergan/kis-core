"use client";

import { useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import Tabs from "@/components/ui/Tabs";
import { langLabel } from "@/app/[locale]/workspace/[uuid]/_types";
import { stimmprobeUrl, type Stimmprobe } from "../_api";

// The excerpt voiced by the platform's own service, the same voices as the podcast above.
const EIGENE = "mylab";

/** The start of the demo script voiced by other services, side by side with the platform's own voices, one tab per language. */
export default function Stimmvergleich({ proben }: { proben: Stimmprobe[] }) {
  const t = useTranslations("tools.podcastDemo");
  const locale = useLocale();
  const sprachen = [...new Set(proben.map((p) => p.sprache))];
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  if (!proben.length) return null;
  const aktiv = gewaehlt ?? (sprachen.includes(locale) ? locale : sprachen[0]);

  return (
    <section className="mt-4 border-t border-border pt-8">
      <h3 className="text-base font-semibold mb-1">{t("vergleichTitel")}</h3>
      <p className="text-sm text-muted mb-5">{t("vergleichText")}</p>
      {sprachen.length > 1 && (
        <Tabs
          className="mb-4"
          items={sprachen.map((s) => ({ key: s, label: langLabel(s, locale) }))}
          active={aktiv}
          onChange={setGewaehlt}
        />
      )}
      <ul className="grid gap-3 sm:grid-cols-2">
        {proben.filter((p) => p.sprache === aktiv).map((p) => (
          <li key={p.id} className="rounded-lg border border-border p-3">
            <p className="text-sm font-semibold">
              {p.anbieter}
              {p.id === EIGENE && <span className="ml-2 text-xs font-normal text-muted">{t("vergleichHier")}</span>}
            </p>
            <p className="text-xs text-muted mb-2">{t("vergleichStimmen", { stimmen: p.stimmen.join(", ") })}</p>
            <audio controls preload="none" className="w-full" src={stimmprobeUrl(p.id)} />
          </li>
        ))}
      </ul>
    </section>
  );
}
