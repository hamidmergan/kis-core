"use client";

import type { DragEvent, RefObject } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import GlossarySelector from "@/components/glossary/GlossarySelector";
import Select from "@/components/ui/Select";
import StepFooter from "./StepFooter";

const ACCEPTED_EXTENSIONS = [".pptx"];

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
  onUploadNext: () => void;
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
    onUploadNext,
  } = props;

  const t = useTranslations("tools.screencast");

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-baseline justify-between mb-2">
        <h1 className="text-xl font-bold">{t("title")}</h1>
        <Link
          href="/tools/screencast-demo"
          className="text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors"
          style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
        >
          {t("demoBadge")}
        </Link>
      </div>
      <p className="text-sm text-muted mb-6">{t("intro")}</p>

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

      <div
        onDragOver={hasActiveJob ? undefined : onDragOver}
        onDragLeave={hasActiveJob ? undefined : onDragLeave}
        onDrop={hasActiveJob ? undefined : onDrop}
        onClick={hasActiveJob ? undefined : () => fileRef.current?.click()}
        className={`
          relative mb-4 flex flex-col items-center justify-center
          rounded-lg border-2 border-dashed px-6 py-10
          transition-colors
          ${hasActiveJob ? "border-border-soft bg-surface opacity-40 cursor-not-allowed" : "cursor-pointer"}
          ${
            !hasActiveJob &&
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
          disabled={!!hasActiveJob}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFileSelect(f);
          }}
        />
        {file ? (
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

      <label className="flex items-start gap-3 mb-4 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={skipTranslation}
          onChange={(e) => onSkipTranslationChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-border text-kb focus:ring-kb"
        />
        <span className="text-sm font-medium text-foreground-soft">
          {t("upload.skipTranslation")}
        </span>
      </label>

      {/* Die Sprache steuert nicht nur die Uebersetzung, sondern auch die Sprache der
          Sprechtexte. Wird die Uebersetzung uebersprungen, muss das Feld deshalb sichtbar
          bleiben, sonst gilt still der Standard und das Video spricht die falsche Sprache. */}
      {languages.length > 0 && (
        <div className="mb-4">
          <label className="block text-xs font-medium text-muted mb-1">
            {skipTranslation ? t("upload.scriptLang") : t("upload.targetLang")}
          </label>
          <Select
            value={targetLang}
            onChange={onTargetLangChange}
            options={languages.map((l) => ({ value: l.id, label: l.label }))}
          />
          <p className="mt-1 text-xs text-muted">
            {skipTranslation ? t("upload.scriptLangHint") : t("upload.autoDetectHint")}
          </p>
        </div>
      )}

      {!skipTranslation && (
        <>
          <GlossarySelector values={glossaryIds} onChange={onGlossaryIdsChange} />

          {translationProviders.length > 1 && (
            <div className="mb-4">
              <label className="block text-xs font-medium text-muted mb-1">
                {t("upload.translationProvider")}
              </label>
              <Select
                value={translationProviderId != null ? String(translationProviderId) : ""}
                onChange={(v) => onTranslationProviderChange(v ? Number(v) : null)}
                options={translationProviders.map((p) => ({ value: String(p.id), label: p.name }))}
              />
            </div>
          )}
        </>
      )}

      {fileError && (
        <p className="mb-4 text-sm text-error" role="alert">
          {fileError}
        </p>
      )}

      <StepFooter
        onBack={onBack}
        nextLabel={t("common.next")}
        onNext={onUploadNext}
        nextDisabled={!file || !!hasActiveJob}
      />
    </section>
  );
}
