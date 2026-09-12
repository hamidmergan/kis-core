"use client";

import { useEffect, useRef, useState, type DragEvent } from "react";
import { useTranslations } from "next-intl";
import { X } from "@phosphor-icons/react";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import IconButton from "@/components/ui/IconButton";
import Select from "@/components/ui/Select";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import StepFooter from "../_components/StepFooter";
import { useModules } from "../_hooks/useModules";
import { hasContent } from "../_logic";
import type { Language, Source, SourceMode } from "../_types";

export const FIELD =
  "w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft";
const ACCEPT = ".pdf,.docx,.pptx,.txt,.md";

interface ContentStepProps {
  /** Without the assistant there are no modules, then the tab stays away. */
  canUseModules: boolean;
  source: Source;
  language: Language;
  instructions: string;
  onSource: (source: Partial<Source>) => void;
  onLanguage: (language: Language) => void;
  onInstructions: (text: string) => void;
  onNext: () => void;
}

export default function ContentStep({ canUseModules, source, language, instructions, onSource, onLanguage, onInstructions, onNext }: ContentStepProps) {
  const t = useTranslations("tools.podcast.content");
  const tCommon = useTranslations("common");
  const labels = useWorkspaceLabel();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  // Whoever loses the assistant must not stay stuck in a tab that is gone.
  const mode: SourceMode = canUseModules || source.mode !== "module" ? source.mode : "text";
  const { modules, sources } = useModules(mode === "module" ? source.moduleId : "");

  // A fresh pick takes everything, later the choice stands, a deleted source drops out.
  const abgeglichen = useRef<string | null>(null);
  useEffect(() => {
    if (!sources) return;
    const frisch = abgeglichen.current !== source.moduleId;
    abgeglichen.current = source.moduleId;
    const vorhanden = new Set(sources.map((s) => s.uuid));
    const geblieben = source.sourceIds.filter((id) => vorhanden.has(id));
    const naechste = frisch && geblieben.length === 0 ? sources.map((s) => s.uuid) : geblieben;
    if (naechste.length !== source.sourceIds.length || naechste.some((id, i) => id !== source.sourceIds[i])) {
      onSource({ sourceIds: naechste });
    }
  }, [sources, source.sourceIds, source.moduleId, onSource]);

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
  const toggleSource = (uuid: string) => {
    const set = new Set(source.sourceIds);
    if (set.has(uuid)) set.delete(uuid);
    else set.add(uuid);
    onSource({ sourceIds: [...set] });
  };

  const bereit = hasContent({ ...source, mode });

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <h2 className="text-lg font-bold mb-4">{t("heading")}</h2>

      <Tabs<SourceMode>
        className="mb-4"
        active={mode}
        onChange={(next) => onSource({ mode: next })}
        items={[
          { key: "text", label: t("tabs.text") },
          { key: "files", label: t("tabs.files") },
          ...(canUseModules ? [{ key: "module" as const, label: labels.singular }] : []),
        ]}
      />

      {mode === "text" && (
        <textarea
          value={source.text}
          onChange={(e) => onSource({ text: e.target.value })}
          rows={8}
          placeholder={t("textPlaceholder")}
          className={`${FIELD} resize-y`}
          aria-label={t("tabs.text")}
        />
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
            <ul className="space-y-2">
              {source.files.map((datei) => (
                <li key={datei.name} className="flex items-center justify-between gap-3 rounded-lg border border-border-soft px-3 py-2 text-sm">
                  <span className="truncate">{datei.name}</span>
                  <IconButton
                    size="sm"
                    aria-label={t("removeFile", { name: datei.name })}
                    onClick={() => onSource({ files: source.files.filter((f) => f.name !== datei.name) })}
                  >
                    <X size={12} weight="bold" />
                  </IconButton>
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
              <label htmlFor="podcast-module" className="block text-sm font-medium text-foreground-soft mb-2">
                {labels.singular}
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
                  <span className="block text-sm font-medium text-foreground-soft mb-2">{t("sourcesLabel")}</span>
                  <ul className="space-y-2">
                    {sources.map((s) => (
                      <li key={s.uuid}>
                        <Checkbox
                          checked={source.sourceIds.includes(s.uuid)}
                          onChange={() => toggleSource(s.uuid)}
                          label={s.filename}
                          labelClassName="text-sm text-foreground"
                        />
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-muted">{t("sourcesHint")}</p>
                </div>
              ))}
          </div>
        )
      )}

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

      {!bereit && <p className="mt-6 text-xs text-muted-soft">{t("empty")}</p>}

      <StepFooter onBack={null} nextLabel={t("next")} onNext={onNext} nextDisabled={!bereit} />
    </section>
  );
}
