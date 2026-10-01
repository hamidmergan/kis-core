"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Info, X } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import EinstellungsFeld from "@/components/tools/EinstellungsFeld";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";
import { Link } from "@/i18n/navigation";
import { MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from "@/lib/constants";
import StepFooter from "../_components/StepFooter";
import { useModules } from "@/hooks/useModules";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { hasContent } from "../_logic";
import type { DemoMaterial } from "../_demo";
import type { Language, Source, SourceMode } from "../_types";

export const FIELD =
  "w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
/** Mirrors PODCAST_MAX_SOURCES in the backend. */
const MAX_QUELLEN = 10;

const EIN_MB = 1024 * 1024;
const KEINE_DATEIEN: File[] = [];

type Zeile = "material" | "language" | "provider" | "instructions";
const DEMO_BADGE = "text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent";
const DEMO_FARBE = { backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" };

interface ContentStepProps {
  /** Without the assistant there are no modules, then the tab stays away. */
  canUseModules: boolean;
  source: Source;
  language: Language;
  instructions: string;
  /** The chat providers the script can be written on, empty hides the choice. */
  llmProviders: FeatureProvider[];
  llmProviderId: number | null;
  onLlmProvider: (id: number) => void;
  onSource: (source: Partial<Source>) => void;
  onLanguage: (language: Language) => void;
  onInstructions: (text: string) => void;
  onNext: () => void;
  /** The demo run: its material and every setting that shaped the prepared podcast stay fixed. */
  demo?: DemoMaterial;
  /** A prepared demo run exists, the real page then links to it. */
  demoDa?: boolean;
  /** Leaves the demo, only set on the demo page. */
  onBeenden?: () => void;
}

export default function ContentStep({ canUseModules, source, language, instructions, llmProviders, llmProviderId,
                                      onLlmProvider, onSource, onLanguage, onInstructions, onNext,
                                      demo, demoDa = false, onBeenden }: ContentStepProps) {
  const t = useTranslations("tools.podcast.content");
  const tDemo = useTranslations("tools.podcastDemo");
  const fest = !!demo;
  const tTool = useTranslations("tools.podcast");
  const tCommon = useTranslations("common");
  const format = useFormatter();
  /** Readable size, the decimal mark follows the display language. */
  const groesse = (bytes: number): string =>
    bytes < EIN_MB
      ? `${format.number(Math.round(bytes / 1024))} KB`
      : `${format.number(bytes / EIN_MB, { maximumFractionDigits: 1 })} MB`;
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [offen, setOffen] = useState<Zeile | null>("material");
  // Whoever loses the assistant must not stay stuck in a tab that is gone.
  const mode: SourceMode = demo ? "module" : canUseModules || source.mode !== "module" ? source.mode : "files";
  const { modules, sources } = useModules(mode === "module" && !demo ? source.moduleId : "");
  const messung = useMaterialMeasure("podcast", demo ? "files" : mode, demo ? KEINE_DATEIEN : source.files,
                                     source.moduleId, source.sourceIds);

  // Nothing is preselected, a deleted source drops out of the choice.
  useEffect(() => {
    if (!sources) return;
    const vorhanden = new Set(sources.map((s) => s.uuid));
    const geblieben = source.sourceIds.filter((id) => vorhanden.has(id));
    if (geblieben.length !== source.sourceIds.length) {
      onSource({ sourceIds: geblieben });
    }
  }, [sources, source.sourceIds, onSource]);

  // Everything lands in the list, too much is marked instead of silently dropped.
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
  const chooseModule = (uuid: string) => onSource({ moduleId: uuid, sourceIds: [] });
  const voll = source.sourceIds.length >= MAX_QUELLEN;
  const toggleSource = (uuid: string) => {
    const set = new Set(source.sourceIds);
    if (set.has(uuid)) set.delete(uuid);
    else if (!voll) set.add(uuid);
    onSource({ sourceIds: [...set] });
  };

  const bytes = source.files.reduce((n, f) => n + f.size, 0);
  const zuViele = source.files.length > MAX_QUELLEN;
  const zuGross = bytes > MAX_UPLOAD_BYTES;
  const hatInhalt = hasContent({ ...source, mode });
  const bereit = fest || (hatInhalt && !zuViele && !zuGross && (mode === "blank" || messung.ready));

  const zeile = (z: Zeile) => ({ offen: offen === z, onToggle: () => setOffen((alt) => (alt === z ? null : z)) });
  const anbieter = llmProviders.find((p) => p.id === llmProviderId)?.name ?? "";
  const materialWert = demo ? tCommon("material.sourcesN", { n: demo.files.length })
    : mode === "files" ? tCommon("material.filesN", { n: source.files.length })
    : mode === "module" ? tCommon("material.sourcesN", { n: source.sourceIds.length })
    : t("tabs.blank");

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-baseline justify-between gap-3 mb-1">
        <h1 className="text-xl font-bold">{tTool("title")}</h1>
        {demo ? (
          <button type="button" onClick={onBeenden} className={`${DEMO_BADGE} hover:border-black transition-colors`} style={DEMO_FARBE}>
            {tDemo("beenden")}
          </button>
        ) : demoDa && (
          <Link href="/tools/podcast-demo" className={`${DEMO_BADGE} hover:border-black transition-colors`} style={DEMO_FARBE}>
            {tTool("demoBadge")}
          </Link>
        )}
      </div>
      <p className={`text-sm text-muted ${demo ? "mb-6" : "mb-8"}`}>
        {tTool("intro")}
        {!demo && demoDa && <> {tTool("demoStimmen")}</>}
      </p>
      {demo && (
        <p className="mb-8 flex items-start gap-2 rounded-lg bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
          <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
          {tDemo("hinweis")}
        </p>
      )}
      {/* On the phone the card dissolves into one list (material, settings), on the desktop settings left, material right. */}
      <div className="-mx-4 lg:mx-0 flex flex-col lg:grid lg:grid-cols-[minmax(0,400px)_1fr] lg:items-start lg:gap-8">
        <div className="contents lg:block min-w-0 lg:rounded-xl lg:border lg:border-border-soft lg:bg-surface lg:p-5">
          {mode !== "blank" && (
            <>
              <EinstellungsFeld titel={t("languageLabel")} wert={t(`languages.${language}`)} htmlFor="podcast-language"
                                className="order-3 lg:mt-0" {...zeile("language")}>
                <Select<Language>
                  id="podcast-language"
                  value={language}
                  onChange={onLanguage}
                  disabled={fest}
                  options={[
                    { value: "de", label: t("languages.de") },
                    { value: "en", label: t("languages.en") },
                  ]}
                />
              </EinstellungsFeld>

              {llmProviders.length > 0 && (
                <EinstellungsFeld titel={t("providerLabel")} wert={anbieter} htmlFor="podcast-provider" {...zeile("provider")}>
                  <Select id="podcast-provider" value={String(llmProviderId ?? "")} onChange={(v) => onLlmProvider(Number(v))}
                    ariaLabel={t("providerLabel")} options={llmProviders.map((p) => ({ value: String(p.id), label: p.name }))} />
                </EinstellungsFeld>
              )}

              <EinstellungsFeld titel={t("instructionsLabel")} wert={instructions || tCommon("emptyValue")} htmlFor="podcast-instructions"
                                {...zeile("instructions")}>
                <textarea
                  id="podcast-instructions"
                  value={instructions}
                  onChange={(e) => onInstructions(e.target.value)}
                  readOnly={fest}
                  rows={3}
                  placeholder={t("instructionsPlaceholder")}
                  className={`${FIELD} resize-y`}
                />
              </EinstellungsFeld>
            </>
          )}

          {/* A self-written script needs no settings here, the card then holds only the way on. */}
          <div className={`order-3 hidden lg:block ${mode === "blank" ? "[&>div]:mt-0" : ""}`}>
            <StepFooter onBack={null} nextLabel={t("next")} onNext={onNext} nextDisabled={!bereit} />
          </div>
        </div>

        <div className="order-1 min-w-0 lg:col-start-2 lg:row-start-1 lg:rounded-xl lg:border lg:border-kb/15 lg:bg-kb/5 lg:p-5">
          <EinstellungsFeld titel={tCommon("material.label")} wert={materialWert} className="border-t lg:border-t-0" {...zeile("material")}>
            <Tabs<SourceMode>
              className="mb-4"
              active={mode}
              onChange={(next) => onSource({ mode: next })}
              items={[
                { key: "files", label: t("tabs.files"), disabled: fest },
                ...(canUseModules || demo ? [{ key: "module" as const, label: "Workspace" }] : []),
                { key: "blank", label: t("tabs.blank"), disabled: fest },
              ]}
            />

            {demo && (
              <div className="space-y-4">
                <div>
                  <label htmlFor="podcast-module" className="block text-sm font-medium text-foreground-soft mb-2">
                    Workspace
                  </label>
                  <Select id="podcast-module" value="demo" onChange={() => {}} disabled
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

            {mode === "blank" && (
              <p className="rounded-lg border border-border-soft px-4 py-3 text-sm text-foreground-soft">
                {t("blankHint")}
              </p>
            )}

            {mode === "files" && (
              <>
                <div
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={(e) => {
                    e.preventDefault();
                    setDragOver(false);
                  }}
                  onDrop={onDrop}
                  onClick={() => fileRef.current?.click()}
                  className={`relative mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-6 lg:py-16 transition-colors cursor-pointer ${
                    dragOver ? "border-kb bg-kb/5" : "border-border hover:border-kb"
                  }`}
                >
                  <input
                    ref={fileRef}
                    type="file"
                    multiple
                    accept={ACCEPT}
                    className="hidden"
                    aria-label={tCommon("fileSelectAria")}
                    onChange={(e) => {
                      addFiles(e.target.files);
                      e.target.value = "";
                    }}
                  />
                  <svg className="w-8 h-8 text-muted-soft mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-sm text-foreground-soft">
                    {t("dropOrBrowse")} <span className="text-kb font-medium">{t("browse")}</span>
                  </p>
                  <p className="text-xs text-muted-soft mt-1">{t("filesHint")}</p>
                </div>
                {source.files.length > 0 && (
                  <>
                    <MaterialGauge bilanz={messung} max={messung.max} />
                    <ul className="space-y-2">
                      {source.files.map((datei) => (
                        <li key={datei.name} className="rounded-lg border border-border-soft px-3 py-2 text-sm">
                          <div className="flex items-center justify-between gap-3">
                            <span className="truncate">{datei.name}</span>
                            <span className="flex items-center gap-2 shrink-0">
                              <MeasureNote messung={messung.forFile(datei)} />
                              <span className="text-xs text-muted-soft">{groesse(datei.size)}</span>
                              <IconButton
                                size="sm"
                                aria-label={t("removeFile", { name: datei.name })}
                                onClick={() => onSource({ files: source.files.filter((f) => f.name !== datei.name) })}
                              >
                                <X size={12} weight="bold" />
                              </IconButton>
                            </span>
                          </div>
                          <MeasureError messung={messung.forFile(datei)} />
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-muted">
                      <span className={zuViele ? "text-error font-medium" : ""}>
                        {t("filesCount", { n: source.files.length, max: MAX_QUELLEN })}
                      </span>
                      {", "}
                      <span className={zuGross ? "text-error font-medium" : ""}>
                        {t("filesSize", { size: groesse(bytes), max: `${MAX_UPLOAD_MB} MB` })}
                      </span>
                    </p>
                    {(zuViele || zuGross) && (
                      <p className="mt-2 rounded-lg border border-error-border bg-error-bg px-3 py-2 text-sm text-error">
                        {t(zuViele ? "tooManyFiles" : "tooLarge")}
                      </p>
                    )}
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
                    <label htmlFor="podcast-module" className="block text-sm font-medium text-foreground-soft mb-2">
                      Workspace
                    </label>
                    <Select
                      id="podcast-module"
                      value={source.moduleId}
                      onChange={chooseModule}
                      placeholder={tCommon("pleaseSelect")}
                      options={modules.map((m) => ({ value: m.uuid, label: m.title }))}
                    />
                  </div>
                  {source.moduleId &&
                    (sources === null ? (
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
                                <Checkbox
                                  checked={source.sourceIds.includes(s.uuid)}
                                  disabled={voll && !source.sourceIds.includes(s.uuid)}
                                  onChange={() => toggleSource(s.uuid)}
                                  label={s.filename}
                                  labelClassName="text-sm text-foreground"
                                />
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

      {/* On the phone the way on stays in reach while scrolling the form and stops at its end. */}
      <div className="lg:hidden sticky bottom-0 z-30 -mx-4 mt-6 border-t border-border-soft bg-background px-4 py-3">
        <button type="button" onClick={onNext} disabled={!bereit}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          {t("next")}
        </button>
      </div>
    </section>
  );
}
