"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, CaretDown, Image as ImageIcon, Plus, Trash } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { MOCK_SLIDES, MOCK_SLIDE_COUNT, VORLAGEN, type MockSlide } from "../_data";

interface Props {
  onBack: () => void;
  onNext: () => void;
}

/** Ein grauer Balken fuer Text, der noch nicht geschrieben ist. Wortwoertlich aus FolienSkizze.tsx. */
function Balken({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`block h-2 rounded-sm bg-surface-dim ${className}`} />;
}

/** Kleine Folien-Skizze: Akzentbalken plus Aufzaehlung, im selben Seitenverhaeltnis wie die echte Vorschau. */
function Skizze({ slide }: { slide: MockSlide }) {
  return (
    <div className="w-full sm:w-80 sm:shrink-0 aspect-video overflow-hidden rounded-md border-2 border-border bg-background flex flex-col">
      <span className="block h-1 w-full flex-shrink-0" style={{ backgroundColor: VORLAGEN[0].accent }} />
      <div className="flex-1 min-h-0 flex flex-col justify-center gap-1.5 p-4">
        <p className="text-sm font-bold text-foreground leading-snug line-clamp-2">{slide.title}</p>
        <ul className="list-disc pl-3.5 space-y-0.5 text-2xs text-foreground-soft">
          {slide.bullets.map((b) => <li key={b}>{b}</li>)}
        </ul>
      </div>
    </div>
  );
}

/** Schritt 2: die aufklappbare Liste bleibt die bestehende Darstellung (folien-zeile aus globals.css),
 *  nur die beiden Spalten innen – Skizze und Notizen – stapeln sich wie im Original ab sm automatisch. */
