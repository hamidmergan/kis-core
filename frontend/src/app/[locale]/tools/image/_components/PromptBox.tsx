"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy } from "@phosphor-icons/react";
import type { BildErgebnis } from "./useBildAuftraege";
import { kopieren, pixelText } from "../_utils";

/** Style, format, pixels and quality in one line, only what the backend stored for this picture. */
function useAngabenZeile(bild: BildErgebnis): string {
  const t = useTranslations("tools.image.options");
  const a = bild.angaben ?? {};
  const teile = [
    a.stil && a.stil !== "keiner" && t.has(`styles.${a.stil}`) ? t(`styles.${a.stil}`) : "",
    a.format === "vorlage" ? t("formats.vorlage") : a.format ?? "",
    a.groesse ? pixelText(a.groesse) : "",
    a.qualitaet && t.has(`qualities.${a.qualitaet}`) ? t(`qualities.${a.qualitaet}`) : "",
  ];
  return teile.filter(Boolean).join(", ");
}

/** What a picture was made from, a click anywhere on the box copies the prompt. */
export default function PromptBox({ bild }: { bild: BildErgebnis }) {
  const t = useTranslations("tools.image.result");
  const [kopiert, setKopiert] = useState(false);
  const angaben = useAngabenZeile(bild);

  if (!bild.jobUuid) {
    return (
      <div className="rounded-md border-2 border-border-soft bg-background p-3">
        <p className="text-xs font-semibold text-muted mb-1">{t("ownImage")}</p>
        <p className="break-words text-sm text-foreground">{bild.filename}</p>
      </div>
    );
  }
  if (!bild.beschreibung) return null;
  const prompt = bild.beschreibung;
  const anModell = bild.modellPrompt && bild.modellPrompt.trim() !== prompt.trim() ? bild.modellPrompt : "";

  const klick = async () => {
    await kopieren(prompt);
    setKopiert(true);
    setTimeout(() => setKopiert(false), 1500);
  };

  return (
    <div>
      <button type="button" onClick={klick} title={t("copyPrompt")}
        className="block w-full cursor-copy rounded-md border-2 border-border-soft bg-background p-3 text-left transition-colors hover:border-kb">
        <span className="mb-1 flex items-center justify-between gap-2">
          <span className="text-xs font-semibold text-muted">{bild.bearbeitet ? t("promptEdit") : t("prompt")}</span>
          {kopiert && <span className="text-xs text-success" aria-live="polite">{t("copied")}</span>}
        </span>
        <span className="block whitespace-pre-wrap break-words text-sm text-foreground">
          {prompt}
          <span className="ml-1.5 inline-flex align-[-2px] text-muted-soft">
            {kopiert ? <Check size={14} weight="bold" className="text-success" /> : <Copy size={14} />}
          </span>
        </span>
        {angaben && <span className="mt-2 block text-xs text-muted">{angaben}</span>}
      </button>
      {anModell && (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-medium text-muted">{t("modelPrompt")}</summary>
          <p className="mt-1 whitespace-pre-wrap break-words text-xs text-foreground-soft">{anModell}</p>
        </details>
      )}
    </div>
  );
}
