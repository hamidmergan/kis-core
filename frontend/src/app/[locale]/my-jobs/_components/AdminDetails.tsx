"use client";

import { useState } from "react";
import { CaretRight } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import { formatElapsed } from "@/lib/format";
import { gesamtdauerS, phasenzeilen, wertText, type JobStats } from "./adminStats";


export function AdminDetails({ stats }: { stats: JobStats }) {
  const [offen, setOffen] = useState(false);
  const locale = useLocale();
  const t = useTranslations("myJobs.adminStats");
  const td = useTranslations("myJobs.duration");
  // The same names as in the AI panel so the route is recognisable there.
  const tr = useTranslations("admin.providers.featureName");
  const [zeilen, gesamt] = [phasenzeilen(stats), gesamtdauerS(stats)];

  if (zeilen.length === 0) return null;

  const dauer = (sekunden: number) => formatElapsed(sekunden * 1000, {
    seconds: (n) => td("seconds", { n }),
    minutes: (m, s) => td("minutes", { m, s }),
    hours: (h, m, s) => td("hours", { h, m, s }),
  });
  const woerter = { ja: t("yes"), nein: t("no") };
  const beschriftung = (bereich: string, schluessel: string) => {
    const pfad = `${bereich}.${schluessel}`;
    return t.has(pfad) ? t(pfad) : schluessel;
  };
  const feldwert = (schluessel: string, wert: string | number | boolean) =>
    schluessel === "route" && typeof wert === "string" && tr.has(wert)
      ? tr(wert)
      : wertText(schluessel, wert, locale, woerter);

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOffen((v) => !v)}
        aria-expanded={offen}
        className="flex items-center gap-1 text-xs text-muted-soft hover:text-muted transition-colors"
      >
        <CaretRight
          size={10}
          weight="bold"
          className={`transition-transform ${offen ? "rotate-90" : ""}`}
        />
        {t("toggle")}
        {gesamt !== null && <span className="text-border">· {dauer(gesamt)}</span>}
      </button>
      {offen && (
        <dl className="mt-1.5 space-y-1 border-l border-border-soft pl-3 text-xs">
          {zeilen.map((zeile) => (
            <div key={zeile.phase}>
              <dt className="text-muted">
                {beschriftung("phase", zeile.phase)}
                {zeile.dauerS !== null && (
                  <span className="ml-2 text-muted-soft">{dauer(zeile.dauerS)}</span>
                )}
              </dt>
              <dd className="flex flex-wrap gap-x-3 text-muted-soft">
                {zeile.felder.map((feld) => (
                  <span key={feld.schluessel} className="whitespace-nowrap">
                    {beschriftung("field", feld.schluessel)}{" "}
                    <span className="text-muted">
                      {feldwert(feld.schluessel, feld.wert)}
                    </span>
                  </span>
                ))}
              </dd>
              {zeile.fehler && (
                <dd className="text-error">{t("error")} {zeile.fehler}</dd>
              )}
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
