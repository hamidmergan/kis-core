"use client";

/**
 * Auslastung: was die Maschine hergibt und wie voll sie gerade ist.
 *
 * Steht an der Stelle, an der vorher fünf Zahlenfelder unter Einstellungen
 * standen. Die fragten nach einer Zahl, die niemand wissen konnte, und gaben
 * danach keine Rückmeldung, ob sie stimmte. Diese Karte fragt nichts und zeigt
 * alles.
 *
 * Bewusst im Aufträge-Bereich: hierher schaut man, wenn jemand meldet, dass es
 * hängt, und dann will man die Auftragsliste direkt darunter haben.
 */

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

type LoadData = {
  machine: {
    cores: number;
    cores_source: string;
    memory_gb: number;
    memory_source: string;
    max_concurrent_uploads: number;
    render_workers: number;
  };
  cpu_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number;
  jobs: { total: number; running: number; queued: number };
  uploads: { total: number; running: number | null };
};

// Auffrischung alle fünf Sekunden. Schnell genug, um beim Zuschauen eine
// Bewegung zu sehen, langsam genug, um die Datenbank nicht zu belästigen.
const REFRESH_MS = 5000;

/** Ein Balken mit Beschriftung. Ab 80 Prozent warnfarben, weil dann die
 *  Wartezeiten anfangen und genau das die Frage ist, mit der man herkommt. */
function Meter({ label, value, max, text }: {
  label: string;
  value: number | null;
  max: number;
  text: string;
}) {
  const pct = value === null || max <= 0 ? 0 : Math.min(100, (value / max) * 100);
  const tight = pct >= 80;
  return (
    <div className="flex items-center gap-3">
      <span className="w-32 shrink-0 text-xs text-muted">{label}</span>
      {/* Die Spur bewusst blass: mit einem kräftigen Grundton sieht ein leerer
          Balken aus wie ein voller, und genau das soll die Karte ja beantworten. */}
      <div className="h-2 flex-1 rounded-full bg-border-soft overflow-hidden">
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${tight ? "bg-warn" : "bg-kb"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-44 shrink-0 text-right text-xs text-foreground-soft tabular-nums">
        {text}
      </span>
    </div>
  );
}

export default function SystemLoadCard() {
  const t = useTranslations("admin.load");
  const locale = useLocale();
  const [data, setData] = useState<LoadData | null>(null);

  // Auf Deutsch heißt es 7,8 GB und nicht 7.8 GB. toFixed kennt keine Sprache.
  const num = (value: number, digits = 1) =>
    value.toLocaleString(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits });

  useEffect(() => {
    let alive = true;
    const load = () =>
      fetch("/api/admin/load", { credentials: "include" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => { if (alive && d) setData(d); })
        .catch(() => { /* Anzeige, kein Auftrag: ein Aussetzer ist egal */ });
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => { alive = false; clearInterval(id); };
  }, []);

  if (!data) return null;

  const { machine, jobs, uploads } = data;
  const usedGb = data.memory_used_bytes === null ? null : data.memory_used_bytes / 1024 ** 3;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5 space-y-4">
      <div>
        <p className="text-sm font-medium text-foreground">{t("title")}</p>
        <p className="text-xs text-muted mt-1">
          {t("detected", {
            cores: num(machine.cores, 0),
            memory: num(machine.memory_gb),
          })}
        </p>
      </div>

      <div className="space-y-2">
        <Meter
          label={t("slots")}
          value={jobs.running}
          max={jobs.total}
          text={
            jobs.queued > 0
              ? t("slotsWaiting", { running: jobs.running, total: jobs.total, waiting: jobs.queued })
              : t("slotsValue", { running: jobs.running, total: jobs.total })
          }
        />
        <Meter
          label={t("uploads")}
          value={uploads.running}
          max={uploads.total}
          text={t("slotsValue", { running: uploads.running ?? 0, total: uploads.total })}
        />
        <Meter
          label={t("cpu")}
          value={data.cpu_percent}
          max={100}
          text={data.cpu_percent === null ? t("unknown") : `${num(data.cpu_percent)} %`}
        />
        <Meter
          label={t("memory")}
          value={usedGb}
          max={machine.memory_gb}
          text={
            usedGb === null
              ? t("unknown")
              : t("memoryValue", { used: num(usedGb), total: num(machine.memory_gb) })
          }
        />
      </div>

      <p className="text-xs text-muted-soft">{t("hint")}</p>
    </div>
  );
}
