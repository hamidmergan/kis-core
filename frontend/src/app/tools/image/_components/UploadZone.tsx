"use client";

import type { DragEvent, RefObject } from "react";


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
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={`relative mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors ${
        dragOver
          ? "border-primary bg-primary/5"
          : "border-gray-300 hover:border-primary"
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
          <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <div className="text-sm text-gray-700">
            <p className="font-medium">{file.name}</p>
            <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
          </div>
        </div>
      ) : (
        <div className="text-center">
          <svg className="mx-auto h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-8-8v12m0-12l-4 4m4-4l4 4" />
          </svg>
          <p className="mt-2 text-sm text-gray-600">
            <span className="font-medium text-primary">Datei auswählen</span> oder hierher ziehen
          </p>
          <p className="text-xs text-gray-500 mt-1">PNG oder JPG, max. 20 MB</p>
        </div>
      )}
    </div>
  );
}
