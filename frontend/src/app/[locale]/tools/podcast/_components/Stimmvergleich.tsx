"use client";

import { useTranslations } from "next-intl";
import { stimmprobeUrl, type Stimmprobe } from "../_api";

// The excerpt voiced by the platform's own service, the same voices as the podcast above.
const EIGENE = "mylab";

/** The start of the demo script voiced by other services, side by side with the platform's own voices. */
export default function Stimmvergleich({ proben }: { proben: Stimmprobe[] }) {
  const t = useTranslations("tools.podcastDemo");
  if (!proben.length) return null;

  return (
    <section className="mt-4 border-t border-border pt-8">
      <h3 className="text-base font-semibold mb-1">{t("vergleichTitel")}</h3>
      <p className="text-sm text-muted mb-5">{t("vergleichText")}</p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {proben.map((p) => (
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
