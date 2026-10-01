"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import BackgroundHint from "@/components/tools/BackgroundHint";
import Checkbox from "@/components/ui/Checkbox";
import Modal from "@/components/ui/Modal";
import Spinner from "@/components/ui/Spinner";
import StatusMark from "@/components/ui/StatusMark";
import FolienGrossbild from "../_components/FolienGrossbild";
import FolienKarte from "../_components/FolienKarte";
import FolienSkizze from "../_components/FolienSkizze";
import StepFooter from "../_components/StepFooter";
import { FIELD } from "../_components/VorlageHochladen";
import { imageUrl, previewUrl } from "../_api";
import { fortschrittMeldung, kannEinfuegen, skizzen } from "../_logic";
import { MAX_GIST, MAX_PROMPT, MAX_TITLE, bildPrompts, type JobProgress, type JobStatus, type Outline, type Slide } from "../_types";

// Before the outline nobody knows the count, a few placeholder rows stand for the deck.
const PLATZHALTER = 6;

const cancelIcon = (
  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
);

interface PreviewStepProps {
  jobUuid: string;
  outline: Outline | null;
  slides: Slide[];
  previews: Record<string, number>;
  images: Record<string, string[]>;
  missingImages: string[];
  inArbeit: string[];
  presenter: string;
  notesOn: boolean;
  notesInclude: boolean;
  /** True from the click on start until the run is done, also before the job answers. */
  laeuft: boolean;
  jobStatus: JobStatus;
  progress: JobProgress | null;
  error: string;
  hasOutline: boolean;
  hasDeck: boolean;
  /** The instruction named nothing the material covers, the deck drew on all of it. */
  instructionUnmatched: boolean;
  onNotesInclude: (include: boolean) => void;
  onSlide: (slide: Slide) => void;
  onMove: (id: string, delta: -1 | 1) => void;
  onDelete: (id: string) => void;
  onInsertAfter: (id: string, title: string, instruction: string) => void;
  onRegenImage: (id: string, prompts: string[]) => void;
  onAnchor: (index: number | null, text: string) => void;
  onResume: () => void;
  onRestart: () => void;
  /** Stops the run, null while the job has no id yet. */
  onCancel: (() => void) | null;
  onFinalize: () => void;
  /** The prepared demo run, its slides can be looked at but not changed. */
  demo?: boolean;
}

