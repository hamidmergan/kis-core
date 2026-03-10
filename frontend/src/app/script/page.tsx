"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScriptFileUpload from "@/components/ScriptFileUpload";
import GlossarySelector from "@/components/GlossarySelector";
import PromptChips from "@/components/PromptChips";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";

export default function SkriptPage() {
    const { mergeToApiJson } = useGlossaries();
    const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);

    const [processing, setProcessing] = useState(false);
    const [pendingFile, setPendingFile] = useState<File | null>(null);
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [userPrompt, setUserPrompt] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string>("");
    const [stallMessage, setStallMessage] = useState<string>("");
    const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);

    const handleFileSelected = useCallback((file: File) => {
        setPendingFile(file);
        setSelectedFile(file.name);
        setErrorMessage("");
        setDoneJobUuid(null);
    }, []);

    const handleSubmit = async () => {
        if (!pendingFile || processing) return;
        setProcessing(true);
        setErrorMessage("");
        setStallMessage("");
        setDoneJobUuid(null);
        try {
            const formData = new FormData();
            formData.append("file", pendingFile);
            if (userPrompt) formData.append("user_prompt", userPrompt);
            const glossaryJson = mergeToApiJson(glossaryIds);
            if (glossaryJson) formData.append("glossary_json", glossaryJson);

            const response = await api.fetch("/api/script", { method: "POST", body: formData });
            if (!response.ok) {
                const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
                throw new Error(parseDetail(error.detail, `Fehler: ${response.status}`));
            }
            const data = await response.json();
            window.dispatchEvent(new Event("kis-jobs-changed"));
            await pollJob(data.job_uuid, undefined, 3000, undefined,
                () => setStallMessage("Läuft noch – große Dokumente können einige Minuten dauern…"),
                60_000,
            );
            setDoneJobUuid(data.job_uuid);
        } catch (err) {
            setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
        } finally {
            setProcessing(false);
        }
    };

    const handleDownload = async () => {
        if (!doneJobUuid) return;
        try {
            const { blob, filename } = await downloadJobAsBlob(doneJobUuid);
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            setErrorMessage(err instanceof Error ? err.message : "Download fehlgeschlagen");
        }
    };

    const handleReset = () => {
        setPendingFile(null);
        setSelectedFile("");
        setUserPrompt("");
        setErrorMessage("");
        setDoneJobUuid(null);
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

                    <ScriptFileUpload onFileSelected={handleFileSelected} disabled={processing} selectedFilename={selectedFile || undefined} />

                    <GlossarySelector values={glossaryIds} onChange={setGlossaryIds} />

                    <div className="mb-6">
                        <label htmlFor="skript-user-prompt" className="block text-sm font-medium text-gray-700 mb-2">
                            Zusätzliche Anweisungen{" "}
                            <span className="font-normal text-gray-400">(optional)</span>
                        </label>
                        <textarea
                            id="skript-user-prompt"
                            value={userPrompt}
                            onChange={(e) => setUserPrompt(e.target.value)}
                            disabled={processing}
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
                            disabled={processing}
                        />
                    </div>

                    <div className="mb-6">
                        <button
                            onClick={handleSubmit}
                            disabled={!pendingFile || processing}
                            className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {processing && (
                                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
                            )}
                            {processing ? "Wird verarbeitet…" : "Skript erstellen"}
                        </button>
                    </div>

                    {stallMessage && !errorMessage && (
                        <p className="text-sm text-amber-600" role="status">{stallMessage}</p>
                    )}

                    {errorMessage && (
                        <p className="text-sm text-red-600" role="alert">{errorMessage}</p>
                    )}

                    {doneJobUuid && (
                        <div className="mt-2 flex items-center gap-3">
                            <button
                                onClick={handleDownload}
                                className="px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
                            >
                                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                Skript
                            </button>
                            <button
                                onClick={handleReset}
                                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 transition-colors"
                            >
                                Neue Datei
                            </button>
                        </div>
                    )}
                </section>
            </div>
        </ProtectedRoute>
    );
}
