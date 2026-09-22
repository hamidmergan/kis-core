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
import { Link } from "@/i18n/navigation";
import { useModules } from "@/hooks/useModules";
import { FIELD } from "../_components/VorlageHochladen";
import VorlagenWahl from "../_components/VorlagenWahl";
import StepFooter from "../_components/StepFooter";
import { hasContent } from "../_logic";
import type { Language, Source, SourceMode } from "../_types";

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";
/** Mirrors the presentation source limit in the backend. */
const MAX_QUELLEN = 5;

interface ContentStepProps {
  canUseModules: boolean;
  source: Source;
  language: Language;
  notes: boolean;
  instructions: string;
  templateId: string;
  hasActiveJob: boolean | null;
  error: string;
  onSource: (source: Partial<Source>) => void;
  onLanguage: (language: Language) => void;
  onNotes: (notes: boolean) => void;
  onInstructions: (text: string) => void;
  onTemplate: (id: string) => void;
  onNext: () => void;
}

export default function ContentStep({ canUseModules, source, language, notes, instructions, templateId, hasActiveJob, error,
                                       onSource, onLanguage, onNotes, onInstructions, onTemplate, onNext }: ContentStepProps) {
  const t = useTranslations("tools.praesentation.content");
  const tCommon = useTranslations("common");
  const format = useFormatter();
  const EIN_MB = 1024 * 1024;
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

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-4">{t("heading")}</h2>

      <Tabs<SourceMode>
        className="mb-4"
        active={mode}
        onChange={(next) => onSource({ mode: next })}
        items={[
          { key: "files", label: t("tabs.files") },
          ...(canUseModules ? [{ key: "module" as const, label: "Workspace" }] : []),
        ]}
      />

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
            <ul className="space-y-2">
              {source.files.map((datei) => (
                <li key={datei.name} className="flex items-center justify-between gap-3 rounded-lg border border-border-soft px-3 py-2 text-sm">
                  <span className="truncate">{datei.name}</span>
                  <span className="flex items-center gap-2 shrink-0">
                    <span className="text-xs text-muted-soft">{groesse(datei.size)}</span>
                    <IconButton
                      size="sm"
                      aria-label={t("removeFile", { name: datei.name })}
                      onClick={() => onSource({ files: source.files.filter((f) => f.name !== datei.name) })}
                    >
                      <X size={12} weight="bold" />
                    </IconButton>
                  </span>
                </li>
              ))}
            </ul>
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
              <label htmlFor="praesentation-module" className="block text-sm font-medium text-foreground-soft mb-2">
                Workspace
              </label>
              <Select
                id="praesentation-module"
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
                  <span className="block text-sm font-medium text-foreground-soft mb-2">{t("sourcesLabel")}</span>
                  <ul className="space-y-2">
                    {sources.map((s) => (
                      <li key={s.uuid}>
                        <Checkbox
                          checked={source.sourceIds.includes(s.uuid)}
                          disabled={voll && !source.sourceIds.includes(s.uuid)}
                          onChange={() => toggleSource(s.uuid)}
                          label={s.filename}
                          labelClassName="text-sm text-foreground"
                        />
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

      <VorlagenWahl templateId={templateId} onTemplate={onTemplate} />

      <label className="block mt-6 text-sm">
        <span className="font-medium">{t("languageLabel")}</span>
        <Select<Language> className="mt-1" value={language} onChange={onLanguage} ariaLabel={t("languageLabel")}
          options={[{ value: "de", label: t("languages.de") }, { value: "en", label: t("languages.en") }]} />
      </label>

      <label className="block mt-6 text-sm">
        <span className="font-medium">{t("instructionsLabel")}</span>
        <textarea className={`${FIELD} mt-1 resize-y`} rows={3} value={instructions}
          placeholder={t("instructionsPlaceholder")} onChange={(e) => onInstructions(e.target.value)} />
      </label>

      <Checkbox className="mt-6" checked={notes} onChange={onNotes} label={t("notesLabel")} />
      <p className="text-xs text-muted mt-1">{t("notesHint")}</p>

      {hasActiveJob === true && (
        <p className="mt-6 text-sm text-error">{t("activeJob")} <Link href="/my-jobs" className="underline">{t("activeJobLink")}</Link></p>
      )}

      {error && (
        <p className="mt-6 text-sm text-error">{error} <Link href="/my-jobs" className="underline">{t("activeJobLink")}</Link></p>
      )}

      <StepFooter onBack={null} nextLabel={t("next")} onNext={onNext}
        nextDisabled={!hasContent({ ...source, mode }) || hasActiveJob === true} />
    </section>
  );
}
