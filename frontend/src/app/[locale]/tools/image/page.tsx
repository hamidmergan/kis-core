"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import Tabs from "@/components/ui/Tabs";
import GenerateTab from "./_tabs/GenerateTab";
import EditTab from "./_tabs/EditTab";
import AnalyzeTab, { type FrageStart } from "./_tabs/AnalyzeTab";
import Antworten from "./_components/Antworten";
import BilderLeiste from "./_components/BilderLeiste";
import Buehne from "./_components/Buehne";
import LoeschenDialog from "./_components/LoeschenDialog";
import PromptBox from "./_components/PromptBox";
import PromptFeld, { usePromptEntwurf } from "./_components/PromptFeld";
import { useBildAuftraege, type BildErgebnis } from "./_components/useBildAuftraege";
import { useBilder } from "./_components/useBilder";
import { useBildFragen } from "./_components/useBildFragen";
import { validateImageFile } from "./_utils";

type Tab = "generate" | "edit" | "analyze";

/** One large picture on the right for all three tasks, the settings of the open task on the left, all pictures below. */
export default function ImagePage() {
  const t = useTranslations("tools.image");
  const tt = useTranslations("tools.image.tabs");
  const tCommon = useTranslations("common");
  const [tab, setTab] = useState<Tab>("generate");
  // Nothing is chosen on arrival, the large picture starts as an empty placeholder.
  const [gewaehlt, setGewaehlt] = useState("");
  const [offen, setOffen] = useState(true);
  const [uploadFehler, setUploadFehler] = useState("");
  const [loeschen, setLoeschen] = useState<{ bild: BildErgebnis; laeuft: boolean; fehler: string } | null>(null);
  const bilder = useBilder();
  const erzeugen = useBildAuftraege(t("generate.spinner"), t("generate.longRunning"), tCommon("unknownError"));
  const bearbeiten = useBildAuftraege(t("edit.spinner"), t("edit.longRunning"), tCommon("unknownError"));
  const entwurf = usePromptEntwurf(erzeugen.setFehler);
  const fragen = useBildFragen(t("analyze.spinner"), t("analyze.longRunning"), tCommon("unknownError"));
  const buehne = useRef<HTMLDivElement>(null);

  const bild = bilder.alle.find((b) => b.key === gewaehlt) ?? null;
  const { vorlageLaden } = bilder;
  useEffect(() => { if (bild) void vorlageLaden(bild); }, [bild, vorlageLaden]);

  // On a phone the form sits above the result, so a finished task scrolls down to it.
  const zumErgebnis = useCallback(() => {
    if (window.innerWidth < 1024) setTimeout(() => buehne.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  }, []);

  const wechseln = (neu: Tab) => {
    setTab(neu);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const { aufnehmen } = bilder;
  const neuesBild = useCallback((neu: BildErgebnis, erstes: boolean) => {
    aufnehmen(neu);
    if (erstes) {
      setGewaehlt(neu.key);
      zumErgebnis();
    }
  }, [aufnehmen, zumErgebnis]);

  const startErzeugen = (formular: FormData) => {
    void erzeugen.starte("/image/generate", formular, neuesBild);
  };

  const startBearbeiten = (formular: FormData) => {
    if (!bild) return;
    const quelle = bild.blob;
    void bearbeiten.starte("/image/edit", formular, (neu, erstes) =>
      neuesBild({ ...neu, bearbeitet: true, vorlageUrl: URL.createObjectURL(quelle) }, erstes));
  };

  const startFragen = async (frage: FrageStart) => {
    if (!bild) return;
    if (await fragen.fragen(bild, frage, false)) zumErgebnis();
  };

  const hochladen = (datei: File) => {
    const fehler = validateImageFile(datei, tCommon);
    setUploadFehler(fehler ?? "");
    if (!fehler) setGewaehlt(bilder.hochladen(datei));
  };

  const loeschenBestaetigt = async () => {
    if (!loeschen) return;
    setLoeschen({ ...loeschen, laeuft: true, fehler: "" });
    try {
      await bilder.loeschen(loeschen.bild);
      setGewaehlt("");
      setLoeschen(null);
    } catch {
      setLoeschen({ ...loeschen, laeuft: false, fehler: tCommon("unknownError") });
    }
  };

  const band = { offen, onToggle: () => setOffen((o) => !o) };
  const erzeugtGerade = erzeugen.laeuft || bearbeiten.laeuft;
  const meldungen = [
    erzeugen.fehler,
    bearbeiten.fehler,
    uploadFehler,
    erzeugen.teilweise ? t("result.partial", erzeugen.teilweise) : "",
  ].filter(Boolean);

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8" data-tour="tool-image">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>

        <Tabs
          className="mb-6"
          active={tab}
          onChange={wechseln}
          items={[
            { key: "generate", label: tt("generate") },
            { key: "edit", label: tt("edit") },
            { key: "analyze", label: tt("analyze") },
          ]}
        />

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]">
          <section className="min-w-0">
            <div className={tab === "generate" ? "" : "hidden"}>
              <GenerateTab {...band} entwurf={entwurf} laeuft={erzeugen.laeuft} onStart={startErzeugen} />
            </div>
            <div className={tab === "edit" ? "" : "hidden"}>
              <EditTab {...band} bild={bild} laeuft={bearbeiten.laeuft} onStart={startBearbeiten} />
            </div>
            <div className={tab === "analyze" ? "" : "hidden"}>
              <AnalyzeTab {...band} bild={bild} laeuft={fragen.laeuft} onStart={(f) => void startFragen(f)} />
            </div>
          </section>

          {/* While creating the prompt stands where the new picture will appear. On a phone this side leads. */}
          <section className="min-w-0 order-first lg:order-none lg:col-start-2 lg:row-start-1">
            {tab === "generate" && !bild && !erzeugtGerade ? (
              <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5">
                {meldungen.map((m) => <p key={m} className="mb-3 text-sm text-error" role="alert">{m}</p>)}
                <PromptFeld entwurf={entwurf} />
              </div>
            ) : (
              <Buehne
                ref={buehne}
                bild={bild}
                laeuft={erzeugtGerade}
                label={erzeugen.laeuft ? erzeugen.label : bearbeiten.label}
                meldungen={meldungen}
                platzhalter={tab === "generate" ? "" : t(`placeholder.${tab}`)}
                onHochladen={tab === "generate" ? undefined : hochladen}
                onLoeschen={() => bild && setLoeschen({ bild, laeuft: false, fehler: "" })}
                onNeu={tab === "generate" ? () => setGewaehlt("") : undefined}
              >
                {bild && (tab === "analyze" ? (
                  <Antworten
                    antworten={fragen.antworten[bild.key] ?? []}
                    laeuft={fragen.laeuft}
                    label={fragen.label}
                    fehler={fragen.fehler}
                    dateiname={bild.filename}
                    onNachfrage={(text) => fragen.nachfragen(bild, text)}
                  />
                ) : (
                  <div className="mt-3"><PromptBox bild={bild} /></div>
                ))}
              </Buehne>
            )}
          </section>
        </div>

        <BilderLeiste bilder={bilder.alle} gewaehlt={gewaehlt}
          onWaehlen={(key) => setGewaehlt((g) => (g === key ? "" : key))} />

        {loeschen && (
          <LoeschenDialog
            name={loeschen.bild.beschreibung ?? loeschen.bild.filename}
            loescht={loeschen.laeuft}
            fehler={loeschen.fehler}
            onAbbrechen={() => setLoeschen(null)}
            onLoeschen={() => void loeschenBestaetigt()}
          />
        )}
      </div>
    </ProtectedRoute>
  );
}
