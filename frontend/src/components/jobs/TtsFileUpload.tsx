"use client";

import { useCallback, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";

const ACCEPTED_EXTENSIONS = [".docx", ".md", ".txt"];

interface TtsFileUploadProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  selectedFilename?: string;
}

export default function TtsFileUpload({ onFileSelected, disabled = false, selectedFilename }: TtsFileUploadProps) {
  const tCommon = useTranslations("common");
  const tUpload = useTranslations("tools.tts.upload");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback((file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      return tCommon("onlyExtsAllowed", { exts: ACCEPTED_EXTENSIONS.join(", ") });
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return tCommon("fileTooLarge", { n: MAX_UPLOAD_MB });
    }
    return null;
  }, [tCommon]);

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      onFileSelected(file);
    },
    [onFileSelected, validateFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragActive(true);
  };

  const handleDragLeave = () => setDragActive(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    if (inputRef.current) inputRef.current.value = "";
  };

  const borderClass = dragActive
    ? "border-kb bg-info-bg"
    : selectedFilename
      ? "border-success-border bg-success-bg"
      : "border-border hover:border-kb";

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        aria-label={tUpload("selectFileAria")}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (!disabled) inputRef.current?.click();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb ${borderClass} ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        {selectedFilename ? (
          <>
            <svg className="mx-auto h-8 w-8 text-success mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <p className="text-sm font-medium text-foreground">{selectedFilename}</p>
            <p className="text-xs text-muted-soft mt-1">{tCommon("clickToReplace")}</p>
          </>
        ) : (
          <>
            <svg
              className="mx-auto h-12 w-12 text-muted-soft mb-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
              />
            </svg>
            <p className="text-sm font-medium text-muted">
              {tCommon("dropOrBrowse")} <span className="text-kb underline">{tCommon("browse")}</span>
            </p>
            <p className="text-xs text-muted-soft mt-1">
              {ACCEPTED_EXTENSIONS.join(", ")}
            </p>
          </>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
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
