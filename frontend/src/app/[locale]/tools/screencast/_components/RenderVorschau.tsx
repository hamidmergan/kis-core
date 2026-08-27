"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Prohibit } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import type { SlideData } from "@/types";

interface Props {
  slides: SlideData[];
  fertig: number[];
  jobUuid: string;
  speed: number;
  /** The run is done: no progress any more, but all slides to listen to again. */
  rueckblick?: boolean;
  /** These slides are not in the screencast, they never get audio. */
  nichtDabei?: number[];
}

export default function RenderVorschau({ slides, fertig, jobUuid, speed, rueckblick = false, nichtDabei = [] }: Props) {
  const t = useTranslations("tools.screencast.vorschau");
  const audioRef = useRef<HTMLAudioElement>(null);
  const streifenRef = useRef<HTMLDivElement>(null);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const [kannLinks, setKannLinks] = useState(false);
  const [kannRechts, setKannRechts] = useState(false);
  const fertigeMenge = new Set(fertig);
  const nichtDabeiMenge = new Set(nichtDabei);
  // Without a click the stage moves along, a click pins it.
  const hoechste = fertig.length ? fertig[fertig.length - 1] : null;
  const zeigt = gewaehlt ?? (rueckblick ? 0 : hoechste) ?? 0;

  // The MP3 is always voiced at speed 1.0, the speed enters the video via atempo.
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

  // The shown tile has to stay visible even when the stage moves on by itself.
  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    const kachel = el.querySelector<HTMLElement>('[data-aktiv="true"]');
    if (!kachel) return;
    const aussen = el.getBoundingClientRect();
    const innen = kachel.getBoundingClientRect();
    el.scrollBy({ left: innen.left - aussen.left - aussen.width / 2 + innen.width / 2, behavior: "smooth" });
  }, [zeigt]);

  /** A click moves by one tile width, measured on the first tile. */
  const schieben = useCallback((richtung: -1 | 1) => {
    const el = streifenRef.current;
    if (!el) return;
    const breite = el.querySelector("button")?.getBoundingClientRect().width ?? 74;
    el.scrollBy({ left: richtung * (breite + 8), behavior: "smooth" });
  }, []);

  if (!slides.length) return null;
  const folie = slides[zeigt];
  const hatSkript = !!folie?.script?.trim();
  const istRaus = nichtDabeiMenge.has(zeigt);
  const istFertig = fertigeMenge.has(zeigt);

  return (
    <section className="mt-8" aria-label={t("ueberschrift")}>
      {!rueckblick && (
        <p className="text-sm text-foreground-soft mb-3">
          {t("fortschritt", { fertig: fertig.length, total: slides.length - nichtDabeiMenge.size })}
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
          {istRaus ? (
            <p className="text-xs text-muted mt-3">{t("nichtDabei", { n: zeigt + 1 })}</p>
          ) : hatSkript && istFertig ? (
            <audio
              ref={audioRef}
              key={`${jobUuid}-${zeigt}`}
              controls
              // Preload nothing during the run, show the length in the review.
              preload={rueckblick ? "metadata" : "none"}
              className="w-full mt-3"
              src={`/api/screencast/${jobUuid}/vorschau/${zeigt}`}
            />
          ) : hatSkript ? (
            <p className="text-xs text-muted mt-3">{t("wirdVertont")}</p>
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
          const raus = nichtDabeiMenge.has(i);
          const bereit = fertigeMenge.has(i) && !raus;
          const beschriftung = raus
            ? t("nichtDabei", { n: i + 1 })
            : bereit
              ? t("abspielen", { n: i + 1 })
              : t("wartet", { n: i + 1 });
          return (
            <button
              key={i}
              type="button"
              data-aktiv={i === zeigt}
              disabled={!bereit}
              onClick={() => setGewaehlt(i)}
              aria-label={beschriftung}
              title={raus ? beschriftung : undefined}
              className={`relative shrink-0 w-[74px] rounded-md overflow-hidden border select-none ${
                i === zeigt ? "border-kb outline outline-2 outline-kb" : "border-border-soft"
              } ${bereit ? "" : raus ? "cursor-default border-dashed" : "opacity-40 grayscale cursor-default"}`}
            >
              {s.imageBase64 ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`data:image/png;base64,${s.imageBase64}`}
                  alt=""
                  className={`w-full block ${raus ? "opacity-20 grayscale" : ""}`}
                />
              ) : (
                <span className={`block aspect-video bg-surface ${raus ? "opacity-20 grayscale" : ""}`} />
              )}
              {raus && (
                <span className="absolute inset-0 flex items-center justify-center" aria-hidden="true">
                  <Prohibit size={26} weight="bold" className="text-muted-soft opacity-60" />
                </span>
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
