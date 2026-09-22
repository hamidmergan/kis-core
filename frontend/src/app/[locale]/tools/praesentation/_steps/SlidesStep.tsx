"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Checkbox from "@/components/ui/Checkbox";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import BauFortschritt, { BAU_PHASEN } from "../_components/BauFortschritt";
import FolienGrossbild from "../_components/FolienGrossbild";
import FolienKarte from "../_components/FolienKarte";
import StepFooter from "../_components/StepFooter";
import { FIELD } from "../_components/VorlageHochladen";
import { previewUrl } from "../_api";
import { kannEinfuegen } from "../_logic";
import { MAX_GIST, MAX_PROMPT, MAX_TITLE, bildPrompts, type JobProgress, type JobStatus, type Slide } from "../_types";

interface SlidesStepProps {
  jobUuid: string;
  slides: Slide[];
  previews: Record<string, number>;
  missingImages: string[];
  notesOn: boolean;
  notesInclude: boolean;
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  onSlide: (slide: Slide) => void;
  onMove: (id: string, delta: -1 | 1) => void;
  onDelete: (id: string) => void;
  onInsertAfter: (id: string, title: string, instruction: string) => void;
  onNotesInclude: (include: boolean) => void;
  onRegenText: (index: number) => void;
  onRegenImage: (id: string, prompts: string[]) => void;
  onAnchor: (index: number | null, text: string) => void;
  onResume: () => void;
  onRestart: () => void;
  onFinalize: () => void;
}

