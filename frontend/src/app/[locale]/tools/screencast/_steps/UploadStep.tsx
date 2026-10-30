"use client";

import { useState, type DragEvent, type RefObject } from "react";
import { Info } from "@phosphor-icons/react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import Select from "@/components/ui/Select";
import Checkbox from "@/components/ui/Checkbox";
import ToggleRow from "@/components/ui/ToggleRow";
import EinstellungsFeld from "@/components/tools/EinstellungsFeld";
import { ProviderPicker, showProviderField } from "@/components/tools/ProviderSelect";
import StepFooter from "./StepFooter";

const ACCEPTED_EXTENSIONS = [".pptx"];

type Zeile = "file" | "language" | "glossary" | "provider";

interface UploadStepProps {
  onBack: (() => void) | null;
  hasActiveJob: boolean | null;
  file: File | null;
  fileError: string | null;
  dragOver: boolean;
  skipTranslation: boolean;
  targetLang: string;
  languages: { id: string; label: string }[];
  glossaryIds: string[];
  fileRef: RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onFileSelect: (f: File) => void;
  onSkipTranslationChange: (v: boolean) => void;
  onTargetLangChange: (v: string) => void;
  onGlossaryIdsChange: (v: string[]) => void;
  translationProviders: { id: number; name: string }[];
  translationProviderId: number | null;
  onTranslationProviderChange: (id: number | null) => void;
  translationProvidersLoading?: boolean;
  onUploadNext: () => void;
  /** In the demo the file is given, this is its name. */
  demoDatei?: string;
  /** Leaves the demo, only set on the demo page. */
  onBeenden?: () => void;
}

