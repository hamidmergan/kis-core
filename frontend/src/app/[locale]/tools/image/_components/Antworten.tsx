"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import BildInfo from "./BildInfo";
import type { Antwort } from "./useBildFragen";
import { kopieren as inZwischenablage, speichern } from "../_utils";

const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";
const FELD = "w-full rounded-md border-2 border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-soft hover:border-kb focus:outline-none focus:border-kb transition-colors";

/** The answers about the large picture, while describing with a further question below them. */
export default function Antworten({ antworten, laeuft, label, fehler, dateiname, onNachfrage }: {
  antworten: Antwort[];
  laeuft: boolean;
  label: string;
  fehler: string;
  dateiname: string;
  /** Only while describing, the other tasks just show the answers. */
  onNachfrage?: (text: string) => Promise<boolean>;
}) {
  const t = useTranslations("tools.image.analyze");
  const tResult = useTranslations("tools.image.result");
  const [kopiert, setKopiert] = useState<number | null>(null);
  const [nachfrage, setNachfrage] = useState("");

  const kopieren = async (i: number, text: string) => {
    await inZwischenablage(text);
    setKopiert(i);
    setTimeout(() => setKopiert(null), 1500);
  };
  const fragen = async () => {
    if (!nachfrage.trim() || laeuft || !onNachfrage) return;
    if (await onNachfrage(nachfrage)) setNachfrage("");
  };
  const alsText = () => antworten.map((a) => `${a.frage}\n\n${a.text}`).join("\n\n\n");

  return (
    <div className="mt-3 space-y-3">
      {antworten.map((a, i) => (
        <article key={a.jobUuid} className="rounded-md border-2 border-border-soft bg-background p-3">
          <div className="mb-1 flex items-start justify-between gap-2">
            <p className="text-xs font-semibold text-muted">{a.frage}</p>
            <BildInfo jobUuid={a.jobUuid} art="analyze" />
          </div>
          <p className="whitespace-pre-wrap break-words text-sm text-foreground">{a.text}</p>
          <button type="button" className={`${KNOPF} mt-2`} onClick={() => kopieren(i, a.text)}>
            {kopiert === i ? t("copied") : t("copy")}
          </button>
        </article>
      ))}
      {laeuft && <Spinner label={label} />}
      {laeuft && <BackgroundHint className="" />}
      {fehler && <p className="text-sm text-error" role="alert">{fehler}</p>}
      {!antworten.length && !laeuft && !fehler && onNachfrage && <p className="text-sm text-muted">{t("empty")}</p>}
      {antworten.length > 0 && (
        <div>
          <button type="button" className={`${KNOPF} ${onNachfrage ? "mb-3" : ""}`}
            onClick={() => speichern(new Blob([alsText()], { type: "text/plain" }), `${dateiname.replace(/\.[^.]+$/, "")}_analyse.txt`)}>
            {tResult("download", { format: "TXT" })}
          </button>
          {onNachfrage && (
            <>
              <label htmlFor="bild-nachfrage" className="block text-sm font-medium text-foreground-soft mb-1">{t("followUp")}</label>
              <div className="flex gap-2">
                <input id="bild-nachfrage" value={nachfrage} onChange={(e) => setNachfrage(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") void fragen(); }} className={FELD} disabled={laeuft} />
                <button type="button" onClick={() => void fragen()} disabled={laeuft || !nachfrage.trim()}
                  className="px-4 py-2 btn-primary text-sm font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed">
                  {t("followUpSubmit")}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
