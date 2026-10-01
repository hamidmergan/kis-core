"use client";

import { useState } from "react";
import { ArrowDown, ArrowRight, ArrowUp, CaretDown, Image as ImageIcon, Plus, Trash } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import IconButton from "@/components/ui/IconButton";
import StatusMark from "@/components/ui/StatusMark";
import { MOCK_SLIDES, MOCK_SLIDE_COUNT, VORLAGEN, type MockSlide } from "../_data";

interface Props {
  onNext: () => void;
}

/** Grey bar for text not written yet, copied verbatim from FolienSkizze.tsx. */
function Balken({ className = "" }: { className?: string }) {
  return <span aria-hidden="true" className={`block h-2 rounded-sm bg-surface-dim ${className}`} />;
}

/** Small slide sketch with accent bar and bullets, same aspect ratio as the real preview. */
function Skizze({ slide }: { slide: MockSlide }) {
  return (
    <div className="w-full lg:w-80 aspect-video overflow-hidden rounded-lg border border-border-soft bg-background shadow-sm flex flex-col">
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

/** Step 2: the existing expandable slide list, sketch with actions left and notes right. */
export default function FolienSchritt({ onNext }: Props) {
  const [offen, setOffen] = useState<Set<string>>(() => new Set(["s2"]));
  const [notizenEin, setNotizenEin] = useState(true);
  const [notizMobil, setNotizMobil] = useState<Set<string>>(() => new Set());
  const ids = MOCK_SLIDES.map((s) => s.id);
  const alleOffen = ids.every((id) => offen.has(id));
  const teilweiseOffen = !alleOffen && ids.some((id) => offen.has(id));

  const umschalten = (setter: typeof setOffen, id: string) => setter((alt) => {
    const neu = new Set(alt);
    if (!neu.delete(id)) neu.add(id);
    return neu;
  });

  return (
    <section>
      <div className="flex items-start justify-between gap-4 flex-wrap mb-5" aria-live="polite">
        <div>
          <h2 className="text-base lg:text-lg font-bold">
            <StatusMark tone="success" className="text-inherit">Vorschau bereit</StatusMark>
          </h2>
          <p className="text-xs lg:text-sm text-muted mt-1">
            {MOCK_SLIDE_COUNT} Folien<span className="hidden lg:inline">, lässt sich jetzt noch anpassen, bevor du fertigstellst.</span>
          </p>
        </div>
        <div className="hidden lg:flex items-center gap-5">
          <Checkbox checked={notizenEin} onChange={setNotizenEin} label="Sprechernotizen einschließen" labelClassName="text-sm text-foreground" />
          <Checkbox
            checked={alleOffen}
            indeterminate={teilweiseOffen}
            label="Alle aufklappen"
            labelClassName="text-sm text-foreground"
            onChange={(auf) => setOffen(auf ? new Set(ids) : new Set())}
          />
        </div>
      </div>

      <ol className="folien-liste">
        {MOCK_SLIDES.map((slide, i) => {
          const istOffen = offen.has(slide.id);
          const aktionen = (
            <>
              <IconButton size="sm" aria-label="Bild neu erzeugen"><ImageIcon className="w-3 h-3" /></IconButton>
              <span className="hidden lg:contents">
                <IconButton size="sm" aria-label="Nach oben" disabled={i === 0}><ArrowUp className="w-3 h-3" /></IconButton>
                <IconButton size="sm" aria-label="Nach unten" disabled={i >= MOCK_SLIDES.length - 1}><ArrowDown className="w-3 h-3" /></IconButton>
              </span>
              <IconButton size="sm" aria-label="Danach einfügen"><Plus className="w-3 h-3" /></IconButton>
              <IconButton size="sm" aria-label="Löschen"><Trash className="w-3 h-3" /></IconButton>
            </>
          );
          return (
            <li key={slide.id} className={`folien-zeile ${istOffen ? "offen" : ""}`}>
              <button
                type="button"
                onClick={() => umschalten(setOffen, slide.id)}
                aria-expanded={istOffen}
                aria-controls={`folie-panel-${slide.id}`}
                className="folien-kopf py-3.5 text-sm"
              >
                <span className="folien-rand">
                  <span className="text-sm font-medium whitespace-nowrap">Folie {i + 1}</span>
                  <span className="text-3xs uppercase tracking-wide text-muted whitespace-nowrap">{slide.role}</span>
                </span>
                <span className="folien-titel flex items-center gap-2.5 min-w-0">
                  <span className="truncate">{slide.title}</span>
                  {slide.imageMissing && <StatusMark tone="warn" className="text-2xs flex-shrink-0">Bild fehlt</StatusMark>}
                </span>
                <span className="row-caret" aria-hidden="true">
                  <CaretDown size={14} weight="bold" className={`transition-transform ${istOffen ? "rotate-180" : ""}`} />
                </span>
              </button>

              {istOffen && (
                <div id={`folie-panel-${slide.id}`} className="pb-4 animate-[fadeIn_0.2s_ease-out]">
                  <div className="flex flex-col lg:flex-row lg:items-start gap-3 lg:gap-6">
                    <div className="flex flex-col gap-2.5 lg:shrink-0">
                      <Skizze slide={slide} />
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex flex-wrap gap-1.5">{aktionen}</div>
                        <button
                          type="button"
                          onClick={() => umschalten(setNotizMobil, slide.id)}
                          className="lg:hidden text-xs text-kb underline"
                        >
                          Notiz bearbeiten
                        </button>
                      </div>
                    </div>
                    <div className={`flex-1 min-w-0 ${notizenEin ? "lg:block" : "lg:hidden"} ${notizMobil.has(slide.id) ? "block" : "hidden"}`}>
                      <span className="text-sm font-medium">Sprechernotizen</span>
                      <p className="mt-1.5 min-h-[9rem] px-3 py-2.5 text-sm text-foreground-soft border-2 border-transparent rounded-md bg-background">
                        {slide.notes}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </li>
          );
        })}

        {/* The last slide is still being written: skeleton instead of a title, not expandable. */}
        <li className="folien-zeile">
          <div className="folien-kopf py-3.5 text-sm">
            <span className="folien-rand">
              <span className="text-sm font-medium whitespace-nowrap">Folie {MOCK_SLIDE_COUNT}</span>
            </span>
            <span className="folien-titel"><Balken className="h-2.5 w-1/2" /></span>
          </div>
        </li>
      </ol>

      <div className="hidden lg:flex justify-end mt-7">
        <button type="button" onClick={onNext} className="px-5 py-2.5 btn-primary text-sm font-medium rounded-md transition-colors inline-flex items-center gap-2">
          Fertigstellen
          <ArrowRight size={14} weight="bold" />
        </button>
      </div>

      <div className="lg:hidden h-20" aria-hidden="true" />
      <div className="lg:hidden fixed inset-x-0 bottom-0 border-t border-border-soft bg-background px-4 py-3">
        <button type="button" onClick={onNext} className="w-full px-5 py-3 btn-primary text-sm font-semibold rounded-lg transition-colors flex items-center justify-center gap-2">
          Fertigstellen
          <ArrowRight size={14} weight="bold" />
        </button>
      </div>
    </section>
  );
}