export default function FolienSchritt({ onBack, onNext }: Props) {
  const [offen, setOffen] = useState<Set<string>>(() => new Set(["s2"]));
  const [notizenEin, setNotizenEin] = useState(true);
  const zeilen = [...MOCK_SLIDES.map((s) => s.id), "skeleton"];
  const alleOffen = zeilen.every((id) => offen.has(id) || id === "skeleton");
  const teilweiseOffen = !alleOffen && zeilen.some((id) => offen.has(id));

  const umschalten = (id: string) => setOffen((alt) => {
    const neu = new Set(alt);
    if (!neu.delete(id)) neu.add(id);
    return neu;
  });

  return (
    <section>
      <div className="flex items-center gap-3 flex-wrap" aria-live="polite">
        <h2 className="text-lg font-bold">
          <StatusMark tone="success" className="text-inherit">Vorschau bereit</StatusMark>
        </h2>
        <span className="text-sm text-muted">{MOCK_SLIDE_COUNT} Folien</span>
      </div>
      <p className="text-sm text-foreground-soft mt-2">Lässt sich jetzt noch anpassen, bevor du fertigstellst.</p>

      <div className="mt-8 flex items-center justify-end gap-x-5 gap-y-2 flex-wrap">
        <Checkbox checked={notizenEin} onChange={setNotizenEin} label="Sprechernotizen einschließen" labelClassName="text-sm text-foreground" />
        <Checkbox
          checked={alleOffen}
          indeterminate={teilweiseOffen}
          label="Alle aufklappen"
          labelClassName="text-sm text-foreground"
          onChange={(auf) => setOffen(auf ? new Set(zeilen) : new Set())}
        />
      </div>

      <ol className="mt-3 folien-liste">
        {MOCK_SLIDES.map((slide, i) => {
          const istOffen = offen.has(slide.id);
          return (
            <li key={slide.id} className={`folien-zeile ${istOffen ? "offen" : ""}`}>
              <button
                type="button"
                onClick={() => umschalten(slide.id)}
                aria-expanded={istOffen}
                aria-controls={`folie-panel-${slide.id}`}
                className="folien-kopf py-3.5 text-sm"
              >
                <span className="folien-rand">
                  <span className="text-sm font-medium whitespace-nowrap">Folie {i + 1}</span>
                  <span className="text-3xs uppercase tracking-wide text-muted whitespace-nowrap">{slide.role}</span>
                  {slide.imageMissing && <StatusMark tone="warn">Bild fehlt</StatusMark>}
                </span>
                <span className="folien-titel truncate">{slide.title}</span>
                <span className="row-caret" aria-hidden="true">
                  <CaretDown size={14} weight="bold" className={`transition-transform ${istOffen ? "rotate-180" : ""}`} />
                </span>
              </button>

              {istOffen && (
                <div id={`folie-panel-${slide.id}`} className="pb-4 animate-[fadeIn_0.2s_ease-out]">
                  {notizenEin ? (
                    <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                      <Skizze slide={slide} />
                      <div className="flex-1 min-w-0 flex flex-col gap-3.5">
                        <div>
                          <span className="text-sm font-medium">Sprechernotizen</span>
                          <p className="mt-1 px-3 py-2 text-sm text-foreground-soft border-2 border-transparent rounded-md bg-background">
                            {slide.notes}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          <IconButton size="sm" aria-label="Bild neu erzeugen"><ImageIcon className="w-3 h-3" /></IconButton>
                          <IconButton size="sm" aria-label="Nach oben" disabled={i === 0}><ArrowUp className="w-3 h-3" /></IconButton>
                          <IconButton size="sm" aria-label="Nach unten" disabled={i >= MOCK_SLIDES.length - 1}><ArrowDown className="w-3 h-3" /></IconButton>
                          <IconButton size="sm" aria-label="Danach einfügen"><Plus className="w-3 h-3" /></IconButton>
                          <IconButton size="sm" aria-label="Löschen"><Trash className="w-3 h-3" /></IconButton>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-4">
                      <Skizze slide={slide} />
                      <div className="flex flex-wrap gap-1">
                        <IconButton size="sm" aria-label="Bild neu erzeugen"><ImageIcon className="w-3 h-3" /></IconButton>
                        <IconButton size="sm" aria-label="Nach oben" disabled={i === 0}><ArrowUp className="w-3 h-3" /></IconButton>
                        <IconButton size="sm" aria-label="Nach unten" disabled={i >= MOCK_SLIDES.length - 1}><ArrowDown className="w-3 h-3" /></IconButton>
                        <IconButton size="sm" aria-label="Danach einfügen"><Plus className="w-3 h-3" /></IconButton>
                        <IconButton size="sm" aria-label="Löschen"><Trash className="w-3 h-3" /></IconButton>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </li>
          );
        })}

        {/* Die letzte Folie wird noch geschrieben: Skelett statt Titel, nicht aufklappbar. */}
        <li className="folien-zeile">
          <div className="folien-kopf py-3.5 text-sm">
            <span className="folien-rand">
              <span className="text-sm font-medium whitespace-nowrap">Folie {MOCK_SLIDE_COUNT}</span>
              <Balken className="w-12 mt-1" />
            </span>
            <span className="folien-titel"><Balken className="h-3 w-1/2" /></span>
          </div>
        </li>
      </ol>

      <div className="flex gap-3 mt-10">
        <button type="button" onClick={onBack} className="px-4 py-3 text-sm text-foreground-soft border-2 border-border rounded-md hover:border-kb transition-colors">
          Zurück
        </button>
        <button type="button" onClick={onNext} className="hidden lg:block flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md transition-colors">
          Fertigstellen
        </button>
      </div>

      <div className="lg:hidden h-20" aria-hidden="true" />
      <div className="lg:hidden fixed inset-x-0 bottom-0 border-t border-border-soft bg-background p-4">
        <button type="button" onClick={onNext} className="w-full px-5 py-2.5 btn-primary text-sm font-medium rounded-md transition-colors">
          Fertigstellen
        </button>
      </div>
    </section>
  );
}
