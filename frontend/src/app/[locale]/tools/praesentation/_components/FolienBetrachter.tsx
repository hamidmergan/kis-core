"use client";

import { ArrowLeft, ArrowRight, CornersOut } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import IconButton from "@/components/ui/IconButton";
import FolienGrossbild from "./FolienGrossbild";

interface FolienBetrachterProps {
  ids: string[];
  urlFuer: (id: string) => string | null;
}

/** The finished deck to page through: one slide large, all of them in a strip below, full screen on click. */
export default function FolienBetrachter({ ids, urlFuer }: FolienBetrachterProps) {
  const t = useTranslations("tools.praesentation.slides");
  const tDone = useTranslations("tools.praesentation.done");
  const [index, setIndex] = useState(0);
  const [gross, setGross] = useState(false);
  const leiste = useRef<HTMLOListElement>(null);
  const n = ids.length;
  const i = Math.min(index, Math.max(n - 1, 0));

  // The arrow keys page through the deck, unless a field has the focus or the full view pages itself.
  useEffect(() => {
    if (gross) return;
    function handler(e: KeyboardEvent) {
      if ((e.target as HTMLElement | null)?.closest("input, textarea, select, [contenteditable='true']")) return;
      if (e.key === "ArrowLeft") setIndex((x) => Math.max(0, x - 1));
      if (e.key === "ArrowRight") setIndex((x) => Math.min(n - 1, x + 1));
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [gross, n]);

  // The strip scrolls sideways only, the page itself must not jump when a key pages on.
  useEffect(() => {
    const box = leiste.current;
    const el = box?.children[i] as HTMLElement | undefined;
    if (box && el) box.scrollTo({ left: el.offsetLeft - box.clientWidth / 2 + el.clientWidth / 2, behavior: "smooth" });
  }, [i]);

  if (n === 0) return null;
  const url = urlFuer(ids[i]);

  return (
    <div>
      <div className="rounded-lg overflow-hidden border border-border-soft bg-surface">
        <button type="button" onClick={() => setGross(true)} aria-label={tDone("fullscreen")} className="block w-full cursor-zoom-in">
          {url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt={t("slideLabel", { n: i + 1 })} className="block w-full h-auto" />
          ) : (
            <span className="aspect-video flex items-center justify-center text-xs text-muted">{t("noPreview")}</span>
          )}
        </button>
      </div>

      <div className="flex items-center justify-center gap-3 mt-3">
        <IconButton aria-label={tDone("prev")} disabled={i === 0} onClick={() => setIndex(i - 1)}>
          <ArrowLeft className="w-3.5 h-3.5" />
        </IconButton>
        <span className="text-sm text-foreground-soft tabular-nums text-center min-w-28">{t("previewTitle", { n: i + 1, total: n })}</span>
        <IconButton aria-label={tDone("next")} disabled={i === n - 1} onClick={() => setIndex(i + 1)}>
          <ArrowRight className="w-3.5 h-3.5" />
        </IconButton>
        <IconButton aria-label={tDone("fullscreen")} onClick={() => setGross(true)}>
          <CornersOut className="w-3.5 h-3.5" />
        </IconButton>
      </div>

      <ol ref={leiste} className="relative flex gap-2 overflow-x-auto scrollbar-hide mt-4 pb-1" aria-label={tDone("allSlides")}>
        {ids.map((id, j) => {
          const bild = urlFuer(id);
          return (
            <li key={id} className="shrink-0">
              <button type="button" onClick={() => setIndex(j)} aria-label={t("slideLabel", { n: j + 1 })}
                      aria-current={j === i ? "true" : undefined}
                      className={`block w-28 rounded-md overflow-hidden border-2 transition-colors ${j === i ? "border-kb" : "border-transparent hover:border-kb"}`}>
                {bild ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={bild} alt="" loading="lazy" className="block w-full aspect-video object-cover" />
                ) : (
                  <span className="block aspect-video bg-surface" />
                )}
              </button>
            </li>
          );
        })}
      </ol>

      {gross && (
        <FolienGrossbild index={i} total={n} previewUrl={urlFuer(ids[i])}
                         onClose={() => setGross(false)} onIndexChange={setIndex} />
      )}
    </div>
  );
}
