"use client";

/** Who is here and who stays, based on presence. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CaretRight } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import { AnteilsZeile, Balken, Kachel, Karte, Kurve, Saeulen, Ladeanzeige } from "./_bausteine";
import { NochNichts, Suche } from "./_suche";
import { PersonAnsicht } from "./_person";
import { BucketAnsicht, type Bucket } from "./_bucket";

interface OnlineNutzer { id: number; name: string }
interface Person { id: number; name: string; role: string }
interface Daten {
  online: { count: number; users: OnlineNutzer[] };
  people: Person[];
  totals: { total: number; active_30d: number; new_this_month: number };
  per_day: { day: string; users: number }[];
  new_per_month: { month: string; users: number }[];
  retention: { regular: number; occasional: number; once: number; threshold_days: number };
  roles: { role: string; users: number }[];
}

/** How many names are visible while the list is collapsed. */
const KURZ = 5;

export default function StatistikNutzerPage() {
  const t = useTranslations("admin.statistik");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [offen, setOffen] = useState(false);
  const [person, setPerson] = useState<number | null>(null);
  const [bucket, setBucket] = useState<Bucket | null>(null);

  useEffect(() => {
    fetch("/api/admin/stats/users", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDaten)
      .catch(() => setFehler(true));
  }, []);

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;
  if (!daten) return <Ladeanzeige />;

  const sichtbar = offen ? daten.online.users : daten.online.users.slice(0, KURZ);
  const rest = daten.online.users.length - KURZ;
  const b = daten.retention;

  // Accumulated from the new arrivals, a separate query would be the same number.
  let lauf = 0;
  const summiert = daten.new_per_month.map((m) => ({
    label: m.month,
    wert: (lauf += m.users),
  }));

  return (
    <div className="space-y-4">
      <Karte titel={t("users.onlineNow")} hinweis={t("users.onlineHint")} marke={t("users.now")}>
        <p className="text-4xl font-bold tabular-nums tracking-tight mt-2">{daten.online.count}</p>
        {daten.online.users.length === 0 ? (
          <p className="text-xs text-muted-soft mt-3">{t("users.nobodyOnline")}</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border-soft text-left text-2xs uppercase text-muted">
                  <th className="py-2 pr-4">{t("detail.colName")}</th>
                </tr>
              </thead>
              <tbody>
                {sichtbar.map((n) => (
                  <tr key={n.id} className="border-b border-border-soft">
                    <td className="py-2 pr-4 text-foreground-soft">{n.name}</td>
                  </tr>
                ))}
                {rest > 0 && (
                  <tr>
                    <td className="p-0">
                      <button
                        type="button"
                        onClick={() => setOffen(!offen)}
                        aria-expanded={offen}
                        className="flex w-full items-center gap-2 py-2 text-xs text-muted transition-colors hover:text-kb"
                      >
                        <CaretRight size={10} weight="bold" className={offen ? "rotate-90" : ""} />
                        {offen ? t("users.showLess") : t("users.showMore", { n: rest })}
                      </button>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Karte>

      <Karte titel={t("users.perDay")} hinweis={t("users.perDayHint")}>
        <Saeulen
          werte={daten.per_day.map((d) => ({ label: d.day.slice(5), wert: d.users }))}
          aufKlick={(i) => setBucket({ art: "day", day: daten.per_day[i].day })}
        />
      </Karte>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Kachel titel={t("users.total")} wert={daten.totals.total} />
        <Kachel titel={t("users.active")} wert={daten.totals.active_30d} fuss={t("users.activeFoot")} />
        <Kachel titel={t("users.newThisMonth")} wert={daten.totals.new_this_month} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Karte titel={t("users.total")} hinweis={t("users.cumulativeHint")}>
          <Kurve werte={summiert} />
        </Karte>
        <Karte titel={t("users.newPerMonth")}>
          <Saeulen
            werte={daten.new_per_month.map((m) => ({ label: m.month, wert: m.users }))}
            aufKlick={(i) => setBucket({ art: "month", month: daten.new_per_month[i].month })}
          />
        </Karte>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Karte titel={t("users.retention")} hinweis={t("users.retentionHint")}>
          <AnteilsZeile
            teile={[
              { label: t("users.regular", { n: b.threshold_days }), wert: b.regular },
              { label: t("users.occasional", { n: b.threshold_days }), wert: b.occasional },
              { label: t("users.once"), wert: b.once },
            ]}
            farben={["bg-kb", "bg-kb/55", "bg-kb/25"]}
          />
        </Karte>
        <Karte titel={t("users.roles")}>
          <Balken zeilen={daten.roles.map((r) => ({ label: r.role, wert: r.users }))} labelBreite={140} />
        </Karte>
      </div>

      <Karte titel={t("detail.searchPerson")} hinweis={t("detail.searchPersonHint")}>
        <Suche
          eintraege={daten.people.map((p) => ({ id: String(p.id), titel: p.name, zusatz: p.role }))}
          platzhalter={t("detail.searchPersonPlaceholder")}
          gewaehlt={person === null ? null : String(person)}
          waehlen={(id) => setPerson(Number(id))}
          nichtsGefunden={t("assistant.nothingFound")}
          leeren={t("detail.searchPersonClear")}
        />
      </Karte>

      {person === null ? <NochNichts text={t("detail.pickPerson")} /> : <PersonAnsicht id={person} />}

      <Modal
        open={bucket !== null}
        onClose={() => setBucket(null)}
        title={
          bucket?.art === "day"
            ? t("users.bucketDay", { day: new Date(bucket.day).toLocaleDateString("de-DE") })
            : bucket?.art === "month"
              ? t("users.bucketMonth", { month: bucket.month })
              : undefined
        }
      >
        {bucket !== null && <BucketAnsicht bucket={bucket} />}
      </Modal>
    </div>
  );
}
