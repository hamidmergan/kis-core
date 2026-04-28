import Spinner from "@/components/ui/Spinner";
import { wordCount, estimateDuration } from "@/lib/text";
import type { SlideData } from "@/types";


interface ScriptReviewStepProps {
  slides: SlideData[];
  openAccordion: number;
  editingSlide: number | null;
  editBuffer: string;
  fastMode: boolean;
  regeneratingSlide: number | null;
  regenPrompt: string;
  regenProposal: string | null;
  regenLoading: boolean;
  onOpenAccordionChange: (idx: number) => void;
  onEditBufferChange: (text: string) => void;
  onStartEdit: (idx: number) => void;
  onCancelEdit: () => void;
  onSaveEdit: (idx: number) => void;
  onOpenRegen: (idx: number) => void;
  onCloseRegen: () => void;
  onRegenPromptChange: (text: string) => void;
  onRegenProposalChange: (text: string) => void;
  onRunRegen: (idx: number) => void;
  onApplyRegen: (idx: number) => void;
  onAcceptScripts: () => void;
}


export function ScriptReviewStep({
  slides, openAccordion, editingSlide, editBuffer, fastMode,
  regeneratingSlide, regenPrompt, regenProposal, regenLoading,
  onOpenAccordionChange, onEditBufferChange, onStartEdit, onCancelEdit, onSaveEdit,
  onOpenRegen, onCloseRegen, onRegenPromptChange, onRegenProposalChange, onRunRegen, onApplyRegen,
  onAcceptScripts,
}: ScriptReviewStepProps) {
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-1">Skripte überprüfen und anpassen</h2>
      <p className="text-sm text-gray-500 mb-4">
        Überprüfen Sie die generierten Skripte für jede Folie.
        Klicken Sie auf den Stift um zu bearbeiten.
      </p>

      <div className="space-y-2 mb-6">
        {slides.map((slide, i) => {
          const isOpen = openAccordion === i;
          const isEditing = editingSlide === i;
          const wc = wordCount(isEditing ? editBuffer : slide.script);
          const dur = estimateDuration(wc);
          const preview = slide.script.slice(0, 60) + (slide.script.length > 60 ? "..." : "");
          return (
            <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
              <button
                onClick={() => { if (editingSlide !== null) onCancelEdit(); onOpenAccordionChange(isOpen ? -1 : i); }}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-100 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                aria-expanded={isOpen} aria-controls={`slide-panel-${i}`}
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900">Folie {i + 1}</span>
                  {!isOpen && <span className="ml-2 text-xs text-gray-400 truncate">{preview}</span>}
                </div>
                <svg className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {isOpen && (
                <div id={`slide-panel-${i}`} className="border-t border-gray-200 p-4 animate-[fadeIn_0.2s_ease-out]">
                  <div className="flex flex-col md:flex-row gap-4">
                    {!fastMode && (
                      <div className="flex-shrink-0" style={{ width: "100px" }}>
                        {slide.imageBase64 ? (
                          <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full rounded border border-gray-200" />
                        ) : (
                          <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center text-sm text-gray-400">Kein Bild</div>
                        )}
                      </div>
                    )}
                    <div className={`${fastMode ? "w-full" : "md:w-3/5"} flex flex-col`}>
                      {isEditing ? (
                        <>
                          <textarea value={editBuffer} onChange={(e) => onEditBufferChange(e.target.value)} rows={8}
                            className="w-full rounded-md border border-primary px-3 py-2 text-sm font-mono text-gray-900 focus:ring-1 focus:ring-primary focus:outline-none"
                            aria-label={`Skript für Folie ${i + 1} bearbeiten`} />
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-xs text-gray-400">ca. {wc} Wörter · ~{dur} Sek</span>
                            <div className="flex gap-2">
                              <button onClick={onCancelEdit} className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-100 transition-colors">Abbrechen</button>
                              <button onClick={() => onSaveEdit(i)} className="px-3 py-1 text-xs bg-primary text-white rounded hover:outline-2 hover:outline-primary transition-colors">Speichern</button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs text-gray-400">ca. {wc} Wörter · ~{dur} Sek</span>
                            <div className="flex items-center gap-1">
                              <button onClick={() => onOpenRegen(i)} disabled
                                className="w-7 h-7 flex items-center justify-center rounded-full text-gray-300 cursor-not-allowed"
                                aria-label={`Skript für Folie ${i + 1} per KI neu generieren`}
                                title="Nicht in der Demo verfügbar"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                                </svg>
                              </button>
                              <button onClick={() => onStartEdit(i)} className="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-100 transition-colors" aria-label={`Skript für Folie ${i + 1} bearbeiten`}>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                              </button>
                            </div>
                          </div>
                          <p className="text-sm font-mono text-gray-700 whitespace-pre-wrap leading-relaxed">
                            {slide.script || <span className="text-gray-400 italic">Kein Skript (leere Folie)</span>}
                          </p>
                          {regeneratingSlide === i && (
                            <div className="mt-3 border border-purple-200 rounded-lg p-3 bg-purple-50 space-y-2">
                              <p className="text-xs font-medium text-purple-700">KI-Anweisung für diese Folie (optional)</p>
                              <textarea value={regenPrompt} onChange={(e) => onRegenPromptChange(e.target.value)} rows={2}
                                placeholder="z.B. Erkläre das Konzept vereinfacht für Einsteiger."
                                className="w-full rounded-md border border-purple-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-purple-400 focus:ring-1 focus:ring-purple-400 focus:outline-none bg-white" />
                              <div className="flex gap-2 justify-end">
                                <button onClick={onCloseRegen} className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-100 transition-colors">Abbrechen</button>
                                <button onClick={() => onRunRegen(i)} disabled={regenLoading}
                                  className="px-3 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 transition-colors flex items-center gap-1.5">
                                  {regenLoading && <Spinner size="xs" color="current" />}
                                  {regenLoading ? "Generiere…" : "Generieren"}
                                </button>
                              </div>
                              {regenProposal !== null && (
                                <div>
                                  <p className="text-xs font-medium text-purple-700 mb-1">Vorschlag</p>
                                  <textarea value={regenProposal} onChange={(e) => onRegenProposalChange(e.target.value)} rows={4}
                                    className="w-full rounded-md border border-purple-300 px-3 py-2 text-sm font-mono text-gray-900 focus:border-purple-400 focus:ring-1 focus:ring-purple-400 focus:outline-none bg-white" />
                                  <div className="flex justify-end mt-2">
                                    <button onClick={() => onApplyRegen(i)} className="px-3 py-1 text-xs bg-primary text-white rounded hover:outline-2 hover:outline-primary transition-colors">Übernehmen</button>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
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
        <button onClick={onAcceptScripts} disabled={editingSlide !== null}
          className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:outline-2 hover:outline-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          Alle Skripte übernehmen
        </button>
      </div>
    </section>
  );
}