/** The deck as rows: a skeleton that fills while the run writes and draws, then the real slides to check and edit. */
export default function PreviewStep(p: PreviewStepProps) {
  const t = useTranslations("tools.praesentation.slides");
  const tCancel = useTranslations("tools.praesentation.common");
  const tDemo = useTranslations("tools.praesentationDemo");
  const [lightbox, setLightbox] = useState<number | null>(null);
  // Every row starts open so the skeleton can be watched filling, only what the person closes stays closed.
  const [zu, setZu] = useState<Set<string>>(() => new Set());
  const [einfuegen, setEinfuegen] = useState<{ id: string; title: string; anweisung: string } | null>(null);
  const [bildWunsch, setBildWunsch] = useState<{ id: string; prompts: string[] } | null>(null);
  const [loeschen, setLoeschen] = useState<{ id: string; nummer: number; title: string } | null>(null);
  const gestoert = p.jobStatus === "failed" || p.jobStatus === "paused";
  const meldung = fortschrittMeldung(p.jobStatus, p.progress);
  const karten = skizzen(p.outline, p.slides);
  const nachId = new Map(p.slides.map((s) => [s.id, s]));
  // The first build has no finished slide yet, a later change keeps the others in view.
  const erstbau = p.laeuft && Object.keys(p.previews).length === 0;
  // A stopped run leaves slides without text or the file unbuilt, resuming does only what is missing.
  const unfertig = !p.laeuft && !gestoert && p.outline !== null
    && (p.outline.rows.some((r) => !nachId.has(r.id)) || !p.hasDeck);
  // Nothing runs, nothing is missing: the slides are ready to be checked.
  const bereit = !p.laeuft && !gestoert && !unfertig && p.slides.length > 0;
  const version = (id: string) => p.previews[id] ?? 0;
  const vorschau = (id: string) => (typeof p.previews[id] === "number" ? previewUrl(p.jobUuid, id, version(id)) : null);
  const gemeinsam = {
    deckTitel: p.outline?.title ?? "",
    untertitel: p.outline?.subtitle ?? "",
    vortragend: p.presenter,
    laeuft: p.laeuft,
  };
  const notizen = p.notesOn && p.notesInclude;
  const zeilen = karten.length > 0 ? karten.map((k) => k.id) : Array.from({ length: PLATZHALTER }, (_, i) => `platz${i}`);
  const alleOffen = zeilen.every((id) => !zu.has(id));
  const teilweiseOffen = !alleOffen && zeilen.some((id) => !zu.has(id));
  const umschalten = (id: string) => setZu((alt) => {
    const neu = new Set(alt);
    if (!neu.delete(id)) neu.add(id);
    return neu;
  });

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      {/* A stopped run says what happened in its own box below, it needs no heading. */}
      {bereit ? (
        <div className="flex items-center gap-3 flex-wrap" aria-live="polite">
          <h2 className="text-lg font-bold">
            <StatusMark tone="success" className="text-inherit">{t("previewReady")}</StatusMark>
          </h2>
          <span className="text-sm text-muted">{t("summary", { n: p.slides.length })}</span>
        </div>
      ) : (
        <>
          {p.laeuft && <h2 className="text-lg font-bold">{t("working")}</h2>}
          <div className="mt-1" aria-live="polite">
            {p.laeuft ? (
              <p className="text-sm text-foreground-soft flex items-center gap-2">
                <Spinner size="sm" />
                {t(meldung.key, meldung.values)}
              </p>
            ) : (
              <p className="text-sm text-muted">{t("summary", { n: p.slides.length })}</p>
            )}
          </div>
        </>
      )}

      {bereit && (
        <p className="text-sm text-foreground-soft mt-2">{p.demo ? tDemo("bearbeitenGesperrt") : t("previewReadyHint")}</p>
      )}

      {p.instructionUnmatched && (
        <p className="mt-4 rounded-md border border-warn-border bg-warn-bg px-3 py-2 text-sm text-warn-strong" role="status">
          {t("instructionUnmatched")}
        </p>
      )}

      {/* Below the status and the hint on the right, so the lines above read on their own. */}
      <div className="mt-12 flex items-center justify-end gap-x-5 gap-y-2 flex-wrap">
        {/* Only whoever asked for notes in the first step has anything to decide here. */}
        {p.notesOn && !erstbau && (
          <Checkbox checked={p.notesInclude} onChange={p.onNotesInclude} label={t("notesInclude")} disabled={p.laeuft}
                    labelClassName="text-sm text-foreground" />
        )}
        {/* Sets every row at once, and in return shows how many are open. */}
        <Checkbox checked={alleOffen} indeterminate={teilweiseOffen} label={t("expandAll")}
                  labelClassName="text-sm text-foreground"
                  onChange={(auf) => setZu(auf ? new Set() : new Set(zeilen))} />
      </div>

      {gestoert && (
        <div className="mt-4 rounded-xl border-2 border-error-border p-3">
          <p className="text-sm text-error">{p.error || t("failed")}</p>
          <button type="button" className="mt-2 px-4 py-2 text-sm btn-primary rounded-lg"
                  onClick={p.hasOutline ? p.onResume : p.onRestart}>
            {p.hasOutline ? t("retry") : t("restart")}
          </button>
        </div>
      )}
      {!gestoert && p.error && <p className="text-sm text-error mt-3">{p.error}</p>}
      {unfertig && (
        <div className="mt-4 rounded-xl border-2 border-border p-3">
          <p className="text-sm text-foreground-soft">{t("unfinished")}</p>
          <button type="button" className="mt-2 px-4 py-2 text-sm btn-primary rounded-lg" onClick={p.onResume}>
            {t("resume")}
          </button>
        </div>
      )}

      {(karten.length > 0 || p.laeuft) && (
        <ol className="mt-3 folien-liste">
          {karten.length > 0
            ? karten.map((k, i) => {
                const s = nachId.get(k.id);
                // A slide being redone shows as a sketch again, its old preview and pictures would only mislead.
                const neu = p.laeuft && (erstbau || p.inArbeit.includes(k.id));
                return (
                  <FolienKarte key={k.id} index={i} role={k.role} titel={k.slide?.title || k.row?.title || ""} slide={k.slide}
                    previewUrl={neu ? null : vorschau(k.id)}
                    skizze={<FolienSkizze nummer={i + 1} skizze={k} {...gemeinsam} bilder={neu && !erstbau ? [] : p.images[k.id] ?? []}
                                          bildUrl={(slot) => imageUrl(p.jobUuid, k.id, slot, version(k.id))} />}
                    imageMissing={!p.laeuft && p.missingImages.includes(k.id)} notesOn={notizen}
                    first={i <= 1} last={i >= karten.length - 2} open={!zu.has(k.id)} gesperrt={p.laeuft || !!p.demo}
                    onToggle={() => umschalten(k.id)}
                    onChange={p.onSlide} onMove={(d) => p.onMove(k.id, d)}
                    onDelete={() => setLoeschen({ id: k.id, nummer: i + 1, title: k.slide?.title || k.row?.title || "" })}
                    onInsertAfter={() => setEinfuegen({ id: k.id, title: "", anweisung: "" })}
                    onRegenImage={() => s && setBildWunsch({ id: k.id, prompts: bildPrompts(s) })}
                    onAnchor={(text) => p.onAnchor(text ? i : null, text)} onOpenPreview={() => setLightbox(i)} />
                );
              })
            : zeilen.map((id, i) => (
                <FolienKarte key={id} index={i} role={null} titel="" slide={null} previewUrl={null}
                  skizze={<FolienSkizze nummer={i + 1} skizze={null} {...gemeinsam} bilder={[]} bildUrl={() => ""} />}
                  imageMissing={false} notesOn={notizen} first last open={!zu.has(id)} gesperrt={p.laeuft}
                  onToggle={() => umschalten(id)} onChange={() => undefined} onMove={() => undefined} onDelete={() => undefined}
                  onInsertAfter={() => undefined} onRegenImage={() => undefined} onAnchor={() => undefined} onOpenPreview={() => undefined} />
              ))}
        </ol>
      )}

      {p.laeuft && <BackgroundHint />}
      {p.laeuft && p.onCancel ? (
        <div className="flex justify-center mt-6">
          <button type="button" onClick={p.onCancel}
                  className="btn-cancel px-4 py-2 text-sm text-error border border-error-border rounded-md transition-colors inline-flex items-center gap-2">
            {cancelIcon}
            {tCancel("cancel")}
          </button>
        </div>
      ) : (
        <StepFooter onBack={null} nextLabel={t("finalize")} onNext={p.onFinalize}
          nextDisabled={p.slides.length === 0 || p.laeuft || gestoert} />
      )}

      {lightbox !== null && karten[lightbox] && (
        <FolienGrossbild index={lightbox} total={karten.length} previewUrl={vorschau(karten[lightbox].id)}
                         onClose={() => setLightbox(null)} onIndexChange={setLightbox} />
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

      {loeschen && (
        <Modal open onClose={() => setLoeschen(null)} size="sm" title={t("delete")}
          footer={<>
            <button type="button" onClick={() => setLoeschen(null)} className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg">{tCancel("cancel")}</button>
            <button type="button" className="px-4 py-2 text-sm btn-danger rounded-lg"
                    onClick={() => { p.onDelete(loeschen.id); setLoeschen(null); }}>{t("deleteConfirm")}</button>
          </>}>
          <p className="text-sm font-medium">{t("deleteBody", { n: loeschen.nummer, title: loeschen.title })}</p>
          <p className="text-sm text-muted mt-2">{t("deleteWarning")}</p>
        </Modal>
      )}
    </section>
  );
}
