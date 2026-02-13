"use client";

import type { ScriptState } from "@/types";

interface ScriptStatusProps {
    state: ScriptState;
    fileName: string;
    scriptText: string;
    errorMessage: string;
    onDownload: () => void;
    onReset: () => void;
}

export default function ScriptStatus({
    state,
    fileName,
    scriptText,
    errorMessage,
    onDownload,
    onReset,
}: ScriptStatusProps) {
    if (state === "idle") return null;

    return (
        <div className="mt-6">
            {/* Processing state */}
            {state === "processing" && (
                <div className="flex items-center gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4">
                    <svg className="h-5 w-5 animate-spin text-[#0066cc]" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                    </svg>
                    <span className="text-sm text-blue-800">Skript wird erstellt… Das kann je nach Dokumentlänge etwas dauern.</span>
                </div>
            )}

            {/* Done state */}
            {state === "done" && (
                <div className="space-y-4">
                    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <svg className="h-5 w-5 text-green-600" viewBox="0 0 20 20" fill="currentColor">
                                    <path
                                        fillRule="evenodd"
                                        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                                <span className="text-sm font-medium text-green-800">Skript erstellt</span>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={onDownload}
                                    className="rounded-md bg-[#0066cc] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#0055aa] transition-colors"
                                >
                                    {fileName} herunterladen
                                </button>
                                <button
                                    onClick={onReset}
                                    className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
                                >
                                    Neues Dokument
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Script preview */}
                    {scriptText && (
                        <div className="rounded-lg border border-gray-200 bg-white">
                            <div className="border-b border-gray-200 px-4 py-3">
                                <h3 className="text-sm font-medium text-gray-700">Vorschau des generierten Skripts</h3>
                            </div>
                            <div className="p-4 max-h-96 overflow-y-auto">
                                <pre className="text-sm text-gray-800 whitespace-pre-wrap font-sans leading-relaxed">
                                    {scriptText}
                                </pre>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Error state */}
            {state === "error" && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <svg className="h-5 w-5 text-red-600" viewBox="0 0 20 20" fill="currentColor">
                                <path
                                    fillRule="evenodd"
                                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                                    clipRule="evenodd"
                                />
                            </svg>
                            <span className="text-sm text-red-800">{errorMessage || "Unbekannter Fehler"}</span>
                        </div>
                        <button
                            onClick={onReset}
                            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
                        >
                            Erneut versuchen
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
