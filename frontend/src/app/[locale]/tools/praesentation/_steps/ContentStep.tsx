"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import ToggleRow from "@/components/ui/ToggleRow";
import EinstellungsFeld from "@/components/tools/EinstellungsFeld";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";
import { Link } from "@/i18n/navigation";
import { useModules } from "@/hooks/useModules";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { FIELD } from "../_components/VorlageHochladen";
import StepFooter from "../_components/StepFooter";
import VorlagenWahl from "../_components/VorlagenWahl";
import { hasContent } from "../_logic";
import type { DemoMaterial } from "../_demo";
import type { Language, Source, SourceMode, Vorlage } from "../_types";

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
/** Mirrors the presentation source limit in the backend. */
const MAX_QUELLEN = 10;
/** Mirrors MAX_PRESENTER_CHARS in the backend. */
const MAX_PRESENTER = 80;
/** Mirrors MAX_STYLE_CHARS in the backend, the same cap as a template's own style. */
const MAX_STIL = 1000;
const KEINE_DATEIEN: File[] = [];

type Zeile = "material" | "language" | "provider" | "presenter" | "instructions" | "style";

interface ContentStepProps {
  canUseModules: boolean;
  source: Source;
  language: Language;
  notes: boolean;
  instructions: string;
  imageStyle: string | null;
  presenter: string;
  templateId: string;
  hasActiveJob: boolean | null;
  error: string;
  llmProviders: FeatureProvider[];
  llmProviderId: number | null;
  onLlmProvider: (id: number) => void;
  onSource: (source: Partial<Source>) => void;
  onLanguage: (language: Language) => void;
  onNotes: (notes: boolean) => void;
  onInstructions: (text: string) => void;
  onImageStyle: (text: string | null) => void;
  onPresenter: (name: string) => void;
  onTemplate: (id: string) => void;
  onNext: () => void;
  /** The demo run: its material and every setting that shaped the prepared deck stay fixed. */
  demo?: DemoMaterial;
}

