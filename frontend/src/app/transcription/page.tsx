"use client";

import { useCallback, useState } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import TranscriptionFileUpload from "@/components/TranscriptionFileUpload";
import TranscriptionStatus from "@/components/TranscriptionStatus";
import { backendApi } from "@/lib/api";
import type { TranscriptionState } from "@/types";

const TASK_OPTIONS = [
  { value: "transcribe", label: "In Originalsprache transkribieren" },
  { value: "translate", label: "Transkribieren und ins Englische übersetzen" },
];

const FORMAT_OPTIONS = [
  { value: "text", label: "Text (.txt)" },
  { value: "srt", label: "SRT (.srt)" },
  { value: "vtt", label: "VTT (.vtt)" },
];

export default function TranscriptionPage() {
  const [state, setState] = useState<TranscriptionState>("idle");
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [selectedFile, setSelectedFile] = useState<string>("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [downloadName, setDownloadName] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string>("");

  const [task, setTask] = useState("transcribe");
  const [responseFormat, setResponseFormat] = useState("text");

  const [transcriptText, setTranscriptText] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryError, setSummaryError] = useState("");

  const isProcessing = state === "uploading" || state === "processing";

  const handleFileSelected = useCallback((file: File) => {
    setPendingFile(file);
    setSelectedFile(file.name);
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setTranscriptText(null);
    setSummary(null);
    setSummaryError("");
    setState("idle");
  }, []);

  const handleSubmit = async () => {
    if (!pendingFile || isProcessing) return;
    setState("uploading");
    try {
      setState("processing");
      const { blob, filename } = await backendApi.uploadFileWithFields(
        "/transcription",
        pendingFile,
        { task, response_format: responseFormat },
      );
      setDownloadBlob(blob);
      setDownloadName(filename);
      if (responseFormat === "text") {
        setTranscriptText(await blob.text());
      }
      setState("done");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
      setState("error");
    }
  };

  const handleDownload = () => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
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
    setDownloadBlob(null);
    setDownloadName("");
    setErrorMessage("");
    setTranscriptText(null);
    setSummary(null);
    setSummaryError("");
  };

  const handleSummarize = async () => {
    if (!transcriptText) return;
    setSummarizing(true);
    setSummary(null);
    setSummaryError("");
    try {
      const response = await backendApi.fetch("/transcription/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: transcriptText, task }),
      });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(err.detail || `Fehler: ${response.status}`);
      }
      const data = await response.json();
      const summaryText = data.summary ?? "";
      setSummary(summaryText);

      const stem = selectedFile.replace(/\.[^.]+$/, "") || "transkript";
      const blob = new Blob([summaryText], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${stem}_zusammenfassung.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setSummaryError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setSummarizing(false);
    }
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Transkription</h1>
          <p className="text-sm text-gray-500 mb-6">
            Laden Sie eine Audio- oder Videodatei hoch, um sie zu transkribieren oder ins Englische zu übersetzen.
          </p>

          <TranscriptionFileUpload
            onFileSelected={handleFileSelected}
            disabled={isProcessing}
          />
          {selectedFile && (
            <p className="mt-2 text-sm font-medium text-gray-700">{selectedFile}</p>
          )}

          {/* Task selection */}
          <div className="mt-6 mb-4">
            <label htmlFor="task-select" className="block text-sm font-medium text-gray-700 mb-2">
              Aktion
            </label>
            <select
              id="task-select"
              value={task}
              onChange={(e) => setTask(e.target.value)}
              disabled={isProcessing}
              className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {TASK_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Format selection – radio buttons */}
          <div className="mb-6">
            <span className="block text-sm font-medium text-gray-700 mb-2">Ausgabeformat</span>
            <div className="flex gap-6">
              {FORMAT_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name="response-format"
                    value={opt.value}
                    checked={responseFormat === opt.value}
                    onChange={() => setResponseFormat(opt.value)}
                    disabled={isProcessing}
                    className="accent-[#0066cc]"
                  />
                  <span className="text-sm text-gray-700">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <button
              onClick={handleSubmit}
              disabled={!pendingFile || isProcessing}
              className="self-start px-5 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isProcessing && (
                <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
              )}
              {isProcessing ? "Transkription läuft…" : "Transkription starten"}
            </button>
          </div>

          <TranscriptionStatus
            state={state}
            fileName={downloadName}
            errorMessage={errorMessage}
            onDownload={handleDownload}
            onReset={handleReset}
          />

          {/* Summarize button — only for plain text transcriptions */}
          {transcriptText && state === "done" && (
            <div className="mt-4">
              <button
                onClick={handleSummarize}
                disabled={summarizing}
                className="px-4 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {summarizing && (
                  <span className="inline-block animate-spin rounded-full h-4 w-4 border-b-2 border-white shrink-0" />
                )}
                {summarizing ? "Zusammenfassung wird erstellt…" : "Zusammenfassung"}
              </button>
            </div>
          )}

          {summaryError && (
            <p className="mt-4 text-sm text-red-600" role="alert">{summaryError}</p>
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}
