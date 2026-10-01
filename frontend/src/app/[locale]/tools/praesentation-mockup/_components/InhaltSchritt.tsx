"use client";

import { useRef, useState, type ReactNode } from "react";
import { ArrowRight, CaretDown, X } from "@phosphor-icons/react";
import Tabs from "@/components/ui/Tabs";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import ToggleRow from "@/components/ui/ToggleRow";
import { EmptyState } from "@/components/ui/EmptyState";
import StatusMark from "@/components/ui/StatusMark";
import { LETZTE_PRAESENTATIONEN, MOCK_DATEIEN, VORLAGEN, type MockDatei } from "../_data";

// Copied verbatim from _components/VorlageHochladen.tsx of the real presentation.
const FIELD =
  "w-full px-3 py-2 text-sm border border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";

const SPRACHEN = [{ value: "de" as const, label: "Deutsch" }, { value: "en" as const, label: "English" }];

type Quelle = "dateien" | "workspace";
type MobilZeile = "material" | "sprache" | "redner" | "anweisungen";

interface Props {
  onNext: () => void;
}

function groesse(bytes: number) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Template thumbnail: accent bar on top, two grey lines below. */
function VorlageKarte({ accent, gewaehlt, gross, name, onClick }: { accent: string; gewaehlt: boolean; gross?: boolean; name: string; onClick: () => void }) {
  return (
    <div className={`flex-shrink-0 flex flex-col items-center ${gross ? "w-36 snap-start" : "w-20"}`}>
      <button
        type="button"
        role="radio"
        aria-checked={gewaehlt}
        aria-label={name}
        onClick={onClick}
        className={`w-full aspect-video rounded-lg border-2 overflow-hidden flex flex-col transition-colors ${gewaehlt ? "border-kb bg-kb/5" : "border-border bg-background hover:border-kb"}`}
      >
        <span className={`block w-full ${gross ? "h-2" : "h-1.5"}`} style={{ backgroundColor: accent }} />
        <span className="flex flex-col gap-1 p-2">
          <span className="block h-1 w-3/5 rounded-sm bg-border" />
          <span className="block h-1 w-2/5 rounded-sm bg-border" />
        </span>
      </button>
      <span className={`mt-1 text-2xs text-center ${gewaehlt ? "text-kb font-semibold" : "text-muted"}`}>{name}</span>
    </div>
  );
}

