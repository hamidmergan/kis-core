"use client";

import type { DragEvent, RefObject } from "react";
import GlossarySelector from "@/components/glossary/GlossarySelector";

const ACCEPTED_EXTENSIONS = [".pptx"];

interface UploadStepProps {
  showDemoLink: boolean;
  hasActiveJob: boolean | null;
  file: File | null;
  fileError: string | null;
  dragOver: boolean;
  sourceLang: string;
  targetLang: string;
  languages: { id: string; label: string }[];
  glossaryIds: string[];
  fileRef: RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onFileSelect: (f: File) => void;
  onSourceLangChange: (v: string) => void;
  onTargetLangChange: (v: string) => void;
  onGlossaryIdsChange: (v: string[]) => void;
  onUploadNext: () => void;
}

export default function UploadStep(props: UploadStepProps) {
  const {
    showDemoLink,
    hasActiveJob,
    file,
    fileError,
    dragOver,
    sourceLang,
    targetLang,
    languages,
    glossaryIds,
    fileRef,
    onDragOver,
    onDragLeave,
    onDrop,
    onFileSelect,
    onSourceLangChange,
    onTargetLangChange,
    onGlossaryIdsChange,
    onUploadNext,
  } = props;

  return (
    <section className="animate-[fadeIn_0.3s_ease-out]">
      <div className="flex items-baseline justify-between mb-1">
        <h1 className="text-xl font-bold">Screencast</h1>
        {showDemoLink && (
          <a
            href="/tools/screencast-demo"
            className="text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors"
            style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
          >
            Demo ansehen →
          </a>
        )}
      </div>
      <p className="text-sm text-muted mb-6">
        Aus PowerPoint-Folien ein vertontes Video erzeugen, wahlweise in einer anderen Sprache.
      </p>

      {hasActiveJob === true && (
        <div className="mb-6 rounded-lg border border-error-border bg-error-bg px-4 py-4">
          <p className="text-sm font-semibold text-error-strong">
            Sie haben bereits 5 Jobs in der Warteschlange, kein weiterer ist möglich.
          </p>
          <p className="mt-1 text-sm text-error-strong">
            Warten Sie bis ein Job abgeschlossen ist oder löschen Sie einen in der{" "}
            <a href="/my-jobs" className="underline hover:text-error-strong font-medium">
              Jobliste
            </a>
            .
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
                ? "border-success-border bg-success-bg"
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
            <svg className="w-8 h-8 text-success mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <p className="text-sm font-medium text-foreground">{file.name}</p>
            <p className="text-xs text-muted-soft mt-1">Klicken oder ziehen Sie eine andere Datei hierher</p>
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
              Datei hierher ziehen oder <span className="text-kb font-medium">durchsuchen</span>
            </p>
            <p className="text-xs text-muted-soft mt-1">Nur .pptx-Datei</p>
          </>
        )}
      </div>

      <label className="flex items-start gap-3 mb-4 cursor-pointer select-none">
        <input
          type="checkbox"
          checked={sourceLang === targetLang}
          onChange={(e) => {
            if (e.target.checked) onSourceLangChange(targetLang);
            else onSourceLangChange("DE");
          }}
          className="mt-0.5 h-4 w-4 rounded border-border text-kb focus:ring-kb"
        />
        <span className="text-sm font-medium text-foreground-soft">
          Präsentation bereits übersetzt (Übersetzung überspringen)
        </span>
      </label>

      {sourceLang !== targetLang && (
        <>
          {languages.length > 0 && (
            <div className="flex gap-3 mb-4">
              <div className="flex-1">
                <label className="block text-xs font-medium text-muted mb-1">Quellsprache</label>
                <select
                  value={sourceLang}
                  onChange={(e) => onSourceLangChange(e.target.value)}
                  disabled
                  className="w-full rounded-md border border-border text-sm py-2 px-3 focus:ring-2 focus:ring-kb focus:border-kb disabled:opacity-50"
                >
                  {languages.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-xs font-medium text-muted mb-1">Zielsprache</label>
                <select
                  value={targetLang}
                  onChange={(e) => onTargetLangChange(e.target.value)}
                  disabled
                  className="w-full rounded-md border border-border text-sm py-2 px-3 focus:ring-2 focus:ring-kb focus:border-kb disabled:opacity-50"
                >
                  {languages.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <GlossarySelector values={glossaryIds} onChange={onGlossaryIdsChange} />
        </>
      )}

      {fileError && (
        <p className="mb-4 text-sm text-error" role="alert">
          {fileError}
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onUploadNext}
          disabled={!file || !!hasActiveJob}
          className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Weiter
        </button>
      </div>
    </section>
  );
}
