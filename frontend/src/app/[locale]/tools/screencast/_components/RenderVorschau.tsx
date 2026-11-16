"use client";

import { useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight, Prohibit } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import type { SlideData } from "@/types";
import { useTileStrip } from "@/hooks/useTileStrip";

interface Props {
  slides: SlideData[];
  fertig: number[];
  jobUuid: string;
  speed: number;
  /** The run is done: no progress any more, but all slides to listen to again. */
  rueckblick?: boolean;
  /** These slides are not in the screencast, they never get audio. */
  nichtDabei?: number[];
  /** Where the audio of a slide comes from, the demo has its own files. */
  tonUrl?: (index: number) => string;
}

export default function RenderVorschau({ slides, fertig, jobUuid, speed, rueckblick = false, nichtDabei = [], tonUrl }: Props) {
  const t = useTranslations("tools.screencast.vorschau");
  const audioRef = useRef<HTMLAudioElement>(null);
  const [gewaehlt, setGewaehlt] = useState<number | null>(null);
  const fertigeMenge = new Set(fertig);
  const nichtDabeiMenge = new Set(nichtDabei);
  // Without a click the stage moves along, a click pins it.
  const hoechste = fertig.length ? fertig[fertig.length - 1] : null;
  const zeigt = gewaehlt ?? (rueckblick ? 0 : hoechste) ?? 0;

  // The MP3 is always voiced at speed 1.0, the speed enters the video via atempo.
  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = speed;
  }, [speed, zeigt]);

  const { streifenRef, kannLinks, kannRechts, schieben } = useTileStrip(slides.length, zeigt);

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

        <div className="flex flex-col">
          <p className="text-xs uppercase tracking-wide text-muted-soft mb-1">
            {t("folieVon", { n: zeigt + 1, total: slides.length })}
          </p>
          {/* Beside the slide the text fills the column down to the audio, stacked it keeps its cap. */}
          <div className="md:relative md:flex-1 md:min-h-24">
            <div className="bg-surface border border-border-soft rounded-lg p-3 text-sm text-foreground-soft max-h-40 overflow-y-auto md:absolute md:inset-0 md:max-h-none">
              {folie?.script || t("ohneTon")}
            </div>
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
              src={tonUrl ? tonUrl(zeigt) : `/api/screencast/${jobUuid}/vorschau/${zeigt}`}
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
