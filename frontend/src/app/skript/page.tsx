"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScriptFileUpload from "@/components/ScriptFileUpload";
import ScriptStatus from "@/components/ScriptStatus";
import { api } from "@/lib/api";
import type { ScriptState } from "@/types";

export default function SkriptPage() {
    const [state, setState] = useState<ScriptState>("idle");
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [scriptText, setScriptText] = useState<string>("");
    const [downloadName, setDownloadName] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string>("");

    const handleFileSelected = useCallback(async (file: File) => {
        setScriptText("");
        setDownloadName("");
        setErrorMessage("");
        setSelectedFile(file.name);
        setState("processing");

        try {
            const formData = new FormData();
            formData.append("file", file);

            const response = await api.fetch("/api/script", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
                throw new Error(error.detail || `Fehler: ${response.status}`);
            }

            // Get filename from Content-Disposition header
            let filename = "";
            const disposition = response.headers.get("Content-Disposition");
            if (disposition) {
                const utf8Match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/i);
                if (utf8Match) {
                    filename = decodeURIComponent(utf8Match[1].trim());
                } else {
                    const basicMatch = disposition.match(/filename="?([^";\n]+)"?/i);
                    if (basicMatch) {
                        filename = decodeURIComponent(basicMatch[1].trim());
                    }
                }
            }
            if (!filename) {
                const stem = file.name.replace(/\.[^.]+$/, "");
                filename = `${stem}_skript.md`;
            }

            const text = await response.text();
            setScriptText(text);
            setDownloadName(filename);
            setState("done");
        } catch (err) {
            setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
            setState("error");
        }
    }, []);

    const handleDownload = () => {
        if (!scriptText) return;
        const blob = new Blob([scriptText], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = downloadName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleReset = () => {
        setState("idle");
        setSelectedFile("");
        setScriptText("");
        setDownloadName("");
        setErrorMessage("");
    };

    return (
        <ProtectedRoute>
            <Header showLogout />
            <div className="max-w-3xl mx-auto px-4 py-8">
                <section>
                    <h1 className="text-xl font-bold text-gray-900 mb-1">Skript erstellen</h1>
                    <p className="text-sm text-gray-500 mb-6">
                        Laden Sie ein Dokument hoch und lassen Sie daraus ein fließendes Vorleseskript erstellen.
                    </p>

                    <ScriptFileUpload
                        onFileSelected={handleFileSelected}
                        disabled={state === "processing"}
                    />

                    {selectedFile && state !== "idle" && (
                        <p className="mt-3 text-xs text-gray-500">Datei: {selectedFile}</p>
                    )}

                    <ScriptStatus
                        state={state}
                        fileName={downloadName}
                        scriptText={scriptText}
                        errorMessage={errorMessage}
                        onDownload={handleDownload}
                        onReset={handleReset}
                    />
                </section>
            </div>
        </ProtectedRoute>
    );
}
