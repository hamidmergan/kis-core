"use client";

import { useState } from "react";
import { Info } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import Checkbox from "@/components/ui/Checkbox";
import type { SlideData } from "@/types";
import { markeFuerFolie, type VertonterStand } from "../_utils";

interface Props {
  slides: SlideData[];
  stand: VertonterStand | null;
  imScreencast: number[];
  neuVertonen: number[];
  gesperrtNeu: Set<number>;
  /** Ab dem zweiten Lauf gibt es etwas wiederzuverwenden. */
  zeigtNeu: boolean;
  stimmeGewechselt: boolean;
  onUmschaltenScreencast: (i: number) => void;
  onUmschaltenNeu: (i: number) => void;
  onAlle: (zeigtNeu: boolean) => void;
  onKeine: (zeigtNeu: boolean) => void;
  onGeaenderte: () => void;
}

export default function FolienAuswahl(props: Props) {
  const {
    slides, stand, imScreencast, neuVertonen, gesperrtNeu, zeigtNeu, stimmeGewechselt,
    onUmschaltenScreencast, onUmschaltenNeu, onAlle, onKeine, onGeaenderte,
  } = props;
  const t = useTranslations("tools.screencast.folienAuswahl");
  const [offen, setOffen] = useState(false);

  const dabei = new Set(imScreencast);
  const neu = new Set(neuVertonen);

  return (
    <section className="mb-6" aria-label={t("titel")}>
      <div className="flex items-baseline justify-between gap-4 mb-2">
        <span className="text-sm font-medium text-foreground-soft">{t("titel")}</span>
        <button
          type="button"
          onClick={() => setOffen(!offen)}
          aria-expanded={offen}
          className="rounded-sm px-1 py-0.5 text-sm font-medium text-kb hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
        >
          {offen ? t("zuklappen") : t("aendern")}
        </button>
      </div>

      <div className="rounded-lg bg-surface px-4 py-3 text-sm text-foreground-soft">
        {zeigtNeu
          ? t("zusammenfassungMitNeu", { dabei: dabei.size, total: slides.length, neu: neu.size })
          : t("zusammenfassung", { dabei: dabei.size, total: slides.length })}
      </div>

      {!zeigtNeu && <p className="mt-1 text-xs text-muted-soft">{t("erstlaufHinweis")}</p>}

      {offen && (
        <div className="mt-2 rounded-lg border border-border-soft overflow-hidden">
          {stimmeGewechselt && (
            <p className="flex items-start gap-2 border-b border-border-soft bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
              <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
              {t("stimmeGewechselt")}
            </p>
          )}

          <div className="flex flex-col gap-2 border-b border-border-soft bg-surface px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex gap-1">
              <SchnellKnopf label={t("alle")} onClick={() => onAlle(zeigtNeu)} />
              <SchnellKnopf label={t("keine")} onClick={() => onKeine(zeigtNeu)} />
              {zeigtNeu && <SchnellKnopf label={t("geaenderte")} onClick={onGeaenderte} />}
            </div>
            <div className="flex justify-end gap-2">
              <span className="w-[3.25rem] text-center text-2xs font-semibold uppercase tracking-wide text-muted-soft sm:w-[4.5rem]">
                {t("spalteScreencast")}
              </span>
              {zeigtNeu && (
                <span className="w-[3.25rem] text-center text-2xs font-semibold uppercase tracking-wide text-muted-soft sm:w-[4.5rem]">
                  {t("spalteNeu")}
                </span>
              )}
            </div>
          </div>

          <div className="max-h-[21rem] overflow-y-auto">
            {slides.map((folie, i) => {
              const drin = dabei.has(i);
              const leer = !folie.script?.trim();
              const marke = markeFuerFolie(stand, i, folie.script ?? "", folie.extractedText ?? "");
              return (
                <div
                  key={i}
                  className="flex items-center gap-3 border-b border-border-soft px-3 py-2 last:border-b-0"
                >
                  <span className={`w-6 flex-shrink-0 text-right text-xs tabular-nums text-muted-soft ${drin ? "" : "opacity-45"}`}>
                    {i + 1}
                  </span>
                  <div className={`min-w-0 flex-1 ${drin ? "" : "opacity-45"}`}>
                    <p className={`truncate text-sm ${leer ? "italic text-muted-soft" : "text-foreground-soft"}`}>
                      {leer ? t("ohneText") : folie.script}
                    </p>
                    {marke && (
                      <span className="mt-0.5 inline-block rounded px-1.5 py-px text-2xs font-medium bg-kb/20 text-kb">
                        {marke === "skript" ? t("markeSkript") : t("markeFolie")}
                      </span>
                    )}
                  </div>
                  <div className="flex w-[3.25rem] flex-shrink-0 justify-center sm:w-[4.5rem]">
                    <Checkbox
                      checked={drin}
                      onChange={() => onUmschaltenScreencast(i)}
                      label={t("hakenScreencast", { n: i + 1 })}
                      labelClassName="sr-only"
                    />
                  </div>
                  {zeigtNeu && (
                    <div className="flex w-[3.25rem] flex-shrink-0 justify-center rounded bg-kb/5 py-0.5 sm:w-[4.5rem]">
                      <Checkbox
                        checked={neu.has(i)}
                        disabled={!drin || leer || gesperrtNeu.has(i)}
                        onChange={() => onUmschaltenNeu(i)}
                        label={t("hakenNeu", { n: i + 1 })}
                        labelClassName="sr-only"
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

function SchnellKnopf({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded border border-border-soft bg-background px-2 py-1 text-xs font-medium text-muted transition-colors hover:border-kb hover:text-kb focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
    >
      {label}
    </button>
  );
}
