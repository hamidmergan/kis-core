"use client";

import { useRef, useState } from "react";
import { X } from "@phosphor-icons/react";
import Tabs from "@/components/ui/Tabs";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import { VORLAGEN } from "../_data";

// Wortwoertlich aus _components/VorlageHochladen.tsx der echten Praesentation.
const FIELD =
  "w-full px-3 py-2 text-sm border border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";

type Quelle = "dateien" | "workspace";

interface Props {
  onNext: () => void;
}

/** Schritt 1: Material, Vorlage und Einstellungen. Die Buehne rechts zeigt die Vorlage als Vorschau,
 *  auf dem Handy wandert sie ueber das Formular (gleicher Kniff wie bei tools/image). */
export default function InhaltSchritt({ onNext }: Props) {
  const [quelle, setQuelle] = useState<Quelle>("dateien");
  const [dateien, setDateien] = useState<File[]>([]);
  const [vorlage, setVorlage] = useState(0);
  const [sprache, setSprache] = useState<"de" | "en">("de");
  const [redner, setRedner] = useState("");
  const [anweisungen, setAnweisungen] = useState("");
  const [notizen, setNotizen] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);

  const aktiv = VORLAGEN[vorlage];

  const dateienHinzufuegen = (liste: FileList | null) => {
    if (!liste) return;
    setDateien((alt) => [...alt, ...Array.from(liste)]);
  };

  return (
    <section>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]">
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
          <Tabs
            variant="pill"
            className="mb-4"
            active={quelle}
            onChange={setQuelle}
            items={[{ key: "dateien", label: "Dateien" }, { key: "workspace", label: "Workspace" }]}
          />

          {quelle === "dateien" ? (
            <>
              <div
                role="button"
                tabIndex={0}
                aria-label="Dateien auswählen"
                onClick={() => inputRef.current?.click()}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    inputRef.current?.click();
                  }
                }}
                className="border-2 border-dashed border-border hover:border-kb rounded-lg px-6 py-10 text-center transition-colors cursor-pointer"
              >
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.pptx,.txt,.md"
                  className="hidden"
                  aria-hidden="true"
                  onChange={(e) => {
                    dateienHinzufuegen(e.target.files);
                    e.target.value = "";
                  }}
                />
                <svg className="w-8 h-8 text-muted-soft mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-foreground-soft">
                  Dateien hierher ziehen oder <span className="text-kb font-medium">auswählen</span>
                </p>
                <p className="text-xs text-muted-soft mt-1">.pdf, .docx, .pptx, .txt, .md</p>
              </div>
              {dateien.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {dateien.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="rounded-lg border border-border-soft px-3 py-2 text-sm flex items-center justify-between gap-3">
                      <span className="truncate">{f.name}</span>
                      <button
                        type="button"
                        aria-label={`${f.name} entfernen`}
                        onClick={() => setDateien((alt) => alt.filter((_, j) => j !== i))}
                        className="text-muted hover:text-foreground flex-shrink-0"
                      >
                        <X size={12} weight="bold" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            <EmptyState size="sm" text="Noch kein Workspace ausgewählt." />
          )}

          <div className="mt-6">
            <p className="text-sm font-medium text-foreground mb-2">Vorlage</p>
            <div className="flex gap-2 overflow-x-auto pb-1" role="radiogroup" aria-label="Vorlage">
              {VORLAGEN.map((v, i) => {
                const gewaehlt = i === vorlage;
                return (
                  <button
                    key={v.id}
                    type="button"
                    role="radio"
                    aria-checked={gewaehlt}
                    aria-label={v.name}
                    onClick={() => setVorlage(i)}
                    className={`flex-shrink-0 w-20 rounded-lg border-2 overflow-hidden transition-colors ${gewaehlt ? "border-kb" : "border-border hover:border-kb"}`}
                  >
                    <span className="block h-1.5 w-full" style={{ backgroundColor: v.accent }} />
                    <span className="flex flex-col gap-1 p-2 bg-surface">
                      <span className="block h-1 w-3/5 rounded-sm bg-border" />
                      <span className="block h-1 w-2/5 rounded-sm bg-border" />
                    </span>
                  </button>
                );
              })}
            </div>
            <p className="text-xs text-muted mt-1.5">{aktiv.name}</p>
          </div>

          <label className="block mt-6 text-sm">
            <span className="font-medium">Sprache</span>
            <Select
              className="mt-1"
              value={sprache}
              onChange={setSprache}
              ariaLabel="Sprache"
              options={[{ value: "de", label: "Deutsch" }, { value: "en", label: "English" }]}
            />
          </label>

          <label className="block mt-6 text-sm">
            <span className="font-medium">Redner/in</span>
            <input
              type="text"
              className={`${FIELD} mt-1`}
              value={redner}
              onChange={(e) => setRedner(e.target.value)}
              placeholder="Dein Name (optional)"
            />
          </label>

          <label className="block mt-6 text-sm">
            <span className="font-medium">Anweisungen</span>
            <textarea
              className={`${FIELD} mt-1 resize-y`}
              rows={3}
              value={anweisungen}
              onChange={(e) => setAnweisungen(e.target.value)}
              placeholder="z. B. Fokus auf Studierende im ersten Semester"
            />
          </label>

          <Checkbox
            className="mt-6"
            checked={notizen}
            onChange={setNotizen}
            label="Sprechernotizen miterzeugen"
            labelClassName="text-sm text-foreground"
          />
          <p className="text-xs text-muted mt-1">Zusätzlicher Text zum Vorlesen neben den Folien.</p>

          {/* Auf dem Handy steckt der Knopf unten fest, hier reicht die normale Stelle im Formular. */}
          <button
            type="button"
            onClick={onNext}
            className="hidden lg:inline-flex mt-6 px-5 py-2 btn-primary text-sm font-medium rounded-md transition-colors"
          >
            Erstellen
          </button>
        </section>

        {/* Auf dem Handy steht die Buehne vor dem Formular, am Bildschirm daneben – wie bei tools/image. */}
        <section className="min-w-0 order-first lg:order-none">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5">
            <div className="mx-auto max-w-xl aspect-video rounded-md border border-border-soft bg-background overflow-hidden flex flex-col">
              <span className="block h-1.5 w-full" style={{ backgroundColor: aktiv.accent }} />
              <div className="flex-1 flex flex-col justify-center gap-3 p-6 sm:p-8">
                <p className="text-lg sm:text-xl font-bold text-foreground">Ihr Thema in einem Satz</p>
                {["Erster Kernpunkt", "Zweiter Kernpunkt", "Dritter Kernpunkt"].map((b) => (
                  <div key={b} className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-border flex-shrink-0" />
                    <span className="text-sm text-foreground-soft">{b}</span>
                  </div>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted text-center mt-3">Vorschau · {aktiv.name}</p>
            <p className="text-sm text-foreground-soft text-center mt-3 max-w-md mx-auto">
              So könnte deine erste Folie aussehen. Im nächsten Schritt lassen sich Gliederung und Folien noch anpassen.
            </p>
          </div>
        </section>
      </div>

      {/* Fixierter Knopf nur am Handy, damit er ohne Scrollen erreichbar bleibt. */}
      <div className="lg:hidden h-20" aria-hidden="true" />
      <div className="lg:hidden fixed inset-x-0 bottom-0 border-t border-border-soft bg-background p-4">
        <button type="button" onClick={onNext} className="w-full px-5 py-2.5 btn-primary text-sm font-medium rounded-md transition-colors">
          Erstellen
        </button>
      </div>
    </section>
  );
}
