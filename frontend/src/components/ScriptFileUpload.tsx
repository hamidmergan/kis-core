"use client";

import { useCallback, useRef, useState } from "react";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";

const ACCEPTED_EXTENSIONS = [".docx", ".pptx", ".md", ".tex", ".txt"];

interface ScriptFileUploadProps {
    onFileSelected: (file: File) => void;
    disabled?: boolean;
    selectedFilename?: string;
}

export default function ScriptFileUpload({ onFileSelected, disabled = false, selectedFilename }: ScriptFileUploadProps) {
    const [dragActive, setDragActive] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const validateFile = (file: File): string | null => {
        const ext = "." + file.name.split(".").pop()?.toLowerCase();
        if (!ACCEPTED_EXTENSIONS.includes(ext)) {
            return `Nur ${ACCEPTED_EXTENSIONS.join(", ")} Dateien erlaubt`;
        }
        if (file.size > MAX_UPLOAD_BYTES) {
            return `Datei zu groß (max ${MAX_UPLOAD_MB} MB)`;
        }
        return null;
    };

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
        [onFileSelected]
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
        ? "border-[#0066cc] bg-blue-50"
        : selectedFilename
            ? "border-green-400 bg-green-50"
            : "border-gray-300 hover:border-gray-400";

    return (
        <div>
            <div
                role="button"
                tabIndex={0}
                aria-label="Datei für Skripterstellung auswählen"
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
                className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] ${borderClass} ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
            >
                {selectedFilename ? (
                    <>
                        <svg className="mx-auto h-8 w-8 text-green-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        <p className="text-sm font-medium text-gray-800">{selectedFilename}</p>
                        <p className="text-xs text-gray-400 mt-1">Klicken um zu ersetzen</p>
                    </>
                ) : (
                    <>
                        <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                        </svg>
                        <p className="text-sm font-medium text-gray-500">
                            Datei hierher ziehen oder <span className="text-[#0066cc] underline">durchsuchen</span>
                        </p>
                        <p className="text-xs text-gray-400 mt-1">
                            {ACCEPTED_EXTENSIONS.join(", ")} (max {MAX_UPLOAD_MB} MB)
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
                <p className="mt-2 text-sm text-red-600" role="alert">
                    {error}
                </p>
            )}
        </div>
    );
}
