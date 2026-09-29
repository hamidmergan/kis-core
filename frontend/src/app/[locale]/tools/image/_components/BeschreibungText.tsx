"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { kopieren as inZwischenablage, speichern } from "../_utils";

interface Props {
  beschreibung: string;
  modellPrompt?: string;
  dateiname: string;
}

const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";

/** The description a picture was made from, readable, copyable and as a text file. */
export default function BeschreibungText({ beschreibung, modellPrompt, dateiname }: Props) {
  const t = useTranslations("tools.image.result");
  const [kopiert, setKopiert] = useState(false);
  const anModell = modellPrompt && modellPrompt.trim() !== beschreibung.trim() ? modellPrompt : "";
  const text = anModell ? `${t("description")}:\n${beschreibung}\n\n${t("modelPrompt")}:\n${anModell}` : beschreibung;

  const kopieren = async () => {
    await inZwischenablage(text);
    setKopiert(true);
    setTimeout(() => setKopiert(false), 1500);
  };

  return (
    <div className="mt-2 rounded-md border border-border-soft bg-background p-3">
      <p className="text-xs font-semibold text-muted mb-1">{t("description")}</p>
      <p className="whitespace-pre-wrap break-words text-sm text-foreground">{beschreibung}</p>
      {anModell && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-muted">{t("modelPrompt")}</summary>
          <p className="mt-1 whitespace-pre-wrap break-words text-xs text-foreground-soft">{anModell}</p>
        </details>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <button type="button" className={KNOPF} onClick={kopieren}>{kopiert ? t("copied") : t("copyText")}</button>
        <button type="button" className={KNOPF}
          onClick={() => speichern(new Blob([text], { type: "text/plain" }), `${dateiname.replace(/\.[^.]+$/, "")}.txt`)}>
          {t("download", { format: "TXT" })}
        </button>
      </div>
    </div>
  );
}
