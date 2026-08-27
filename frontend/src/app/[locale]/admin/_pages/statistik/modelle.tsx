"use client";

/** Requests and tokens per model, the numbers come from the provider itself. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Kachel, Karte, Saeulen, Ladeanzeige } from "./_bausteine";

interface Daten {
  totals: { requests: number; tokens_in: number; tokens_out: number };
  per_month: { month: string; requests: number }[];
  per_model: { model: string; provider: string; requests: number; tokens: number }[];
  endpoints: { endpoint: string; requests: number }[];
}

const mio = (n: number) =>
  n >= 1_000_000
    ? `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio.`
    : n.toLocaleString("de-DE");

export default function StatistikModellePage() {
  const t = useTranslations("admin.statistik");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);

  useEffect(() => {
    fetch("/api/admin/stats/models", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDaten)
      .catch(() => setFehler(true));
  }, []);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;

  // While only one endpoint records, the gap deserves to be stated.
  const nurChat = daten.endpoints.length === 1 && daten.endpoints[0]?.endpoint === "chat";
  const anteilRaus =
    daten.totals.tokens_in > 0
      ? Math.round((daten.totals.tokens_out / (daten.totals.tokens_in + daten.totals.tokens_out)) * 1000) / 10
      : 0;

  return (
    <div className="space-y-4">
      {nurChat && (
        <p className="text-xs text-muted border border-border-soft rounded-lg bg-surface px-4 py-3">
          {t("models.onlyChat")}
        </p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Kachel titel={t("models.requests")} wert={daten.totals.requests} />
        <Kachel titel={t("models.tokensIn")} wert={mio(daten.totals.tokens_in)} />
        <Kachel
          titel={t("models.tokensOut")}
          wert={mio(daten.totals.tokens_out)}
          fuss={t("models.tokensOutFoot", { p: anteilRaus })}
        />
      </div>

      <Karte titel={t("models.perMonth")}>
        <Saeulen werte={daten.per_month.map((m) => ({ label: m.month, wert: m.requests }))} />
      </Karte>

      <Karte titel={t("models.all")}>
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-soft text-left text-2xs text-muted uppercase">
                <th className="py-2 pr-4">{t("models.colModel")}</th>
                <th className="py-2 pr-4">{t("models.colProvider")}</th>
                <th className="py-2 pr-4 text-right">{t("models.colRequests")}</th>
                <th className="py-2 text-right">{t("models.colTokens")}</th>
              </tr>
            </thead>
            <tbody>
              {daten.per_model.map((m) => (
                <tr key={`${m.provider}-${m.model}`} className="border-b border-border-soft last:border-0">
                  <td className="py-2 pr-4 text-foreground-soft">{m.model}</td>
                  <td className="py-2 pr-4 text-muted">{m.provider}</td>
                  <td className="py-2 pr-4 text-right tabular-nums">
                    {m.requests.toLocaleString("de-DE")}
                  </td>
                  <td className="py-2 text-right tabular-nums text-muted">
                    {mio(m.tokens)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Karte>
    </div>
  );
}
