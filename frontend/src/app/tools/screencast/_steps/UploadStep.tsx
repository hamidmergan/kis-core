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
            className="text-xs font-semibold px-3.5 py-1.5 rounded transition-opacity hover:opacity-80"
            style={{ backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" }}
          >
            Demo ansehen →
          </a>
        )}
      </div>
      <p className="text-sm text-gray-500 mb-6">
        Aus PowerPoint-Folien ein vertontes Video erzeugen, wahlweise in einer anderen Sprache.
      </p>

      {hasActiveJob === true && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-4">
          <p className="text-sm font-semibold text-red-800">
            Sie haben bereits 5 Jobs in der Warteschlange, kein weiterer ist möglich.
          </p>
          <p className="mt-1 text-sm text-red-700">
            Warten Sie bis ein Job abgeschlossen ist oder löschen Sie einen in der{" "}
            <a href="/my-jobs" className="underline hover:text-red-900 font-medium">
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
          ${hasActiveJob ? "border-gray-200 bg-gray-50 opacity-40 cursor-not-allowed" : "cursor-pointer"}
          ${
            !hasActiveJob &&
            (dragOver
              ? "border-primary bg-primary/5"
              : file
                ? "border-green-400 bg-green-50"
                : "border-gray-300 hover:border-primary")
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
            <svg className="w-8 h-8 text-green-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <p className="text-sm font-medium text-gray-900">{file.name}</p>
            <p className="text-xs text-gray-400 mt-1">Klicken oder ziehen Sie eine andere Datei hierher</p>
          </>
        ) : (
          <>
            <svg className="w-8 h-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="text-sm text-gray-600">
              Datei hierher ziehen oder <span className="text-primary font-medium">durchsuchen</span>
            </p>
            <p className="text-xs text-gray-400 mt-1">Nur .pptx-Datei</p>
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
          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
        />
        <span className="text-sm font-medium text-gray-700">
          Präsentation bereits übersetzt (Übersetzung überspringen)
        </span>
      </label>

      {sourceLang !== targetLang && (
        <>
          {languages.length > 0 && (
            <div className="flex gap-3 mb-4">
              <div className="flex-1">
                <label className="block text-xs font-medium text-gray-500 mb-1">Quellsprache</label>
                <select
                  value={sourceLang}
                  onChange={(e) => onSourceLangChange(e.target.value)}
                  disabled
                  className="w-full rounded-md border border-gray-300 text-sm py-2 px-3 focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50"
                >
                  {languages.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-xs font-medium text-gray-500 mb-1">Zielsprache</label>
                <select
                  value={targetLang}
                  onChange={(e) => onTargetLangChange(e.target.value)}
                  disabled
                  className="w-full rounded-md border border-gray-300 text-sm py-2 px-3 focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50"
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
        <p className="mb-4 text-sm text-red-600" role="alert">
          {fileError}
        </p>
      )}

      <div className="flex gap-3">
        <button
          onClick={onUploadNext}
          disabled={!file || !!hasActiveJob}
          className="flex-1 px-4 py-3 btn-primary text-sm font-medium rounded-md  focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Weiter
        </button>
      </div>
    </section>
  );
}
