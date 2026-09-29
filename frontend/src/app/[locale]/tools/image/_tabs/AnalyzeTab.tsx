"use client";

import { useCallback, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { backendApi, downloadJobAsBlob, parseDetail, pollJob } from "@/lib/api";
import Spinner from "@/components/ui/Spinner";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import Auswahl from "../_components/Auswahl";
import { useZumErgebnis } from "../_components/useZumErgebnis";
import BildWahl from "../_components/BildWahl";
import { AUFGABEN, kopieren as inZwischenablage, speichern, type Uebergabe } from "../_utils";

interface Props {
  uebergabe: Uebergabe | null;
}

interface Antwort {
  frage: string;
  text: string;
}

const FELD = "w-full rounded-md border border-border px-3 py-2 text-sm text-foreground placeholder:text-muted-soft focus:border-kb focus:ring-1 focus:ring-kb focus:outline-none";
const KNOPF = "px-2.5 py-1 text-xs font-medium rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors";

export default function AnalyzeTab({ uebergabe }: Props) {
  const t = useTranslations("tools.image.analyze");
  const tImage = useTranslations("tools.image");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const { providers, providerId, setProviderId } = useFeatureProviders("/image/providers/analyze");
  const [datei, setDatei] = useState<File | null>(null);
  const [aufgabe, setAufgabe] = useState<(typeof AUFGABEN)[number]>("beschreiben");
  const [sprache, setSprache] = useState<"de" | "en">(locale === "en" ? "en" : "de");
  const [frage, setFrage] = useState("");
  const [nachfrage, setNachfrage] = useState("");
  const [antworten, setAntworten] = useState<Antwort[]>([]);
  const [laeuft, setLaeuft] = useState(false);
  const [label, setLabel] = useState(t("spinner"));
  const [fehler, setFehler] = useState("");
  const [kopiert, setKopiert] = useState<number | null>(null);

  const neueDatei = useCallback((f: File) => {
    setDatei(f);
    setAntworten([]);
  }, []);

  const fragen = useCallback(async (welche: (typeof AUFGABEN)[number], text: string, weiter: boolean) => {
    if (!datei || (welche === "frage" && !text.trim())) return;
    setLaeuft(true);
    setLabel(t("spinner"));
    setFehler("");
    try {
      const formular = new FormData();
      formular.append("image", datei);
      formular.append("aufgabe", welche);
      formular.append("sprache", sprache);
      formular.append("prompt", welche === "frage" ? text : "");
      if (providerId != null) formular.append("provider_id", String(providerId));
      const antwort = await backendApi.fetch("/image/analyze", { method: "POST", body: formular });
      if (!antwort.ok) {
        const err = await antwort.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const daten = await antwort.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(daten.job_uuid, undefined, 3000, undefined, () => setLabel(t("longRunning")), 60_000);
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const { blob } = await downloadJobAsBlob(daten.job_uuid);
      const eintrag = { frage: welche === "frage" ? text : t(`tasks.${welche}`), text: await blob.text() };
      setAntworten((alt) => (weiter ? [...alt, eintrag] : [eintrag]));
      if (weiter) setNachfrage("");
    } catch (err) {
      setFehler(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setLaeuft(false);
    }
  }, [datei, sprache, providerId, t, tCommon]);

  const kopieren = async (i: number, text: string) => {
    await inZwischenablage(text);
    setKopiert(i);
    setTimeout(() => setKopiert(null), 1500);
  };

  const alsText = () => antworten.map((a) => `${a.frage}\n\n${a.text}`).join("\n\n\n");
  const stamm = datei?.name.replace(/\.[^.]+$/, "") ?? "bild";

  const ergebnisBereich = useZumErgebnis(antworten.length);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,380px)_1fr]">
      <section className="min-w-0">
        <BildWahl datei={datei} onDatei={neueDatei} onFehler={setFehler} uebergabe={uebergabe} disabled={laeuft}
          label={t("image")} />
        <Auswahl label={t("task")} wert={aufgabe} onChange={setAufgabe} disabled={laeuft}
          optionen={AUFGABEN.map((a) => ({ key: a, label: t(`tasks.${a}`) }))} />
        {aufgabe === "frage" && (
          <textarea value={frage} onChange={(e) => setFrage(e.target.value)} rows={3}
            placeholder={t("questionPlaceholder")} className={`${FELD} mb-4`} />
        )}
        <Auswahl label={t("language")} wert={sprache} onChange={setSprache} disabled={laeuft}
          optionen={(["de", "en"] as const).map((s) => ({ key: s, label: t(`languages.${s}`) }))} />

        <ProviderSelect
          id="image-analyze-provider"
          label={tImage("providerLabel")}
          providers={providers}
          value={providerId}
          onChange={setProviderId}
          disabled={laeuft}
        />

        <button
          onClick={() => fragen(aufgabe, frage, false)}
          disabled={!datei || laeuft || (aufgabe === "frage" && !frage.trim())}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {laeuft ? tCommon("processing") : t("submit")}
        </button>
      </section>

      <section ref={ergebnisBereich} className="min-w-0 scroll-mt-4 self-start rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
        <h2 className="text-sm font-semibold text-foreground mb-3">{tImage("result.title")}</h2>
        {!laeuft && !antworten.length && !fehler && <p className="text-sm text-muted">{tImage("result.empty")}</p>}
        {antworten.map((a, i) => (
          <article key={i} className="mb-4 rounded-lg border border-border-soft bg-background p-4">
            <p className="mb-2 text-xs font-semibold text-muted">{a.frage}</p>
            <p className="whitespace-pre-wrap text-sm text-foreground">{a.text}</p>
            <div className="mt-3 flex gap-1.5">
              <button type="button" className={KNOPF} onClick={() => kopieren(i, a.text)}>
                {kopiert === i ? t("copied") : t("copy")}
              </button>
            </div>
          </article>
        ))}
        {laeuft && <Spinner label={label} className="mb-4" />}
        {laeuft && <BackgroundHint />}
        {fehler && <p className="mb-4 text-sm text-error" role="alert">{fehler}</p>}
        {antworten.length > 0 && (
          <>
            <button type="button" className={`${KNOPF} mb-4`}
              onClick={() => speichern(new Blob([alsText()], { type: "text/plain" }), `${stamm}_analyse.txt`)}>
              {tImage("result.download", { format: "TXT" })}
            </button>
            <label htmlFor="bild-nachfrage" className="block text-sm font-medium text-foreground-soft mb-1">
              {t("followUp")}
            </label>
            <div className="flex gap-2">
              <input id="bild-nachfrage" value={nachfrage} onChange={(e) => setNachfrage(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void fragen("frage", nachfrage, true); }}
                className={FELD} disabled={laeuft} />
              <button type="button" onClick={() => fragen("frage", nachfrage, true)}
                disabled={laeuft || !nachfrage.trim()}
                className="px-4 py-2 btn-primary text-sm font-medium rounded-md disabled:opacity-50 disabled:cursor-not-allowed">
                {t("followUpSubmit")}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
