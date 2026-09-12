"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { lineAudioUrl } from "../_api";
import { needsVoice } from "../_logic";
import Speaker from "./Speaker";
import type { JobProgress, Line, Person } from "../_types";

interface Props {
  jobUuid: string | null;
  lines: Line[];
  persons: Person[];
  voicedIds: string[];
  progress: JobProgress | null;
  running: boolean;
  failedIndex: number;
  /** The run is done: no progress any more, but every contribution to listen to. */
  rueckblick?: boolean;
}

/** The stage and the strip of the screencast, with speakers instead of slides. */
export default function BeitragVorschau(props: Props) {
  const { jobUuid, lines, persons, voicedIds, progress, running, failedIndex, rueckblick = false } = props;
  const t = useTranslations("tools.podcast.vorschau");
  const tCast = useTranslations("tools.podcast.cast");
  const streifenRef = useRef<HTMLDivElement>(null);
  const [gewaehlt, setGewaehlt] = useState<string | null>(null);
  const [kannLinks, setKannLinks] = useState(false);
  const [kannRechts, setKannRechts] = useState(false);

  // While the job runs its progress is the truth, but only once it has one: at the
  // very start of a run the kept contributions are already there to listen to.
  const ausListe = lines.map((l, i) => (needsVoice(l, voicedIds) ? -1 : i));
  const fertigeIdx = new Set(running && progress?.fertig ? progress.fertig : ausListe);
  const hatTon = (i: number) => fertigeIdx.has(i);
  const laufend = running ? lines.findIndex((_, i) => !fertigeIdx.has(i)) : -1;

  const letzteFertig = [...fertigeIdx].filter((i) => i >= 0).sort((a, b) => a - b).pop();
  const zeigtId = (gewaehlt && lines.some((l) => l.id === gewaehlt) ? gewaehlt : null)
    ?? (rueckblick ? lines[0]?.id : letzteFertig !== undefined ? lines[letzteFertig]?.id : null)
    ?? lines[0]?.id
    ?? null;
  const zeigtIdx = lines.findIndex((l) => l.id === zeigtId);
  const zeigt = zeigtIdx >= 0 ? lines[zeigtIdx] : null;
  const istFertig = zeigtIdx >= 0 && hatTon(zeigtIdx);
  const istGeaendert = !!zeigt && !running && needsVoice(zeigt, voicedIds) && voicedIds.length > 0;

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
  }, [messen, lines.length]);

  // The shown tile has to stay visible even when the stage moves on by itself.
  useEffect(() => {
    const el = streifenRef.current;
    if (!el) return;
    const kachel = el.querySelector<HTMLElement>('[data-aktiv="true"]');
    if (!kachel) return;
    const aussen = el.getBoundingClientRect();
    const innen = kachel.getBoundingClientRect();
    el.scrollBy({ left: innen.left - aussen.left - aussen.width / 2 + innen.width / 2, behavior: "smooth" });
  }, [zeigtId]);

  /** A click moves by one tile width, measured on the first tile. */
  const schieben = useCallback((richtung: -1 | 1) => {
    const el = streifenRef.current;
    if (!el) return;
    const breite = el.querySelector("button")?.getBoundingClientRect().width ?? 74;
    el.scrollBy({ left: richtung * (breite + 8), behavior: "smooth" });
  }, []);

  if (!lines.length || !zeigt || !jobUuid) return null;
  const person = persons[zeigt.speaker] ?? persons[0];
  // The audio changes with the text, so the player must not reuse an old one.
  const tonUrl = `${lineAudioUrl(jobUuid, zeigt.id)}?v=${voicedIds.length}`;

  return (
    <section className="mt-8" aria-label={t("ueberschrift")}>
      {!rueckblick && (
        <p className="text-sm text-foreground-soft mb-3">
          {t("fortschritt", { fertig: [...fertigeIdx].filter((i) => i >= 0).length, total: lines.length })}
        </p>
      )}

      <div className="grid gap-5 md:grid-cols-[1fr_1.6fr]">
        <div className="rounded-lg border border-border-soft bg-background p-5 flex flex-col items-center justify-center gap-3 text-center">
          <span className="w-16 h-16 rounded-full border-2 border-border flex items-center justify-center text-2xl font-bold text-foreground-soft">
            {person.name.trim().charAt(0).toUpperCase() || "?"}
          </span>
          <span className="text-sm font-medium text-foreground">{person.name}</span>
          <span className="text-xs text-muted-soft">{tCast(`roles.${person.role}`)}</span>
        </div>

        <div>
          <p className="text-xs uppercase tracking-wide text-muted-soft mb-1">{t("beitragVon", { n: zeigtIdx + 1, total: lines.length })}</p>
          <div className="bg-surface border border-border-soft rounded-lg p-3 text-sm text-foreground-soft max-h-40 overflow-y-auto whitespace-pre-wrap">{zeigt.text}</div>
          {istGeaendert ? (
            <p className="mt-3">
              <StatusMark tone="warn" className="text-xs">{t("geaendert")}</StatusMark>
            </p>
          ) : istFertig ? (
            <audio key={tonUrl} controls preload={rueckblick ? "metadata" : "none"} className="w-full mt-3" src={tonUrl} />
          ) : zeigtIdx === failedIndex ? (
            <p className="text-xs text-error mt-3">{t("fehler")}</p>
          ) : zeigtIdx === laufend ? (
            <p className="text-xs text-muted mt-3">{t("wirdVertont")}</p>
          ) : (
            <p className="text-xs text-muted mt-3">{t("wartet")}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 pt-4 pb-1">
        <span className="hidden md:block select-none">
          <IconButton onClick={() => schieben(-1)} disabled={!kannLinks} aria-label={t("nachLinks")} className="select-none disabled:opacity-40 disabled:cursor-not-allowed">
            <CaretLeft size={14} weight="bold" />
          </IconButton>
        </span>
        <div ref={streifenRef} className="min-w-0 flex-1 flex gap-2 overflow-x-auto scrollbar-hide">
          {lines.map((l, i) => {
            const bereit = hatTon(i);
            const aktiv = l.id === zeigtId;
            const sprecher = persons[l.speaker] ?? persons[0];
            const beschriftung = bereit ? t("abspielen", { n: i + 1 }) : t("wartetKachel", { n: i + 1 });
            return (
              <button
                key={l.id}
                type="button"
                data-aktiv={aktiv}
                disabled={!bereit && !rueckblick}
                onClick={() => setGewaehlt(l.id)}
                aria-label={beschriftung}
                className={`relative shrink-0 w-[74px] h-[52px] rounded-md border select-none flex items-center justify-center text-sm font-bold text-foreground-soft bg-background ${
                  aktiv ? "border-kb outline outline-2 outline-kb" : "border-border-soft"
                } ${bereit ? "" : i === laufend ? "border-dashed" : "opacity-40 grayscale"}`}
              >
                {sprecher.name.trim().charAt(0).toUpperCase() || "?"}
                <span className="absolute left-1 top-1 text-3xs font-semibold px-1 rounded bg-background/90 text-muted">{i + 1}</span>
              </button>
            );
          })}
        </div>
        <span className="hidden md:block select-none">
          <IconButton onClick={() => schieben(1)} disabled={!kannRechts} aria-label={t("nachRechts")} className="select-none disabled:opacity-40 disabled:cursor-not-allowed">
            <CaretRight size={14} weight="bold" />
          </IconButton>
        </span>
      </div>
    </section>
  );
}
