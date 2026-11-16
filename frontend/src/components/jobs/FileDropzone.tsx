"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { checkUpload } from "@/lib/uploadCheck";

interface FileDropzoneProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  selectedFilename?: string;
  extensions: string[];
  maxMb: number;
  maxBytes: number;
  ariaLabel: string;
  // Optional slower check that runs after extension and size passed.
  extraCheck?: (file: File) => Promise<string | null>;
}

export default function FileDropzone({
  onFileSelected,
  disabled = false,
  selectedFilename,
  extensions,
  maxMb,
  maxBytes,
  ariaLabel,
  extraCheck,
}: FileDropzoneProps) {
  const t = useTranslations("common");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const blocked = disabled || checking;

  const handleFile = async (file: File) => {
    setError(null);
    const problem = checkUpload(file, extensions, maxBytes);
    if (problem === "extension") {
      setError(t("onlyExtsAllowed", { exts: extensions.join(", ") }));
      return;
    }
    if (problem === "size") {
      setError(t("fileTooLarge", { n: maxMb }));
      return;
    }
    if (extraCheck) {
      setChecking(true);
      try {
        const extraError = await extraCheck(file);
        if (extraError) {
          setError(extraError);
          return;
        }
      } finally {
        setChecking(false);
      }
    }
    onFileSelected(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (blocked) return;
    const file = e.dataTransfer.files[0];
    if (file) void handleFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragActive(true);
  };

  const handleDragLeave = () => setDragActive(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) void handleFile(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  const borderClass = dragActive
    ? "border-kb bg-info-bg"
    : selectedFilename
      ? "border-kb60 bg-kb20"
      : "border-border hover:border-kb";

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label={ariaLabel}
        onClick={() => !blocked && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (!blocked) inputRef.current?.click();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb ${borderClass} ${blocked ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        {selectedFilename ? (
          <>
            <svg className="mx-auto h-8 w-8 text-kb-dark mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <p className="text-sm font-medium text-foreground">{selectedFilename}</p>
            <p className="text-xs text-muted-soft mt-1">{t("clickToReplace")}</p>
          </>
        ) : (
          <>
            <svg className="mx-auto h-12 w-12 text-muted-soft mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
            </svg>
            <p className="text-sm font-medium text-muted">
              {t("dropOrBrowse")} <span className="text-kb underline">{t("browse")}</span>
            </p>
            <p className="text-xs text-muted-soft mt-1">
              {extensions.join(", ")}
            </p>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={extensions.join(",")}
        onChange={handleInputChange}
        className="hidden"
        aria-hidden="true"
      />
      {error && (
        <p className="mt-2 text-sm text-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
