"use client";

/** What came back from the evaluation, counted and without any name attached. */

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { CaretRight } from "@phosphor-icons/react";
import Modal from "@/components/ui/Modal";
import { Balken, Kachel, Karte, Ladeanzeige } from "./_bausteine";
import { ZeitraumChips } from "./_raster";

type Frage =
  | { id: string; type: "choice"; text: string; answered: number; distribution: Record<string, number> }
  | { id: string; type: "multi"; text: string; answered: number; distribution: Record<string, number> }
  | { id: string; type: "text"; text: string; answered: number; answers: string[] };

interface Teilnahme {
  number: number;
  created_at: string;
  answers: { question_id: string; value: string | number | string[] }[];
}

interface Daten {
  total: number;
  questions: Frage[];
  responses: Teilnahme[];
}

export default function StatistikEvaluationPage() {
  const t = useTranslations("admin.statistik");
  const locale = useLocale();
  const [zeitraum, setZeitraum] = useState("30t");
  const [daten, setDaten] = useState<Daten | null>(null);
  const [fehler, setFehler] = useState(false);
  const [offen, setOffen] = useState<Teilnahme | null>(null);

  useEffect(() => {
    setDaten(null);
    fetch(`/api/admin/evaluation/results?range=${zeitraum}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDaten)
      .catch(() => setFehler(true));
  }, [zeitraum]);

  const datum = (wert: string) =>
    new Date(wert).toLocaleString(locale === "en" ? "en-US" : "de-DE", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Europe/Berlin",
    });

  if (fehler) return <p className="text-sm text-error">{t("loadError")}</p>;

  return (
    <div className="space-y-4">
      <ZeitraumChips wert={zeitraum} setzen={setZeitraum} className="" mitAlle />

      {!daten ? (
        <Ladeanzeige />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Kachel titel={t("evaluation.total")} wert={daten.total} fuss={t("evaluation.totalHint")} />
          </div>

          {daten.questions.map((frage) =>
            frage.type === "choice" || frage.type === "multi" ? (
              <Karte
                key={frage.id}
                titel={frage.text}
                hinweis={t("evaluation.textHint", { answered: frage.answered })}
              >
                <div className="mt-3">
                  <Balken
                    zeilen={Object.entries(frage.distribution).map(([option, anzahl]) => ({
                      label: option === "not_tested" ? t("evaluation.notTested") : option,
                      wert: anzahl,
                    }))}
                    kopf={[t("evaluation.count")]}
                    labelBreite={24}
                  />
                </div>
              </Karte>
            ) : (
              <Karte
                key={frage.id}
                titel={frage.text}
                hinweis={t("evaluation.textHint", { answered: frage.answered })}
              >
                {frage.answers.length === 0 ? (
                  <p className="text-xs text-muted-soft mt-3">{t("evaluation.noAnswers")}</p>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {frage.answers.map((antwort, i) => (
                      <li
                        key={i}
                        className="text-sm text-foreground-soft border-l-2 border-border-soft pl-3"
                      >
                        {antwort}
                      </li>
                    ))}
                  </ul>
                )}
              </Karte>
            ),
          )}

          <Karte titel={t("evaluation.single")} hinweis={t("evaluation.singleHint")}>
            {daten.responses.length === 0 ? (
              <p className="text-xs text-muted-soft mt-3">{t("evaluation.noAnswers")}</p>
            ) : (
              <ul className="mt-3 divide-y divide-border-soft">
                {daten.responses.map((teilnahme) => (
                  <li key={teilnahme.number}>
                    <button
                      type="button"
                      onClick={() => setOffen(teilnahme)}
                      className="w-full flex items-center justify-between gap-3 py-2.5 text-left"
                    >
                      <span className="text-sm font-medium">
                        {t("evaluation.participant", { number: teilnahme.number })}
                      </span>
                      <span className="flex items-center gap-2 text-xs text-muted">
                        {datum(teilnahme.created_at)}
                        <CaretRight size={14} weight="bold" />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Karte>

          {offen && (
            <Modal
              open
              onClose={() => setOffen(null)}
              title={t("evaluation.participant", { number: offen.number })}
            >
              <p className="text-xs text-muted mb-4">{datum(offen.created_at)}</p>
              <div className="space-y-4">
                {daten.questions.map((frage) => {
                  const antwort = offen.answers.find((a) => a.question_id === frage.id);
                  return (
                    <div key={frage.id}>
                      <p className="text-xs uppercase tracking-wide text-muted">{frage.text}</p>
                      <p className="text-sm mt-1">
                        {antwort === undefined ? (
                          <span className="text-muted-soft">{t("evaluation.skipped")}</span>
                        ) : antwort.value === "not_tested" ? (
                          <span className="text-muted-soft">{t("evaluation.notTested")}</span>
                        ) : Array.isArray(antwort.value) ? (
                          antwort.value.join(", ")
                        ) : (
                          String(antwort.value)
                        )}
                      </p>
                    </div>
                  );
                })}
              </div>
            </Modal>
          )}
        </>
      )}
    </div>
  );
}
