"use client";

import { CaretDown } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import IconButton from "@/components/ui/IconButton";
import SparkleIcon from "@/components/ui/SparkleIcon";
import Spinner from "@/components/ui/Spinner";
import { wordCount } from "@/lib/text";
import type { SlideData } from "@/types";
import StepFooter from "./StepFooter";

interface ScriptReviewStepProps {
  onBack: (() => void) | null;
  slides: SlideData[];
  openAccordion: number;
  editingSlide: number | null;
  editBuffer: string;
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
  onBack,
  slides,
  openAccordion,
  editingSlide,
  editBuffer,
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
  const t = useTranslations("tools.screencast");
  const missing = slides.filter((s) => !s.script.trim()).length;
  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-2">{t("scriptReview.heading")}</h2>
      <p className="text-sm text-muted mb-6">{t("scriptReview.intro")}</p>

      {/* Same register as the slide list of the presentation: no card border,
          a hairline above each row, the open row on the tile tone. */}
      <ol className="folien-liste mb-6">
        {slides.map((slide, i) => {
          const isOpen = openAccordion === i;
          const isEditing = editingSlide === i;
          const wc = wordCount(isEditing ? editBuffer : slide.script);
          const preview = slide.script.slice(0, 60) + (slide.script.length > 60 ? "..." : "");

          return (
            <li key={i} className={`folien-zeile ${isOpen ? "offen" : ""}`}>
              <button
                onClick={() => onAccordionToggle(i)}
                className="w-full flex items-center gap-2 py-3.5 text-left"
                aria-expanded={isOpen}
                aria-controls={`slide-panel-${i}`}
              >
                <span className="flex-1 min-w-0 flex items-baseline gap-2">
                  <span className="folien-titel text-sm font-medium text-foreground whitespace-nowrap">
                    {t("common.slide", { n: i + 1 })}
                  </span>
                  {!isOpen && <span className="text-xs text-muted-soft truncate">{preview}</span>}
                </span>
                <span className="row-caret shrink-0" aria-hidden="true">
                  <CaretDown size={14} weight="bold" className={`transition-transform ${isOpen ? "rotate-180" : ""}`} />
                </span>
              </button>

              {isOpen && (
                <div id={`slide-panel-${i}`} className="pb-4 animate-[fadeIn_0.2s_ease-out]">
                  <div className="flex flex-col gap-4">
                    <div className="flex-shrink-0" style={{ width: "100px" }}>
                      {slide.imageBase64 ? (
                        <button
                          onClick={() => onLightboxOpen(i)}
                          className="block w-full rounded border-2 border-transparent hover:border-kb transition-colors overflow-hidden leading-none cursor-zoom-in focus-visible:outline-2 focus-visible:outline-kb"
                          aria-label={t("common.slideZoomAria", { n: i + 1 })}
                        >
                          {/* The image sets the height, so the hover frame lies on the slide edge. */}
                          <img src={`data:image/png;base64,${slide.imageBase64}`} alt={t("common.slide", { n: i + 1 })} className="block w-full" />
                        </button>
                      ) : (
                        <div className="w-full aspect-video bg-surface rounded flex items-center justify-center">
                          <Spinner size="sm" />
                        </div>
                      )}
                    </div>

                    <div className="w-full flex flex-col">
                      {isEditing ? (
                        <>
                          {/* No resting border, it appears only once the cursor is in the field. */}
                          <textarea
                            value={editBuffer}
                            onChange={(e) => onEditBufferChange(e.target.value)}
                            rows={8}
                            className="w-full rounded-md border-2 border-transparent bg-background px-3 py-2 text-sm font-mono text-foreground focus:border-kb focus:outline-none"
                            aria-label={t("scriptReview.editAria", { n: i + 1 })}
                          />
                          <div className="flex items-center justify-between mt-2">
                            <span className="text-xs text-muted-soft">{t("scriptReview.wordsApprox", { n: wc })}</span>
                            <div className="flex gap-2">
                              <button
                                onClick={onCancelEdit}
                                className="btn-cancel px-3 py-1 text-xs text-foreground-soft border border-border rounded transition-colors"
                              >
                                {t("common.cancel")}
                              </button>
                              <button
                                onClick={() => onSaveEdit(i)}
                                className="px-3 py-1 text-xs btn-primary rounded  transition-colors"
                              >
                                {t("common.save")}
                              </button>
                            </div>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs text-muted-soft">{t("scriptReview.wordsApprox", { n: wc })}</span>
                            <div className="flex items-center gap-1">
                              <IconButton
                                onClick={() => onOpenRegen(i)}
                                className={regenAnchorSlide === i && regenAnchorText ? "text-kb" : "text-muted-soft"}
                                aria-label={t("scriptReview.regenAria", { n: i + 1 })}
                                title={t("scriptReview.regenTitle")}
                              >
                                <SparkleIcon />
                              </IconButton>
                              <IconButton
                                onClick={() => onStartEdit(i)}
                                className="text-muted-soft"
                                aria-label={t("scriptReview.editAria", { n: i + 1 })}
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                  />
                                </svg>
                              </IconButton>
                            </div>
                          </div>
                          <p
                            className="text-sm font-mono text-foreground-soft whitespace-pre-wrap leading-relaxed"
                            onMouseUp={() => {
                              const text = window.getSelection()?.toString().trim();
                              onRegenAnchor(text ? i : null, text || "");
                            }}
                          >
                            {slide.script || <span className="text-muted-soft italic">{t("scriptReview.emptyScript")}</span>}
                          </p>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      {missing > 0 && (
        <p className="text-sm text-warn-strong bg-warn-bg border border-warn-border rounded-md px-3 py-2">
          {t("scriptReview.missingScripts", { n: missing })}
        </p>
      )}

      <StepFooter
        onBack={onBack}
        nextLabel={t("scriptReview.acceptAll")}
        onNext={onAcceptScripts}
        nextDisabled={editingSlide !== null}
      />
    </section>
  );
}