export default function UploadStep(props: UploadStepProps) {
  const {
    onBack,
    hasActiveJob,
    file,
    fileError,
    dragOver,
    skipTranslation,
    targetLang,
    languages,
    glossaryIds,
    fileRef,
    onDragOver,
    onDragLeave,
    onDrop,
    onFileSelect,
    onSkipTranslationChange,
    onTargetLangChange,
    onGlossaryIdsChange,
    translationProviders,
    translationProviderId,
    onTranslationProviderChange,
    translationProvidersLoading = false,
    onUploadNext,
    demoDatei,
    onBeenden,
  } = props;

  const t = useTranslations("tools.screencast");
  const tDemo = useTranslations("tools.screencastDemo");
  const tGlossar = useTranslations("tools.glossarySelector");
  const tCommon = useTranslations("common");
  const gesperrt = !!hasActiveJob || !!demoDatei;
  const [offen, setOffen] = useState<Zeile | null>("file");
  const zeile = (z: Zeile) => ({ offen: offen === z, onToggle: () => setOffen((alt) => (alt === z ? null : z)) });
  const weiterGesperrt = demoDatei ? false : !file || !!hasActiveJob;
  const sprache = languages.find((l) => l.id === targetLang)?.label ?? "";
  const anbieter = translationProvidersLoading
    ? tCommon("providersLoading")
    : translationProviders.find((p) => p.id === translationProviderId)?.name ?? "";
  const glossare = glossaryIds.filter(Boolean).length;

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-baseline justify-between mb-2">
        <h1 className="text-xl font-bold">{t("title")}</h1>
        {demoDatei ? (
          <button
            type="button"
            onClick={onBeenden}
            className="text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors"
            style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
          >
            {tDemo("beenden")}
          </button>
        ) : (
          <Link
            href="/tools/screencast-demo"
            className="text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors"
            style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
          >
            {t("demoBadge")}
          </Link>
        )}
      </div>
      <p className="text-sm text-muted mb-6">{t("intro")}</p>
      {demoDatei && (
        <p className="mb-6 flex items-start gap-2 text-sm text-warn-strong">
          <Info size={14} className="mt-0.5 flex-shrink-0 text-warn" aria-hidden="true" />
          {tDemo("hinweis")}
        </p>
      )}

      {hasActiveJob === true && (
        <div className="mb-6 rounded-lg border border-error-border bg-error-bg px-4 py-4">
          <p className="text-sm font-semibold text-error-strong">
            {t("upload.activeJobsTitle")}
          </p>
          <p className="mt-1 text-sm text-error-strong">
            {t("upload.activeJobsBodyPrefix")}
            <Link href="/my-jobs" className="underline hover:text-error-strong font-medium">
              {t("upload.activeJobsBodyLink")}
            </Link>
            {t("upload.activeJobsBodySuffix")}
          </p>
        </div>
      )}

      {/* On the phone the card dissolves into one list (file, settings), on the desktop settings left, file right. */}
      <div className="-mx-4 lg:mx-0 flex flex-col lg:grid lg:grid-cols-[minmax(0,400px)_1fr] lg:items-start lg:gap-8">
        <div className="contents lg:block min-w-0 lg:rounded-xl lg:border lg:border-border-soft lg:bg-surface lg:p-5">
          <div className="order-3 px-4 py-3.5 border-b border-border-soft lg:hidden">
            <ToggleRow title={t("upload.skipTranslation")} description={skipTranslation ? t("upload.scriptLangHint") : t("upload.autoDetectHint")}
                       checked={skipTranslation} onToggle={() => onSkipTranslationChange(!skipTranslation)} />
          </div>
          <div className="order-3 hidden lg:block">
            <Checkbox checked={skipTranslation} onChange={onSkipTranslationChange}
                      label={t("upload.skipTranslation")} labelClassName="text-sm text-foreground" />
          </div>

          {/* The language sets not only the translation but also the language of the spoken texts,
              so it stays visible when the translation is skipped. */}
          {languages.length > 0 && (
            <EinstellungsFeld titel={skipTranslation ? t("upload.scriptLang") : t("upload.targetLang")} wert={sprache}
                              htmlFor="screencast-sprache" {...zeile("language")}>
              <Select
                id="screencast-sprache"
                value={targetLang}
                onChange={onTargetLangChange}
                ariaLabel={skipTranslation ? t("upload.scriptLang") : t("upload.targetLang")}
                options={languages.map((l) => ({ value: l.id, label: l.label }))}
              />
              <p className="mt-1 text-xs text-muted hidden lg:block">
                {skipTranslation ? t("upload.scriptLangHint") : t("upload.autoDetectHint")}
              </p>
            </EinstellungsFeld>
          )}

          {!skipTranslation && (
            <>
              <EinstellungsFeld titel={t("upload.glossaryLabel")} wert={glossare ? tGlossar("selected", { count: glossare }) : tCommon("emptyValue")}
                                {...zeile("glossary")}>
                <GlossarySelector values={glossaryIds} onChange={onGlossaryIdsChange} className="" />
              </EinstellungsFeld>

              {showProviderField(translationProviders, translationProvidersLoading) && (
                <EinstellungsFeld titel={t("upload.translationProvider")} wert={anbieter} htmlFor="screencast-anbieter" {...zeile("provider")}>
                  <ProviderPicker
                    id="screencast-anbieter"
                    providers={translationProviders}
                    value={translationProviderId}
                    onChange={onTranslationProviderChange}
                    loading={translationProvidersLoading}
                    ariaLabel={t("upload.translationProvider")}
                  />
                </EinstellungsFeld>
              )}
            </>
          )}

          {fileError && (
            <p className="order-3 mt-6 px-4 lg:px-0 text-sm text-error" role="alert">
              {fileError}
            </p>
          )}

          <div className="order-3 hidden lg:block">
            <StepFooter onBack={onBack} nextLabel={t("common.next")} onNext={onUploadNext} nextDisabled={weiterGesperrt} />
          </div>
        </div>

        <div className="order-1 min-w-0 lg:col-start-2 lg:row-start-1 lg:rounded-xl lg:border lg:border-kb/15 lg:bg-kb/5 lg:p-5">
          <EinstellungsFeld titel={t("upload.fileLabel")} wert={demoDatei ?? file?.name ?? tCommon("emptyValue")}
                            className="border-t lg:border-t-0" {...zeile("file")}>
            <div
              onDragOver={gesperrt ? undefined : onDragOver}
              onDragLeave={gesperrt ? undefined : onDragLeave}
              onDrop={gesperrt ? undefined : onDrop}
              onClick={gesperrt ? undefined : () => fileRef.current?.click()}
              className={`
                relative flex flex-col items-center justify-center
                rounded-lg border-2 border-dashed px-6 py-6 lg:py-16
                transition-colors
                ${demoDatei ? "border-kb60 bg-kb20 cursor-default" : hasActiveJob ? "border-border-soft bg-surface opacity-40 cursor-not-allowed" : "cursor-pointer"}
                ${
                  !gesperrt &&
                  (dragOver
                    ? "border-kb bg-kb/5"
                    : file
                      ? "border-kb60 bg-kb20"
                      : "border-border hover:border-kb")
                }
              `}
            >
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                className="hidden"
                disabled={gesperrt}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onFileSelect(f);
                }}
              />
              {demoDatei ? (
                <>
                  <svg className="w-8 h-8 text-kb-dark mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <p className="text-sm font-medium text-foreground">{demoDatei}</p>
                  <p className="text-xs text-muted-soft mt-1">{tDemo("dateiVorgegeben")}</p>
                </>
              ) : file ? (
                <>
                  <svg className="w-8 h-8 text-kb-dark mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <p className="text-sm font-medium text-foreground">{file.name}</p>
                  <p className="text-xs text-muted-soft mt-1">{t("upload.replaceHint")}</p>
                </>
              ) : (
                <>
                  <svg className="w-8 h-8 text-muted-soft mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p className="text-sm text-foreground-soft">
                    {t("upload.dropPrefix")}
                    <span className="text-kb font-medium">{t("upload.dropBrowse")}</span>
                  </p>
                  <p className="text-xs text-muted-soft mt-1">{t("upload.onlyPptx")}</p>
                </>
              )}
            </div>
          </EinstellungsFeld>
        </div>
      </div>

      {/* On the phone the way on stays in reach while scrolling the form and stops at its end. */}
      <div className="lg:hidden sticky bottom-0 z-30 -mx-4 mt-6 border-t border-border-soft bg-background px-4 py-3">
        <button type="button" onClick={onUploadNext} disabled={weiterGesperrt}
          className="w-full px-4 py-3 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
          {t("common.next")}
        </button>
      </div>
    </section>
  );
}
