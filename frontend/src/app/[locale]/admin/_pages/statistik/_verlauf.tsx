"use client";

/** Everything one person did, merged and time-ordered, only for those with the right. */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Karte } from "./_bausteine";

interface Ereignis {
  kind: "chat" | "werkzeug" | "uebung" | "beitritt";
  module: string | null;
  text: string | null;
  tool: string | null;
  status: string | null;
  when: string;
}

interface Sitzung {
  day: string;
  from: number;
  to: number;
}

interface Seite {
  events: Ereignis[];
  has_more: boolean;
  sessions: Sitzung[];
}

function EreignisZeile({ e }: { e: Ereignis }) {
  const t = useTranslations("admin.statistik.detail");
  const zeit = new Date(e.when).toLocaleString("de-DE");

  const titel =
    e.kind === "chat"
      ? e.module
        ? t("kindChatIn", { module: e.module })
        : t("kindChat")
      : e.kind === "werkzeug"
        ? t("kindTool", { tool: e.tool ?? "—" })
        : e.kind === "uebung"
          ? t("kindExerciseIn", { module: e.module ?? "—" })
          : t("kindJoinIn", { module: e.module ?? "—" });

  return (
    <li className="border-b border-border-soft py-3 last:border-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
        <p className="text-sm text-foreground-soft">{titel}</p>
        <p className="text-xs text-muted-soft tabular-nums">{zeit}</p>
      </div>
      {e.kind === "chat" && e.text && (
        <p className="mt-1 text-xs text-muted italic">&bdquo;{e.text}&ldquo;</p>
      )}
      {e.kind === "werkzeug" && (
        <p className="mt-1 text-xs text-muted">
          {e.status ?? "—"}
          {e.text && ` · ${e.text}`}
        </p>
      )}
      {e.kind === "beitritt" && e.status && (
        <p className="mt-1 text-xs text-muted">{e.status}</p>
      )}
    </li>
  );
}

export function VerlaufAnsicht({ id }: { id: number }) {
  const t = useTranslations("admin.statistik.detail");
  const tAllgemein = useTranslations("admin.statistik");
  const tAdmin = useTranslations("admin");
  const [seite, setSeite] = useState<Seite | null>(null);
  const [laedt, setLaedt] = useState(false);
  const [fehler, setFehler] = useState(false);

  const laden = (vor?: string) => {
    setLaedt(true);
    const url = vor
      ? `/api/admin/stats/users/${id}/verlauf?vor=${encodeURIComponent(vor)}`
      : `/api/admin/stats/users/${id}/verlauf`;
    fetch(url, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d: Seite) => {
        setSeite((bisher) =>
          bisher && vor ? { ...d, events: [...bisher.events, ...d.events] } : d,
        );
      })
      .catch(() => setFehler(true))
      .finally(() => setLaedt(false));
  };

  useEffect(() => {
    setSeite(null);
    setFehler(false);
    laden();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (fehler) return <p className="mt-4 text-sm text-error">{tAllgemein("loadError")}</p>;

  return (
    <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_260px]">
      <Karte titel={t("history")} hinweis={t("historyHint")}>
        {!seite ? (
          <p className="mt-3 text-xs text-muted-soft">{tAdmin("loading")}</p>
        ) : seite.events.length === 0 ? (
          <p className="mt-3 text-xs text-muted-soft">{t("historyEmpty")}</p>
        ) : (
          <>
            <ul className="mt-3">
              {seite.events.map((e, i) => (
                <EreignisZeile key={i} e={e} />
              ))}
            </ul>
            {seite.has_more && (
              <button
                type="button"
                onClick={() => laden(seite.events[seite.events.length - 1].when)}
                disabled={laedt}
                className="mt-2 text-xs text-muted transition-colors hover:text-kb disabled:opacity-50"
              >
                {laedt ? tAdmin("loading") : t("historyMore")}
              </button>
            )}
          </>
        )}
      </Karte>

      <Karte titel={t("sessions")} hinweis={t("sessionsHint")}>
        {!seite ? (
          <p className="mt-3 text-xs text-muted-soft">{tAdmin("loading")}</p>
        ) : seite.sessions.length === 0 ? (
          <p className="mt-3 text-xs text-muted-soft">{t("sessionsEmpty")}</p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {seite.sessions.map((s, i) => (
              <li key={i} className="flex justify-between text-xs">
                <span className="text-foreground-soft">
                  {new Date(s.day).toLocaleDateString("de-DE")}
                </span>
                <span className="tabular-nums text-muted">
                  {String(s.from).padStart(2, "0")}–{String(s.to + 1).padStart(2, "0")} {t("sessionClock")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Karte>
    </div>
  );
}
