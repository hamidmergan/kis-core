"use client";

import Spinner from "@/components/ui/Spinner";
import { wordCount } from "@/lib/text";
import type { SlideData } from "@/types";

interface ScriptReviewStepProps {
  slides: SlideData[];
  openAccordion: number;
  editingSlide: number | null;
  editBuffer: string;
  fastMode: boolean;
  regenAnchorSlide: number | null;
  regenAnchorText: string;
  onEditBufferChange: (v: string) => void;
  onLightboxOpen: (index: number) => void;
  onAccordionToggle: (index: number) => void;
  onRegenAnchor: (slide: number | null, text: string) => void;
  onOpenRegen: (index: number) => void;
  onStartEdit: (index: number) => void;
  onCancelEdit: () => void;
  onSaveEdit: (index: number) => void;
  onAcceptScripts: () => void;
}

export default function ScriptReviewStep({
  slides,
  openAccordion,
  editingSlide,
  editBuffer,
  fastMode,
  regenAnchorSlide,
  regenAnchorText,
  onEditBufferChange,
  onLightboxOpen,
  onAccordionToggle,
  onRegenAnchor,
  onOpenRegen,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onAcceptScripts,
}: ScriptReviewStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Skripte überprüfen und anpassen</h2>
      <p className="text-sm text-gray-500 mb-4">
        Überprüfen Sie die generierten Skripte für jede Folie. Klicken Sie auf den Stift um zu bearbeiten.
      </p>

      <div className="space-y-2 mb-6">
        {slides.map((slide, i) => {
          const isOpen = openAccordion === i;
          const isEditing = editingSlide === i;
          const wc = wordCount(isEditing ? editBuffer : slide.script);
          const preview = slide.script.slice(0, 60) + (slide.script.length > 60 ? "..." : "");

          return (
            <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => onAccordionToggle(i)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                aria-expanded={isOpen}
                aria-controls={`slide-panel-${i}`}
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900">Folie {i + 1}</span>
                  {!isOpen && <span className="ml-2 text-xs text-gray-400 truncate">{preview}</span>}
                </div>
                <svg
                  className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {isOpen && (
                <div id={`slide-panel-${i}`} className="border-t border-gray-200 p-4 animate-[fadeIn_0.2s_ease-out]">
                  <div className="flex flex-col gap-4">
                    {!fastMode && (
                      <div className="flex-shrink-0" style={{ width: "100px" }}>
                        {slide.imageBase64 ? (
                          <button
                            onClick={() => onLightboxOpen(i)}
                            className="w-full rounded border border-gray-200 hover:border-primary transition-colors overflow-hidden cursor-zoom-in focus-visible:outline-2 focus-visible:outline-primary"
                            aria-label={`Folie ${i + 1} vergrößern`}
                          >
                            <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full" />
                          </button>
                        ) : (
                          <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center">
                            <Spinner size="sm" />
                          </div>
                        )}
                      </div>
                    )}

                    <div className="w-full flex flex-col">
                      {isEditing ? (
                        <>
                          <textarea
                            value={editBuffer}
                            onChange={(e) => onEditBufferChange(e.target.value)}
                            rows={8}
                            className="w-full rounded-md border border-primary px-3 py-2 text-sm font-mono text-gray-900 focus:ring-1 focus:ring-primary focus:outline-none"
                            aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                          />
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-xs text-gray-400">ca. {wc} Wörter</span>
                            <div className="flex gap-2">
                              <button
                                onClick={onCancelEdit}
                                className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                              >
                                Abbrechen
                              </button>
                              <button
                                onClick={() => onSaveEdit(i)}
                                className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition-colors"
                              >
                                Speichern
                              </button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs text-gray-400">ca. {wc} Wörter</span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => onOpenRegen(i)}
                                className={`w-7 h-7 flex items-center justify-center rounded-full transition-colors hover:text-primary hover:bg-gray-100 ${regenAnchorSlide === i && regenAnchorText ? "text-primary" : "text-gray-400"}`}
                                aria-label={`Skript für Folie ${i + 1} per KI neu generieren`}
                                title="Mit KI neu generieren"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"
                                  />
                                </svg>
                              </button>
                              <button
                                onClick={() => onStartEdit(i)}
                                className="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-100 transition-colors"
                                aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                  />
                                </svg>
                              </button>
                            </div>
                          </div>
                          <p
                            className="text-sm font-mono text-gray-700 whitespace-pre-wrap leading-relaxed"
                            onMouseUp={() => {
                              const text = window.getSelection()?.toString().trim();
                              onRegenAnchor(text ? i : null, text || "");
                            }}
                          >
                            {slide.script || <span className="text-gray-400 italic">Kein Skript (leere Folie)</span>}
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {slides.filter((s) => !s.script.trim()).length > 0 && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-300 rounded-md px-3 py-2">
          {slides.filter((s) => !s.script.trim()).length} Folie(n) haben kein Skript. Bitte füllen Sie diese aus, bevor Sie fortfahren.
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onAcceptScripts}
          disabled={editingSlide !== null}
          className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          Alle Skripte übernehmen
        </button>
      </div>
    </section>
  );
}
