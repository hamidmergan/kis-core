"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import ProviderSelect from "@/components/tools/ProviderSelect";
import type { FeatureProvider } from "@/hooks/useFeatureProviders";
import { MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from "@/lib/constants";
import StepFooter from "../_components/StepFooter";
import { useModules } from "@/hooks/useModules";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { hasContent } from "../_logic";
import type { Language, Source, SourceMode } from "../_types";

export const FIELD =
  "w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
/** Mirrors PODCAST_MAX_SOURCES in the backend. */
const MAX_QUELLEN = 10;

const EIN_MB = 1024 * 1024;

interface ContentStepProps {
  /** Without the assistant there are no modules, then the tab stays away. */
  canUseModules: boolean;
  source: Source;
  language: Language;
  instructions: string;
  glossaryIds: string[];
  /** The chat providers the script can be written on, empty hides the choice. */
  llmProviders: FeatureProvider[];
  llmProviderId: number | null;
  onLlmProvider: (id: number) => void;
  onSource: (source: Partial<Source>) => void;
  onLanguage: (language: Language) => void;
  onGlossaryIds: (ids: string[]) => void;
  onInstructions: (text: string) => void;
  onNext: () => void;
}

export default function ContentStep({ canUseModules, source, language, instructions, glossaryIds, llmProviders, llmProviderId,
                                      onLlmProvider, onSource, onLanguage, onGlossaryIds, onInstructions, onNext }: ContentStepProps) {
  const t = useTranslations("tools.podcast.content");
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
  // Whoever loses the assistant must not stay stuck in a tab that is gone.
  const mode: SourceMode = canUseModules || source.mode !== "module" ? source.mode : "files";
  const { modules, sources } = useModules(mode === "module" ? source.moduleId : "");
  const messung = useMaterialMeasure("podcast", mode, source.files, source.moduleId, source.sourceIds);

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
  const bereit = hatInhalt && !zuViele && !zuGross && (mode === "blank" || messung.ready);

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h1 className="text-xl font-bold mb-1">{tTool("title")}</h1>
      <p className="text-sm text-muted mb-8">{tTool("intro")}</p>
      <h2 className="text-lg font-bold mb-4">{t("heading")}</h2>

      <Tabs<SourceMode>
        className="mb-4"
        active={mode}
        onChange={(next) => onSource({ mode: next })}
        items={[
          { key: "files", label: t("tabs.files") },
          ...(canUseModules ? [{ key: "module" as const, label: "Workspace" }] : []),
          { key: "blank", label: t("tabs.blank") },
        ]}
      />

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
            className={`relative mb-3 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors cursor-pointer ${
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

      {mode === "module" && (
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

      {mode !== "blank" && (
        <>
        <div className="mt-6">
          <label htmlFor="podcast-language" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("languageLabel")}
          </label>
          <Select<Language>
            id="podcast-language"
            value={language}
            onChange={onLanguage}
            options={[
              { value: "de", label: t("languages.de") },
              { value: "en", label: t("languages.en") },
            ]}
          />
        </div>

        <ProviderSelect
          id="podcast-provider"
          label={t("providerLabel")}
          providers={llmProviders}
          value={llmProviderId}
          onChange={onLlmProvider}
          className="mt-4"
          showModel
        />

        <div className="mt-4">
          <span className="block text-sm font-medium text-foreground-soft">
            {t("glossaryLabel")}
          </span>
          <p className="mt-1 text-xs text-muted-soft">{t("glossaryHint")}</p>
          <GlossarySelector values={glossaryIds} onChange={onGlossaryIds} className="mb-4 mt-2" />
        </div>

        <div className="mt-4">
          <label htmlFor="podcast-instructions" className="block text-sm font-medium text-foreground-soft mb-2">
            {t("instructionsLabel")}
          </label>
          <textarea
            id="podcast-instructions"
            value={instructions}
            onChange={(e) => onInstructions(e.target.value)}
            rows={3}
            placeholder={t("instructionsPlaceholder")}
            className={`${FIELD} resize-y`}
          />
        </div>
        </>
      )}

      <StepFooter onBack={null} nextLabel={t("next")} onNext={onNext} nextDisabled={!bereit} />
    </section>
  );
}
