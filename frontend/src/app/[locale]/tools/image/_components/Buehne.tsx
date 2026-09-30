"use client";

import { forwardRef, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Platzhalter from "./Platzhalter";
import VorherNachher from "./VorherNachher";
import type { BildErgebnis } from "./useBildAuftraege";
import { alsJpg, speichern } from "../_utils";

const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";

interface Props {
  bild: BildErgebnis | null;
  /** A picture is being created or edited, it will land here. */
  laeuft: boolean;
  label: string;
  meldungen: string[];
  platzhalter: string;
  onHochladen?: (datei: File) => void;
  onBearbeiten?: () => void;
  onBeschreiben?: () => void;
  onLoeschen?: () => void;
  children?: ReactNode;
}

/** The one large picture of the page, the same in all three tasks, with its downloads and ways on. */
const Buehne = forwardRef<HTMLDivElement, Props>(function Buehne(
  { bild, laeuft, label, meldungen, platzhalter, onHochladen, onBearbeiten, onBeschreiben, onLoeschen, children }, ref,
) {
  const t = useTranslations("tools.image.result");
  const tEdit = useTranslations("tools.image.edit");
  const stamm = bild?.filename.replace(/\.[^.]+$/, "") ?? "bild";

  return (
    <div ref={ref} className="scroll-mt-4 rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
      {meldungen.map((m) => <p key={m} className="mb-3 text-sm text-error" role="alert">{m}</p>)}
      {laeuft ? (
        <>
          <div className="flex aspect-video items-center justify-center rounded-md bg-surface-dim animate-pulse">
            <Spinner label={label} />
          </div>
          <BackgroundHint className="mt-3" />
        </>
      ) : bild ? (
        <>
          {bild.vorlageUrl ? (
            <VorherNachher vorher={bild.vorlageUrl} nachher={bild.url} labelVorher={tEdit("before")}
              labelNachher={tEdit("after")} labelRegler={tEdit("compareLabel")} />
          ) : (
            <img src={bild.url} alt={bild.beschreibung ?? bild.filename} className="w-full max-h-[60vh] rounded-md bg-surface object-contain" />
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {bild.jobUuid && (
              <>
                <button type="button" className={KNOPF} onClick={() => speichern(bild.blob, bild.filename)}>
                  {t("download", { format: "PNG" })}
                </button>
                <button type="button" className={KNOPF} onClick={async () => speichern(await alsJpg(bild.blob), `${stamm}.jpg`)}>
                  {t("download", { format: "JPG" })}
                </button>
              </>
            )}
            {onBearbeiten && <button type="button" className={KNOPF} onClick={onBearbeiten}>{t("toEdit")}</button>}
            {onBeschreiben && <button type="button" className={KNOPF} onClick={onBeschreiben}>{t("toAnalyze")}</button>}
            {bild.jobUuid && onLoeschen && <button type="button" className={KNOPF} onClick={onLoeschen}>{t("delete")}</button>}
          </div>
          {children}
        </>
      ) : (
        <Platzhalter text={platzhalter} onHochladen={onHochladen} />
      )}
    </div>
  );
});

export default Buehne;
