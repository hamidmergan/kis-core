"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScriptFileUpload from "@/components/ScriptFileUpload";
import ScriptStatus from "@/components/ScriptStatus";
import GlossarySelector from "@/components/GlossarySelector";
import PromptChips from "@/components/PromptChips";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api } from "@/lib/api";
import type { ScriptState } from "@/types";

export default function SkriptPage() {
    const { mergeToApiJson } = useGlossaries();
    const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);

    const [state, setState] = useState<ScriptState>("idle");
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [userPrompt, setUserPrompt] = useState<string>("");
    const [scriptText, setScriptText] = useState<string>("");
    const [downloadName, setDownloadName] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string>("");

    const handleFileSelected = useCallback((file: File) => {
        setPendingFile(file);
        setSelectedFile(file.name);
        setScriptText("");
        setDownloadName("");
        setErrorMessage("");
        setState("idle");
    }, []);

    const handleSubmit = async () => {
        if (!pendingFile || state === "processing") return;
        setState("processing");

        try {
            const formData = new FormData();
            formData.append("file", pendingFile);
            if (userPrompt) formData.append("user_prompt", userPrompt);
            const glossaryJson = mergeToApiJson(glossaryIds);
            if (glossaryJson) formData.append("glossary_json", glossaryJson);

            const response = await api.fetch("/api/script", {
                method: "POST",
                body: formData,
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
                throw new Error(error.detail || `Fehler: ${response.status}`);
            }

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
                const stem = pendingFile.name.replace(/\.[^.]+$/, "");
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
    };

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
        setPendingFile(null);
        setSelectedFile("");
        setUserPrompt("");
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
                    {selectedFile && (
                        <p className="mt-2 text-sm font-medium text-gray-700">{selectedFile}</p>
                    )}

                    <GlossarySelector
                        values={glossaryIds}
                        onChange={setGlossaryIds}
                    />

                    <div className="mb-6">
                        <label htmlFor="skript-user-prompt" className="block text-sm font-medium text-gray-700 mb-2">
                            Zusätzliche Anweisungen{" "}
                            <span className="font-normal text-gray-400">(optional)</span>
                        </label>
                        <textarea
                            id="skript-user-prompt"
                            value={userPrompt}
                            onChange={(e) => setUserPrompt(e.target.value)}
                            disabled={state === "processing"}
                            rows={3}
                            placeholder="z. B. Kurze Sätze verwenden, formelle Sprache …"
                            className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed resize-y"
                        />
                        <PromptChips
                            onChipClick={(chip) =>
                                setUserPrompt((prev) =>
                                    prev.trim() ? `${prev.trimEnd()}\n- ${chip}` : `- ${chip}`,
                                )
                            }
                            disabled={state === "processing"}
                        />
                    </div>

                    <div className="mb-6">
                        <button
                            onClick={handleSubmit}
                            disabled={!pendingFile || state === "processing"}
                            className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {state === "processing" && (
                                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
                            )}
                            {state === "processing" ? "Skript wird erstellt…" : "Skript erstellen"}
                        </button>
                    </div>

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