/** Step 1 in two fixed columns: settings in a card on the left, the material to upload on the right. */
export default function ContentStep({ canUseModules, source, language, notes, instructions, imageStyle, presenter, templateId, hasActiveJob,
                                        error, llmProviders, llmProviderId, onLlmProvider, onSource, onLanguage, onNotes, onInstructions, onImageStyle,
                                        onPresenter, onTemplate, onNext, demo }: ContentStepProps) {
  const t = useTranslations("tools.praesentation.content");
  const tDemo = useTranslations("tools.praesentationDemo");
  const fest = !!demo;
  const tCommon = useTranslations("common");
  const format = useFormatter();
  const EIN_MB = 1024 * 1024;
  const groesse = (bytes: number): string =>
    bytes < EIN_MB
      ? `${format.number(Math.round(bytes / 1024))} KB`
      : `${format.number(bytes / EIN_MB, { maximumFractionDigits: 1 })} MB`;
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [vorlage, setVorlage] = useState<Vorlage | undefined>();
  const [offen, setOffen] = useState<Zeile | null>("material");
  // Whoever loses the assistant must not stay stuck in a tab that is gone.
  const mode: SourceMode = demo ? "module" : canUseModules || source.mode !== "module" ? source.mode : "files";
  const { modules, sources } = useModules(mode === "module" && !demo ? source.moduleId : "");
  const messung = useMaterialMeasure("praesentation", demo ? "files" : mode, demo ? KEINE_DATEIEN : source.files,
                                     source.moduleId, source.sourceIds);

  // A deleted source drops out of the choice.
  useEffect(() => {
    if (!sources) return;
    const vorhanden = new Set(sources.map((s) => s.uuid));
    const geblieben = source.sourceIds.filter((id) => vorhanden.has(id));
    if (geblieben.length !== source.sourceIds.length) onSource({ sourceIds: geblieben });
  }, [sources, source.sourceIds, onSource]);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const dabei = new Set(source.files.map((f) => f.name));
    const neue = Array.from(list).filter((f) => !dabei.has(f.name));
    onSource({ files: [...source.files, ...neue] });
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  };
  const voll = source.sourceIds.length >= MAX_QUELLEN;
  const toggleSource = (uuid: string) => {
    const set = new Set(source.sourceIds);
    if (set.has(uuid)) set.delete(uuid);
    else if (!voll) set.add(uuid);
    onSource({ sourceIds: [...set] });
  };
  const zeile = (z: Zeile) => ({ offen: offen === z, onToggle: () => setOffen((alt) => (alt === z ? null : z)) });

  const stil = imageStyle ?? vorlage?.stiltext ?? "";
  const anbieter = llmProviders.find((p) => p.id === llmProviderId)?.name ?? "";
  const gesperrt = !demo && (!hasContent({ ...source, mode }) || !messung.ready || hasActiveJob === true);

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      {/* On the phone the card dissolves into one list (templates, material, settings), on the desktop settings left, material right. */}
      <div className="-mx-4 lg:mx-0 flex flex-col lg:grid lg:grid-cols-[minmax(0,400px)_1fr] lg:items-start lg:gap-8">
        <div className="contents lg:block min-w-0 lg:rounded-xl lg:border lg:border-border-soft lg:bg-surface lg:p-5">

          {/* On the phone the templates lead, as a carousel above the material. */}
          <div className="order-1 px-4 pb-4 lg:p-0">
            <VorlagenWahl templateId={templateId} onTemplate={onTemplate} onVorlage={setVorlage} nurGewaehlte={fest} />
          </div>

          <EinstellungsFeld titel={t("languageLabel")} wert={t(`languages.${language}`)} htmlFor="praesentation-sprache" {...zeile("language")}>
            <Select<Language> id="praesentation-sprache" value={language} onChange={onLanguage} ariaLabel={t("languageLabel")} disabled={fest}
              options={[{ value: "de", label: t("languages.de") }, { value: "en", label: t("languages.en") }]} />
          </EinstellungsFeld>

          {llmProviders.length > 0 && (
            <EinstellungsFeld titel={t("providerLabel")} wert={anbieter} htmlFor="praesentation-provider" {...zeile("provider")}>
              <Select id="praesentation-provider" value={String(llmProviderId ?? "")} onChange={(v) => onLlmProvider(Number(v))}
                ariaLabel={t("providerLabel")} options={llmProviders.map((p) => ({ value: String(p.id), label: p.name }))} />
            </EinstellungsFeld>
          )}

          <EinstellungsFeld titel={t("presenterLabel")} wert={presenter || t("emptyValue")} htmlFor="praesentation-name" {...zeile("presenter")}>
            <input id="praesentation-name" type="text" className={FIELD} value={presenter} maxLength={MAX_PRESENTER}
              placeholder={t("presenterPlaceholder")} onChange={(e) => onPresenter(e.target.value)} readOnly={fest} />
          </EinstellungsFeld>

          <EinstellungsFeld titel={t("instructionsLabel")} wert={instructions || t("emptyValue")} htmlFor="praesentation-anweisung" {...zeile("instructions")}>
            <textarea id="praesentation-anweisung" className={`${FIELD} resize-y`} rows={3} value={instructions}
              placeholder={t("instructionsPlaceholder")} onChange={(e) => onInstructions(e.target.value)} readOnly={fest} />
          </EinstellungsFeld>

          {/* Only a template with picture fields gets pictures, the style belongs to the template and follows its choice. */}
          {vorlage?.hasImages && (
            <EinstellungsFeld titel={t("styleLabel")} wert={stil || t("emptyValue")} htmlFor="praesentation-stil" {...zeile("style")}>
              <textarea id="praesentation-stil" className={`${FIELD} resize-y`} rows={4} value={stil} maxLength={MAX_STIL}
                placeholder={t("stylePlaceholder")} onChange={(e) => onImageStyle(e.target.value)} readOnly={fest} />
              <div className="mt-2 flex justify-end">
                <button type="button" onClick={() => onImageStyle(null)} disabled={fest || imageStyle === null || imageStyle === vorlage.stiltext}
                  className="shrink-0 text-xs px-3 py-1.5 border-2 border-border rounded-md transition-colors enabled:hover:border-kb enabled:hover:text-kb disabled:opacity-40">
                  {t("styleReset")}
                </button>
              </div>
            </EinstellungsFeld>
          )}

          <div className="order-3 px-4 py-3.5 lg:hidden">
            <ToggleRow title={t("notesLabel")} description={t("notesHint")} checked={notes} onToggle={() => onNotes(!notes)} disabled={fest} />
          </div>
          <div className="order-3 hidden lg:block mt-6">
            <Checkbox checked={notes} onChange={onNotes} label={t("notesLabel")} disabled={fest} />
            <p className="text-xs text-muted mt-1">{t("notesHint")}</p>
          </div>

          {hasActiveJob === true && !demo && (
            <p className="order-3 mt-6 px-4 lg:px-0 text-sm text-error">{t("activeJob")} <Link href="/my-jobs" className="underline">{t("activeJobLink")}</Link></p>
          )}
          {error && (
            <p className="order-3 mt-6 px-4 lg:px-0 text-sm text-error">{error} <Link href="/my-jobs" className="underline">{t("activeJobLink")}</Link></p>
          )}

          <div className="order-3 hidden lg:block">
            <StepFooter onBack={null} nextLabel={t("next")} onNext={onNext} nextDisabled={gesperrt} />
          </div>
        </div>

        <div className="order-2 min-w-0 lg:col-start-2 lg:row-start-1 lg:rounded-xl lg:border lg:border-kb/15 lg:bg-kb/5 lg:p-5">
            <EinstellungsFeld titel={t("materialLabel")} className="border-t lg:border-t-0"
                  wert={demo ? t("sourcesCount", { n: demo.files.length }) : mode === "files" ? t("filesCount", { n: source.files.length }) : t("sourcesCount", { n: source.sourceIds.length })}
                  {...zeile("material")}>
              <Tabs<SourceMode>
                className="mb-4"
                active={mode}
                onChange={(next) => onSource({ mode: next })}
                items={[
                  { key: "files", label: t("tabs.files"), disabled: fest },
                  ...(canUseModules || demo ? [{ key: "module" as const, label: "Workspace" }] : []),
                ]}
              />

              {demo && (
                <div className="space-y-4">
                  <div>
                    <label htmlFor="praesentation-module" className="block text-sm font-medium text-foreground-soft mb-2">Workspace</label>
                    <Select id="praesentation-module" value="demo" onChange={() => {}} disabled
                      options={[{ value: "demo", label: demo.workspace }]} />
                  </div>
                  <div>
                    <span className="block text-sm font-medium text-foreground-soft mb-2">{t("sourcesLabel")}</span>
                    <ul className="space-y-2">
                      {demo.files.map((name) => (
                        <li key={name}>
                          <Checkbox checked disabled onChange={() => {}} label={name} labelClassName="text-sm text-foreground" />
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-muted">{tDemo("materialVorgegeben")}</p>
                  </div>
                </div>
              )}

              {mode === "files" && (
                <>
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
                    onDrop={onDrop}
                    onClick={() => fileRef.current?.click()}
                    className={`relative mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-6 lg:py-16 transition-colors cursor-pointer ${
                      dragOver ? "border-kb bg-kb/5" : "border-border hover:border-kb"
                    }`}
                  >
                    <input ref={fileRef} type="file" multiple accept={ACCEPT} className="hidden" aria-label={tCommon("fileSelectAria")}
                      onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
                    <svg className="hidden lg:block w-8 h-8 text-muted-soft mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    <p className="text-sm text-foreground-soft text-center">
                      {t("dropOrBrowse")} <span className="text-kb font-medium">{t("browse")}</span>
                    </p>
                    <p className="text-xs text-muted-soft mt-1">{t("filesHint")}</p>
                  </div>
                  {source.files.length > 0 && (
                    <>
                      <MaterialGauge bilanz={messung} max={messung.max} />
                      <ul className="space-y-2">
                        {source.files.map((datei) => (
                          <li key={datei.name} className="rounded-lg border border-border-soft bg-background px-3 py-2 text-sm">
                            <div className="flex items-center justify-between gap-3">
                              <span className="truncate">{datei.name}</span>
                              <span className="flex items-center gap-2 shrink-0">
                                <MeasureNote messung={messung.forFile(datei)} />
                                <span className="text-xs text-muted-soft">{groesse(datei.size)}</span>
                                <IconButton size="sm" aria-label={t("removeFile", { name: datei.name })}
                                  onClick={() => onSource({ files: source.files.filter((f) => f.name !== datei.name) })}>
                                  <X size={12} weight="bold" />
                                </IconButton>
                              </span>
                            </div>
                            <MeasureError messung={messung.forFile(datei)} />
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </>
              )}

              {mode === "module" && !demo && (
                modules === null ? (
                  <Spinner className="justify-center py-10" />
                ) : modules.length === 0 ? (
                  <EmptyState text={t("noModules")} />
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="praesentation-module" className="block text-sm font-medium text-foreground-soft mb-2">Workspace</label>
                      <Select id="praesentation-module" value={source.moduleId} onChange={(uuid) => onSource({ moduleId: uuid, sourceIds: [] })}
                        placeholder={tCommon("pleaseSelect")} options={modules.map((m) => ({ value: m.uuid, label: m.title }))} />
                    </div>
                    {source.moduleId && (sources === null ? (
                      <Spinner className="justify-center py-6" />
                    ) : sources.length === 0 ? (
                      <EmptyState size="sm" text={t("noSources")} />
                    ) : (
                      <div>
                        {source.sourceIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
                        <span className="block text-sm font-medium text-foreground-soft mb-2">{t("sourcesLabel")}</span>
                        <ul className="space-y-2">
                          {sources.map((s) => (
                            <li key={s.uuid}>
                              <div className="flex items-center justify-between gap-3">
                                <Checkbox checked={source.sourceIds.includes(s.uuid)} disabled={voll && !source.sourceIds.includes(s.uuid)}
                                  onChange={() => toggleSource(s.uuid)} label={s.filename} labelClassName="text-sm text-foreground" />
                                {source.sourceIds.includes(s.uuid) && <MeasureNote messung={messung.forSource(s.uuid)} />}
                              </div>
                              {source.sourceIds.includes(s.uuid) && <MeasureError messung={messung.forSource(s.uuid)} />}
                            </li>
                          ))}
                        </ul>
                        <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>
                          {t(voll ? "sourcesFull" : "sourcesHint", { max: MAX_QUELLEN })}
                        </p>
                      </div>
                    ))}
                  </div>
                )
              )}
            </EinstellungsFeld>
        </div>
      </div>

      {/* On the phone the start button stays in reach while scrolling the form and stops at its end. */}
      <div className="lg:hidden sticky bottom-0 z-30 -mx-4 mt-6 border-t border-border-soft bg-background px-4 pt-2.5 pb-3.5 flex flex-col gap-2">
        {vorlage && <span className="text-xs text-muted truncate">{t("barTemplate", { name: vorlage.name })}</span>}
        <button type="button" onClick={onNext} disabled={gesperrt}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          {t("next")}
        </button>
      </div>
    </section>
  );
}
