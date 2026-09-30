"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import type { BildErgebnis } from "./useBildAuftraege";
import BeschreibungText from "./BeschreibungText";
import { alsJpg, speichern } from "../_utils";

interface Props {
  bild: BildErgebnis;
  alt: string;
  onBearbeiten?: (bild: BildErgebnis) => void;
  onBeschreiben?: (bild: BildErgebnis) => void;
  /** Shown instead of the plain picture, the before and after comparison of an edit. */
  vorschau?: ReactNode;
}

const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";

/** One result with its downloads and the ways into the other tasks. */
export default function ErgebnisKarte({ bild, alt, onBearbeiten, onBeschreiben, vorschau }: Props) {
  const t = useTranslations("tools.image.result");
  const stamm = bild.filename.replace(/\.[^.]+$/, "");
  return (
    <figure className="rounded-lg border border-border-soft bg-background p-2">
      {vorschau ?? <img src={bild.url} alt={alt} className="w-full rounded-md" />}
      <figcaption className="mt-2 flex flex-wrap gap-1.5">
        <button type="button" className={KNOPF} onClick={() => speichern(bild.blob, bild.filename)}>
          {t("download", { format: "PNG" })}
        </button>
        <button type="button" className={KNOPF} onClick={async () => speichern(await alsJpg(bild.blob), `${stamm}.jpg`)}>
          {t("download", { format: "JPG" })}
        </button>
        {onBearbeiten && (
          <button type="button" className={KNOPF} onClick={() => onBearbeiten(bild)}>{t("toEdit")}</button>
        )}
        {onBeschreiben && (
          <button type="button" className={KNOPF} onClick={() => onBeschreiben(bild)}>{t("toAnalyze")}</button>
        )}
      </figcaption>
      {bild.beschreibung && (
        <BeschreibungText beschreibung={bild.beschreibung} modellPrompt={bild.modellPrompt} dateiname={bild.filename} />
      )}
    </figure>
  );
}