/** Settings row on the phone that opens its field in place. */
function Zeile({ titel, wert, offen, onToggle, children }: { titel: string; wert: string; offen: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <div className="border-b border-border-soft">
      <button type="button" onClick={onToggle} aria-expanded={offen} className="w-full px-4 py-3.5 flex items-center justify-between gap-3 text-left">
        <span className="text-sm font-medium">{titel}</span>
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-sm text-muted truncate">{wert}</span>
          <CaretDown size={14} weight="bold" className={`text-muted flex-shrink-0 transition-transform ${offen ? "rotate-180" : ""}`} />
        </span>
      </button>
      {offen && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

/** Step 1: material, template and settings, two columns on the desktop and a settings list on the phone. */
export default function InhaltSchritt({ onNext }: Props) {
  const [quelle, setQuelle] = useState<Quelle>("dateien");
  const [dateien, setDateien] = useState<MockDatei[]>(MOCK_DATEIEN);
  const [vorlage, setVorlage] = useState(0);
  const [sprache, setSprache] = useState<"de" | "en">("de");
  const [redner, setRedner] = useState("");
  const [anweisungen, setAnweisungen] = useState("");
  const [notizen, setNotizen] = useState(true);
  const [mobilOffen, setMobilOffen] = useState<MobilZeile | null>("material");
  const inputRef = useRef<HTMLInputElement>(null);

  const aktiv = VORLAGEN[vorlage];
  const umschalten = (z: MobilZeile) => setMobilOffen((alt) => (alt === z ? null : z));

  const dateiInput = (
    <input
      ref={inputRef}
      type="file"
      multiple
      accept=".pdf,.docx,.pptx,.txt,.md"
      className="hidden"
      aria-hidden="true"
      onChange={(e) => {
        const liste = e.target.files;
        if (liste) setDateien((alt) => [...alt, ...Array.from(liste).map((f) => ({ name: f.name, groesse: groesse(f.size) }))]);
        e.target.value = "";
      }}
    />
  );

  const dateiListe = dateien.length > 0 && (
    <ul className="mt-3 space-y-2">
      {dateien.map((f, i) => (
        <li key={`${f.name}-${i}`} className="rounded-lg border border-border-soft px-3 py-2 text-sm flex items-center justify-between gap-3">
          <span className="truncate">{f.name}</span>
          <span className="flex items-center gap-2 flex-shrink-0">
            <span className="text-xs text-muted">{f.groesse}</span>
            <button
              type="button"
              aria-label={`${f.name} entfernen`}
              onClick={() => setDateien((alt) => alt.filter((_, j) => j !== i))}
              className="text-muted hover:text-foreground"
            >
              <X size={12} weight="bold" />
            </button>
          </span>
        </li>
      ))}
    </ul>
  );

  return (
    <section>
      {dateiInput}

      {/* Desktop: form card left, stage right. */}
      <div className="hidden lg:grid gap-8 grid-cols-[400px_1fr]">
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-5">
          <Tabs
            variant="pill"
            className="mb-4"
            active={quelle}
            onChange={setQuelle}
            items={[{ key: "dateien", label: "Dateien" }, { key: "workspace", label: "Workspace" }]}
          />

          {quelle === "dateien" ? (
            <>
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="w-full border-2 border-dashed border-border hover:border-kb rounded-lg px-6 py-10 text-center transition-colors"
              >
                <svg className="w-8 h-8 text-muted-soft mb-2 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="text-sm text-foreground-soft">
                  Dateien hierher ziehen oder <span className="text-kb font-medium underline">auswählen</span>
                </p>
                <p className="text-xs text-muted-soft mt-1">.pdf, .docx, .pptx, .txt, .md</p>
              </button>
              {dateiListe}
            </>
          ) : (
            <EmptyState size="sm" text="Noch kein Workspace ausgewählt." />
          )}

          <div className="mt-6">
            <p className="text-sm font-semibold mb-2">Vorlage</p>
            <div className="flex gap-2.5 overflow-x-auto pb-1" role="radiogroup" aria-label="Vorlage">
              {VORLAGEN.map((v, i) => (
                <VorlageKarte key={v.id} accent={v.accent} name={v.name} gewaehlt={i === vorlage} onClick={() => setVorlage(i)} />
              ))}
            </div>
          </div>

          <label className="block mt-6 text-sm">
            <span className="font-medium">Sprache</span>
            <Select className="mt-1" value={sprache} onChange={setSprache} ariaLabel="Sprache" options={SPRACHEN} />
          </label>

          <label className="block mt-6 text-sm">
            <span className="font-medium">Redner/in</span>
            <input type="text" className={`${FIELD} mt-1`} value={redner} onChange={(e) => setRedner(e.target.value)} placeholder="Dein Name (optional)" />
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

          <Checkbox className="mt-6" checked={notizen} onChange={setNotizen} label="Sprechernotizen miterzeugen" labelClassName="text-sm text-foreground" />
          <p className="text-xs text-muted mt-1">Zusätzlicher Text zum Vorlesen neben den Folien.</p>

          <button type="button" onClick={onNext} className="mt-6 px-5 py-2 btn-primary text-sm font-medium rounded-md transition-colors inline-flex items-center gap-2">
            Erstellen
            <ArrowRight size={14} weight="bold" />
          </button>
        </section>

        <section className="min-w-0">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-5 min-h-[35rem] flex flex-col items-center justify-center gap-4">
            <div className="w-full max-w-2xl aspect-video rounded-lg border border-border-soft bg-background shadow-sm overflow-hidden flex flex-col">
              <span className="block h-1.5 w-full" style={{ backgroundColor: aktiv.accent }} />
              <div className="flex-1 flex flex-col justify-center gap-4 p-10">
                <p className="text-2xl font-bold text-foreground">Ihr Thema in einem Satz</p>
                <div className="flex flex-col gap-2.5">
                  {["Erster Kernpunkt", "Zweiter Kernpunkt", "Dritter Kernpunkt"].map((b) => (
                    <div key={b} className="flex items-center gap-2.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-border flex-shrink-0" />
                      <span className="text-base text-foreground-soft">{b}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <p className="w-full max-w-2xl text-xs text-muted">Vorschau: {aktiv.name}</p>
            <p className="text-sm text-foreground-soft text-center max-w-md mt-2">
              So könnte deine erste Folie aussehen. Im nächsten Schritt lassen sich Gliederung und Folien noch anpassen.
            </p>
          </div>
        </section>
      </div>

      <div className="hidden lg:block mt-10">
        <h2 className="text-sm font-semibold">Letzte Präsentationen</h2>
        <p className="text-xs text-muted mt-1 mb-3">Wähle einen Eintrag, um ihn weiter zu bearbeiten.</p>
        <ul className="border-t border-border-soft">
          {LETZTE_PRAESENTATIONEN.map((p) => (
            <li key={p.name} className="flex items-center justify-between gap-4 py-2.5 border-b border-border-soft text-sm">
              <span className="truncate">{p.name}</span>
              <span className="flex items-center gap-4 flex-shrink-0">
                <span className="text-xs text-muted">{p.datum}</span>
                <StatusMark tone="success" className="text-xs">Fertig</StatusMark>
              </span>
            </li>
          ))}
        </ul>
      </div>

      {/* Phone: template carousel, settings as rows, button pinned at the bottom. */}
      <div className="lg:hidden -mx-4">
        <div className="px-4 pb-2">
          <p className="text-xs font-semibold mb-2">Vorlage</p>
          <div className="flex gap-2.5 overflow-x-auto snap-x pb-1" role="radiogroup" aria-label="Vorlage">
            {VORLAGEN.map((v, i) => (
              <VorlageKarte key={v.id} gross accent={v.accent} name={v.name} gewaehlt={i === vorlage} onClick={() => setVorlage(i)} />
            ))}
          </div>
        </div>

        <div className="mt-2 border-t border-border-soft">
          <Zeile titel="Material" wert={`${dateien.length} Dateien`} offen={mobilOffen === "material"} onToggle={() => umschalten("material")}>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="w-full border-2 border-dashed border-border hover:border-kb rounded-lg p-4 text-center transition-colors"
            >
              <p className="text-sm text-foreground-soft">Dateien auswählen</p>
              <p className="text-2xs text-muted-soft mt-1">.pdf, .docx, .pptx, .txt, .md</p>
            </button>
            {dateiListe}
          </Zeile>
          <Zeile titel="Sprache" wert={SPRACHEN.find((s) => s.value === sprache)?.label ?? ""} offen={mobilOffen === "sprache"} onToggle={() => umschalten("sprache")}>
            <Select value={sprache} onChange={setSprache} ariaLabel="Sprache" options={SPRACHEN} />
          </Zeile>
          <Zeile titel="Redner/in" wert={redner || "optional"} offen={mobilOffen === "redner"} onToggle={() => umschalten("redner")}>
            <input type="text" className={FIELD} value={redner} onChange={(e) => setRedner(e.target.value)} placeholder="Dein Name (optional)" aria-label="Redner/in" />
          </Zeile>
          <Zeile titel="Anweisungen" wert={anweisungen || "keine"} offen={mobilOffen === "anweisungen"} onToggle={() => umschalten("anweisungen")}>
            <textarea
              className={`${FIELD} resize-y`}
              rows={3}
              value={anweisungen}
              onChange={(e) => setAnweisungen(e.target.value)}
              placeholder="z. B. Fokus auf Studierende im ersten Semester"
              aria-label="Anweisungen"
            />
          </Zeile>
          <div className="px-4 py-3.5">
            <ToggleRow
              title="Sprechernotizen"
              description="Zusätzlicher Text zum Vorlesen neben den Folien."
              checked={notizen}
              onToggle={() => setNotizen((n) => !n)}
            />
          </div>
        </div>

        <div className="h-28" aria-hidden="true" />
        <div className="fixed inset-x-0 bottom-0 border-t border-border-soft bg-background px-4 pt-2.5 pb-3.5 flex flex-col gap-2">
          <span className="text-xs text-muted">Vorlage: {aktiv.name}</span>
          <button type="button" onClick={onNext} className="w-full px-5 py-3 btn-primary text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2">
            Erstellen
            <ArrowRight size={14} weight="bold" />
          </button>
        </div>
      </div>
    </section>
  );
}
