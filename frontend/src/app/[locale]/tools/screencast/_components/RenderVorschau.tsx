"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import type { SlideData } from "@/types";

interface Props {
  slides: SlideData[];
  fertig: number[];
  jobUuid: string;
  speed: number;
  /** Der Lauf ist durch: kein Fortschritt mehr, sondern alle Folien zum Nachhoeren. */
  rueckblick?: boolean;
}

export default function RenderVorschau({ slides, fertig, jobUuid, speed, rueckblick = false }: Props) {
  const t = useTranslations("tools.screencast.vorschau");
  const audioRef = useRef<HTMLAudioElement>(null);
  const streifenRef = useRef<HTMLDivElement>(null);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [kannLinks, setKannLinks] = useState(false);
  const [kannRechts, setKannRechts] = useState(false);
  const fertigeMenge = new Set(fertig);
  // Ohne Klick zeigt die Buehne die hoechste fertige Folie und wandert mit. Ein Klick
  // haelt sie fest, sonst wird man beim Zuhoeren weggerissen.
  const hoechste = fertig.length ? fertig[fertig.length - 1] : null;
  const zeigt = gewaehlt ?? (rueckblick ? 0 : hoechste);

  // Die MP3 ist immer in Tempo 1,0 vertont, das Tempo kommt erst per atempo ins Video.
  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = speed;
  }, [speed, zeigt]);

  const messen = useCallback(() => {
    const el = streifenRef.current;
    if (!el) return;
    setKannLinks(el.scrollLeft > 1);
    setKannRechts(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    messen();
    el.addEventListener("scroll", messen, { passive: true });
    window.addEventListener("resize", messen);
    return () => {
      el.removeEventListener("scroll", messen);
      window.removeEventListener("resize", messen);
    };
  }, [messen, slides.length]);

  // Die gezeigte Kachel muss sichtbar bleiben, auch wenn die Buehne von allein weiterwandert.
  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    const kachel = el.querySelector<HTMLElement>('[data-aktiv="true"]');
    if (!kachel) return;
    const aussen = el.getBoundingClientRect();
    const innen = kachel.getBoundingClientRect();
    el.scrollBy({ left: innen.left - aussen.left - aussen.width / 2 + innen.width / 2, behavior: "smooth" });
  }, [zeigt]);

  /** Ein Klick schiebt um eine Kachelbreite, gemessen an der ersten Kachel. */
  const schieben = useCallback((richtung: -1 | 1) => {
    const el = streifenRef.current;
    if (!el) return;
    const breite = el.querySelector("button")?.getBoundingClientRect().width ?? 74;
    el.scrollBy({ left: richtung * (breite + 8), behavior: "smooth" });
  }, []);

  if (zeigt === null || !slides.length) return null;
  const folie = slides[zeigt];
  const hatTon = !!folie?.script?.trim();

  return (
    <section className="mt-8" aria-label={t("ueberschrift")}>
      {!rueckblick && (
        <p className="text-sm text-foreground-soft mb-3">
          {t("fortschritt", { fertig: fertig.length, total: slides.length })}
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-[1.25fr_1fr]">
        <div className="rounded-lg overflow-hidden border border-border-soft bg-background">
          {folie?.imageBase64 ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={`data:image/png;base64,${folie.imageBase64}`} alt="" className="w-full block" />
          ) : (
            <div className="aspect-video bg-surface" />
          )}
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-muted-soft mb-1">
            {t("folieVon", { n: zeigt + 1, total: slides.length })}
          </p>
          <div className="bg-surface border border-border-soft rounded-lg p-3 text-sm text-foreground-soft max-h-40 overflow-y-auto">
            {folie?.script || t("ohneTon")}
          </div>
          {hatTon ? (
            <audio
              ref={audioRef}
              key={`${jobUuid}-${zeigt}`}
              controls
              // Waehrend des Laufs nichts vorladen, im Rueckblick die Laenge zeigen.
              preload={rueckblick ? "metadata" : "none"}
              className="w-full mt-3"
              src={`/api/screencast/${jobUuid}/vorschau/${zeigt}`}
            />
          ) : (
            <p className="text-xs text-muted mt-3">{t("ohneTon")}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-4 pb-1">
        <span className="hidden md:block select-none">
          <IconButton
            onClick={() => schieben(-1)}
            disabled={!kannLinks}
            aria-label={t("nachLinks")}
            className="select-none disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CaretLeft size={14} weight="bold" />
          </IconButton>
        </span>
        <div ref={streifenRef} className="min-w-0 flex-1 flex gap-2 overflow-x-auto scrollbar-hide">
        {slides.map((s, i) => {
          const bereit = fertigeMenge.has(i);
          return (
            <button
              key={i}
              type="button"
              data-aktiv={i === zeigt}
              disabled={!bereit}
              onClick={() => setGewaehlt(i)}
              aria-label={bereit ? t("abspielen", { n: i + 1 }) : t("wartet", { n: i + 1 })}
              className={`relative shrink-0 w-[74px] rounded-md overflow-hidden border select-none ${
                i === zeigt ? "border-kb outline outline-2 outline-kb" : "border-border-soft"
              } ${bereit ? "" : "opacity-40 grayscale cursor-default"}`}
            >
              {s.imageBase64 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={`data:image/png;base64,${s.imageBase64}`} alt="" className="w-full block" />
              ) : (
                <span className="block aspect-video bg-surface" />
              )}
              <span className="absolute left-1 top-1 text-3xs font-semibold px-1 rounded bg-background/90 text-muted">
                {i + 1}
              </span>
            </button>
          );
        })}
        </div>
        <span className="hidden md:block select-none">
          <IconButton
            onClick={() => schieben(1)}
            disabled={!kannRechts}
            aria-label={t("nachRechts")}
            className="select-none disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <CaretRight size={14} weight="bold" />
          </IconButton>
        </span>
      </div>
    </section>
  );
}