export default function SlidesStep(p: SlidesStepProps) {
  const t = useTranslations("tools.praesentation.slides");
  const tCancel = useTranslations("tools.praesentation.common");
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [einfuegen, setEinfuegen] = useState<{ id: string; title: string; anweisung: string } | null>(null);
  const [bildWunsch, setBildWunsch] = useState<{ id: string; prompts: string[] } | null>(null);
  const [loeschen, setLoeschen] = useState<{ id: string; nummer: number; title: string } | null>(null);
  const [offen, setOffen] = useState<Set<number>>(() => new Set([0]));
  const running = p.jobStatus === "pending" || p.jobStatus === "running" || p.jobStatus === "waiting_retry";
  const gestoert = p.jobStatus === "failed" || p.jobStatus === "paused";
  const schritt = p.progress?.step ?? "";
  const alleOffen = p.slides.length > 0 && offen.size === p.slides.length;
  const teilweiseOffen = offen.size > 0 && !alleOffen;

  if (running) {
    // The route reports "material", the reading task "lesen", both mean the sources.
    const text = schritt === "material" || schritt === "lesen" ? t("progressMaterial")
      : schritt === "outline" ? t("progressOutline")
      : schritt === "texte" ? t("progressTexts", { done: p.progress?.current ?? 0, total: p.progress?.total ?? 0 })
      : schritt === "bilder" ? t("progressImages", { done: p.progress?.current ?? 0, total: p.progress?.total ?? 0 })
      : schritt === "vorschau" ? t("progressPreview") : t("progressBuild");
    const detail = p.jobStatus === "waiting_retry" ? t("waitingRetry") : text;
    const kennt = (BAU_PHASEN as readonly string[]).includes(schritt);
    return (
      <section className="animate-[fadeIn_0.3s_ease-out] py-4" role="status" aria-live="polite">
        <div className="text-center">
          {!kennt && <Spinner size="lg" className="justify-center mb-4" />}
          <h2 className="text-lg font-bold">{t("working")}</h2>
          {kennt
            ? <div className="mt-5"><BauFortschritt phase={schritt} detail={detail} /></div>
            : <p className="text-sm text-foreground-soft mt-1">{detail}</p>}
        </div>
        {p.progress?.final && <BackgroundHint />}
      </section>
    );
  }

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold">{t("heading")}</h2>
      <div className="mt-1 flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-muted">{t("summary", { n: p.slides.length })}</p>
        <div className="flex items-center gap-x-5 gap-y-2 flex-wrap">
          {/* Only whoever asked for notes in the first step has anything to decide here. */}
          {p.notesOn && (
            <Checkbox checked={p.notesInclude} onChange={p.onNotesInclude} label={t("notesInclude")}
                      labelClassName="text-sm text-foreground" />
          )}
          {/* Sets every row at once, and in return shows how many are open. */}
          <Checkbox checked={alleOffen} indeterminate={teilweiseOffen} label={t("expandAll")}
                    labelClassName="text-sm text-foreground"
                    onChange={(auf) => setOffen(auf ? new Set(p.slides.map((_, i) => i)) : new Set())} />
        </div>
      </div>
      {gestoert && (
        <div className="mt-4 rounded-xl border-2 border-error-border p-3">
          <p className="text-sm text-error">{p.error || t("failed")}</p>
          {/* Without a single slide there is nothing to resume, only the outline can be attempted anew. */}
          <button type="button" className="mt-2 px-4 py-2 text-sm btn-primary rounded-lg"
                  onClick={p.slides.length === 0 ? p.onRestart : p.onResume}>
            {p.slides.length === 0 ? t("restart") : t("resume")}
          </button>
        </div>
      )}
      {!gestoert && p.error && <p className="text-sm text-error mt-3">{p.error}</p>}
      <ol className="mt-6 folien-liste">
        {p.slides.map((s, i) => (
          <FolienKarte key={s.id} index={i} slide={s} first={i <= 1} last={i >= p.slides.length - 2}
            previewUrl={typeof p.previews[s.id] === "number" ? previewUrl(p.jobUuid, s.id, p.previews[s.id]) : null}
            imageMissing={p.missingImages.includes(s.id)} notesOn={p.notesOn && p.notesInclude}
            open={offen.has(i)} onToggle={() => setOffen((alt) => {
              const neu = new Set(alt);
              if (!neu.delete(i)) neu.add(i);
              return neu;
            })}
            onInsertAfter={() => setEinfuegen({ id: s.id, title: "", anweisung: "" })}
            onChange={p.onSlide} onMove={(d) => p.onMove(s.id, d)} onDelete={() => setLoeschen({ id: s.id, nummer: i + 1, title: s.title })}
            onRegenText={() => p.onRegenText(i)} onRegenImage={() => setBildWunsch({ id: s.id, prompts: bildPrompts(s) })}
            onAnchor={(text) => p.onAnchor(text ? i : null, text)} onOpenPreview={() => setLightbox(i)} />
        ))}
      </ol>
      <StepFooter onBack={null} nextLabel={t("finalize")} onNext={p.onFinalize}
        nextDisabled={p.slides.length === 0} />

      {lightbox !== null && p.slides[lightbox] && (
        <FolienGrossbild
          index={lightbox}
          total={p.slides.length}
          previewUrl={typeof p.previews[p.slides[lightbox].id] === "number"
            ? previewUrl(p.jobUuid, p.slides[lightbox].id, p.previews[p.slides[lightbox].id])
            : null}
          onClose={() => setLightbox(null)}
          onIndexChange={setLightbox}
        />
      )}

      {einfuegen && (
        <Modal open onClose={() => setEinfuegen(null)} size="sm" title={t("insertTitle")}
          footer={<>
            <button type="button" onClick={() => setEinfuegen(null)} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">{tCancel("cancel")}</button>
            <button type="button" disabled={!kannEinfuegen(einfuegen.title, einfuegen.anweisung)} className="px-4 py-2 text-sm btn-primary rounded-lg"
                    onClick={() => { p.onInsertAfter(einfuegen.id, einfuegen.title.trim(), einfuegen.anweisung.trim()); setEinfuegen(null); }}>{t("insert")}</button>
          </>}>
          <div className="space-y-3">
            <label className="block text-sm">
              <span className="font-medium">{t("insertTitleLabel")}</span>
              <input className={`${FIELD} mt-1`} value={einfuegen.title} maxLength={MAX_TITLE} placeholder={t("insertPlaceholder")} autoFocus
                     aria-label={t("insertTitleLabel")}
                     onChange={(e) => setEinfuegen({ ...einfuegen, title: e.target.value })} />
            </label>
            <label className="block text-sm">
              <span className="font-medium">{t("insertInstructionLabel")}</span>
              <textarea className={`${FIELD} mt-1 resize-y`} rows={3} value={einfuegen.anweisung} maxLength={MAX_GIST}
                        aria-label={t("insertInstructionLabel")} placeholder={t("insertInstructionPlaceholder")}
                        onChange={(e) => setEinfuegen({ ...einfuegen, anweisung: e.target.value })} />
            </label>
            <p className="text-xs text-muted">{t("insertHint")}</p>
          </div>
        </Modal>
      )}

      {bildWunsch && (
        <Modal open onClose={() => setBildWunsch(null)} size="sm" title={t("imageTitle")}
          footer={<>
            <button type="button" onClick={() => setBildWunsch(null)} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">{tCancel("cancel")}</button>
            <button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg"
                    onClick={() => { p.onRegenImage(bildWunsch.id, bildWunsch.prompts); setBildWunsch(null); }}>{t("imageGo")}</button>
          </>}>
          <div className="space-y-3">
            {bildWunsch.prompts.map((prompt, i) => (
              <label key={i} className="block text-sm">
                {bildWunsch.prompts.length > 1 && <span className="font-medium">{t("imagePrompt", { n: i + 1 })}</span>}
                <textarea className={`${FIELD} mt-1 resize-y`} rows={4} value={prompt} maxLength={MAX_PROMPT}
                          aria-label={t("imagePrompt", { n: i + 1 })} placeholder={t("imagePlaceholder")}
                          onChange={(e) => setBildWunsch({ ...bildWunsch, prompts: bildWunsch.prompts.map((x, j) => (j === i ? e.target.value : x)) })} />
              </label>
            ))}
          </div>
        </Modal>
      )}
    </section>
  );
}
