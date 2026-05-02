"use client";

import type { DragEvent, RefObject } from "react";
import { useTranslations } from "next-intl";


interface Props {
  file: File | null;
  dragOver: boolean;
  disabled: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onChange: (file: File) => void;
}


export default function UploadZone({
  file, dragOver, disabled, inputRef, onDragOver, onDragLeave, onDrop, onChange,
}: Props) {
  const t = useTranslations("tools.image.uploadZone");
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={`relative mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors ${
        dragOver
          ? "border-kb bg-kb/5"
          : "border-border hover:border-kb"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".png,.jpg,.jpeg"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onChange(f);
        }}
      />
      {file ? (
        <div className="flex items-center gap-3">
          <svg className="h-5 w-5 text-kb" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <div className="text-sm text-foreground-soft">
            <p className="font-medium">{file.name}</p>
            <p className="text-xs text-muted">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        </div>
      ) : (
        <div className="text-center">
          <svg className="mx-auto h-8 w-8 text-muted-soft" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-8-8v12m0-12l-4 4m4-4l4 4" />
          </svg>
          <p className="mt-2 text-sm text-foreground-soft">
            <span className="font-medium text-kb">{t("selectFile")}</span> {t("orDragHere")}
          </p>
          <p className="text-xs text-muted mt-1">{t("constraints")}</p>
        </div>
      )}
    </div>
  );
}
