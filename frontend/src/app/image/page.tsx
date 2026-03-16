"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { MAX_IMAGE_BYTES } from "@/lib/constants";

type Tab = "generate" | "edit" | "analyze";

const SIZES = ["1024x1024", "1280x720"] as const;
const COUNTS = [1, 2, 3, 4] as const;
const ALLOWED_EXTS = new Set([".png", ".jpg", ".jpeg"]);

function validateImageFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return "Nur PNG oder JPG erlaubt";
  if (file.size > MAX_IMAGE_BYTES) return "Bild zu groß (max 20 MB)";
  return null;
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex justify-center items-center gap-2 mt-6" role="status" aria-live="polite">
      <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-[#004261]" />
      <p className="text-sm text-gray-500 animate-pulse">{label}</p>
    </div>
  );
}

function UploadZone({
  file,
  dragOver,
  disabled,
  inputRef,
  onDragOver,
  onDragLeave,
  onDrop,
  onChange,
}: {
  file: File | null;
  dragOver: boolean;
  disabled: boolean;
  inputRef: React.RefObject<HTMLInputElement | null>;
  onDragOver: (e: DragEvent) => void;
  onDragLeave: (e: DragEvent) => void;
  onDrop: (e: DragEvent) => void;
  onChange: (file: File) => void;
}) {
  return (
    <div
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className={`relative mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors ${
        dragOver
          ? "border-[#004261] bg-[#004261]/5"
          : file
            ? "border-green-400 bg-green-50"
            : "border-gray-300 hover:border-gray-400"
      } ${disabled ? "opacity-50 pointer-events-none" : ""}`}
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
        <>
          <svg className="w-6 h-6 text-green-500 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <p className="text-sm font-medium text-gray-900">{file.name}</p>
          <p className="text-xs text-gray-400 mt-0.5">Klicken oder ziehen um zu ersetzen</p>
        </>
      ) : (
        <>
          <svg className="w-8 h-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p className="text-sm text-gray-600">
            Bild hierher ziehen oder{" "}
            <span className="text-[#004261] font-medium">durchsuchen</span>
          </p>
          <p className="text-xs text-gray-400 mt-1">PNG oder JPG</p>
        </>
      )}
    </div>
  );
}

export default function ImagePage() {
  const [activeTab, setActiveTab] = useState<Tab>("generate");

  // ── Tab 1: Text zu Bild ──
  const [genPrompt, setGenPrompt] = useState("");
  const [genSize, setGenSize] = useState("1024x1024");
  const [genN, setGenN] = useState(1);
  const [genLoading, setGenLoading] = useState(false);
  const [genSpinnerLabel, setGenSpinnerLabel] = useState("Wird generiert…");
  const [genError, setGenError] = useState("");
  const [genResults, setGenResults] = useState<Array<{ url: string; filename: string }>>([]);
  const [genJobUuid, setGenJobUuid] = useState<string | null>(null);

  // ── Tab 2: Bild bearbeiten ──
  const [editFile, setEditFile] = useState<File | null>(null);
  const [editDragOver, setEditDragOver] = useState(false);
  const [editPrompt, setEditPrompt] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editSpinnerLabel, setEditSpinnerLabel] = useState("Wird bearbeitet…");
  const [editError, setEditError] = useState("");
  const [editResultUrl, setEditResultUrl] = useState<string | null>(null);
  const [editResultFilename, setEditResultFilename] = useState<string | null>(null);
  const [editPreviewUrl, setEditPreviewUrl] = useState<string | null>(null);
  const editFileRef = useRef<HTMLInputElement>(null);

  // ── Tab 3: Bild analysieren ──
  const [analyzeFile, setAnalyzeFile] = useState<File | null>(null);
  const [analyzeDragOver, setAnalyzeDragOver] = useState(false);
  const [analyzePrompt, setAnalyzePrompt] = useState("");
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeSpinnerLabel, setAnalyzeSpinnerLabel] = useState("Wird analysiert…");
  const [analyzeError, setAnalyzeError] = useState("");
  const [analyzeResultText, setAnalyzeResultText] = useState<string | null>(null);
  const [analyzePreviewUrl, setAnalyzePreviewUrl] = useState<string | null>(null);
  const analyzeFileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!editFile) { setEditPreviewUrl(null); return; }
    const url = URL.createObjectURL(editFile);
    setEditPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [editFile]);

  useEffect(() => {
    if (!analyzeFile) { setAnalyzePreviewUrl(null); return; }
    const url = URL.createObjectURL(analyzeFile);
    setAnalyzePreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [analyzeFile]);

  // ── Tab 1 handler ──
  const handleGenerate = useCallback(async () => {
    if (!genPrompt.trim()) return;
    setGenLoading(true);
    setGenSpinnerLabel("Wird generiert…");
    setGenError("");
    setGenResults([]);
    setGenJobUuid(null);
    try {
      const formData = new FormData();
      formData.append("prompt", genPrompt);
      formData.append("size", genSize);
      formData.append("n", String(genN));
      const response = await backendApi.fetch("/image/generate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      const jobStatus = await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setGenSpinnerLabel("Läuft noch – Bildgenerierung kann etwas länger dauern…"),
        60_000,
      );
      setGenJobUuid(data.job_uuid);
      const inlined = jobStatus.result as { images?: Array<{ b64_json: string; filename: string }> } | null;
      if (inlined?.images) {
        // Multiple images: base64 already inlined in job status response
        const results = inlined.images.map((img) => {
          const bytes = Uint8Array.from(atob(img.b64_json), (c) => c.charCodeAt(0));
          const imgBlob = new Blob([bytes], { type: "image/png" });
          return { url: URL.createObjectURL(imgBlob), filename: img.filename };
        });
        setGenResults(results);
      } else {
        // Single image: fetch PNG from download endpoint
        const { blob, filename } = await downloadJobAsBlob(data.job_uuid);
        setGenResults([{ url: URL.createObjectURL(blob), filename }]);
      }
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setGenLoading(false);
    }
  }, [genPrompt, genSize, genN]);

  // ── Tab 2 handlers ──
  const handleEditFileSelect = useCallback((file: File) => {
    const error = validateImageFile(file);
    if (error) { setEditError(error); return; }
    setEditError("");
    setEditFile(file);
    setEditResultUrl(null);
    setEditResultFilename(null);
  }, []);

  const handleEditSubmit = useCallback(async () => {
    if (!editFile || !editPrompt.trim()) return;
    setEditLoading(true);
    setEditSpinnerLabel("Wird bearbeitet…");
    setEditError("");
    setEditResultUrl(null);
    setEditResultFilename(null);
    try {
      const formData = new FormData();
      formData.append("image", editFile);
      formData.append("prompt", editPrompt);
      const response = await backendApi.fetch("/image/edit", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setEditSpinnerLabel("Läuft noch – Bildbearbeitung kann etwas länger dauern…"),
        60_000,
      );
      const { blob, filename } = await downloadJobAsBlob(data.job_uuid);
      const url = URL.createObjectURL(blob);
      setEditResultUrl(url);
      setEditResultFilename(filename);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setEditLoading(false);
    }
  }, [editFile, editPrompt]);

  const handleEditDownload = () => {
    if (!editResultUrl || !editResultFilename) return;
    const a = document.createElement("a");
    a.href = editResultUrl;
    a.download = editResultFilename;
    a.click();
  };

  // ── Tab 3 handlers ──
  const handleAnalyzeFileSelect = useCallback((file: File) => {
    const error = validateImageFile(file);
    if (error) { setAnalyzeError(error); return; }
    setAnalyzeError("");
    setAnalyzeFile(file);
    setAnalyzeResultText(null);
  }, []);

  const handleAnalyzeSubmit = useCallback(async () => {
    if (!analyzeFile) return;
    setAnalyzeLoading(true);
    setAnalyzeSpinnerLabel("Wird analysiert…");
    setAnalyzeError("");
    setAnalyzeResultText(null);
    try {
      const formData = new FormData();
      formData.append("image", analyzeFile);
      formData.append("prompt", analyzePrompt);
      const response = await backendApi.fetch("/image/analyze", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(data.job_uuid, undefined, 3000, undefined,
        () => setAnalyzeSpinnerLabel("Läuft noch – Bildanalyse kann etwas länger dauern…"),
        60_000,
      );
      const { blob } = await downloadJobAsBlob(data.job_uuid);
      const text = await blob.text();
      setAnalyzeResultText(text);
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setAnalyzeLoading(false);
    }
  }, [analyzeFile, analyzePrompt]);

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Image</h1>
        <p className="text-sm text-gray-500 mb-6">
          Bilder generieren, bearbeiten und analysieren mit KI.
        </p>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-200">
          {(
            [
              { id: "generate" as Tab, label: "Text zu Bild" },
              { id: "edit" as Tab, label: "Bild bearbeiten" },
              { id: "analyze" as Tab, label: "Bild analysieren" },
            ] as const
          ).map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === id
                  ? "border-[#004261] text-[#004261]"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* ── Tab 1: Text zu Bild ── */}
        {activeTab === "generate" && (
          <section>
            <textarea
              value={genPrompt}
              onChange={(e) => setGenPrompt(e.target.value)}
              rows={4}
              placeholder="Beschreiben Sie das gewünschte Bild ..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#004261] focus:ring-1 focus:ring-[#004261] focus:outline-none mb-4"
            />

            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-2">Größe</p>
              <div className="flex flex-wrap gap-2">
                {SIZES.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setGenSize(s)}
                    className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                      genSize === s
                        ? "border-[#004261] bg-[#004261]/10 text-[#004261]"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-6">
              <p className="text-sm font-medium text-gray-700 mb-2">Anzahl</p>
              <div className="flex gap-2">
                {COUNTS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setGenN(c)}
                    className={`w-10 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                      genN === c
                        ? "border-[#004261] bg-[#004261]/10 text-[#004261]"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={handleGenerate}
              disabled={!genPrompt.trim() || genLoading}
              className="w-full px-4 py-3 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {genLoading ? "Wird verarbeitet…" : "Bild generieren"}
            </button>

            {genLoading && <Spinner label={genSpinnerLabel} />}
            {genError && <p className="mt-4 text-sm text-red-600" role="alert">{genError}</p>}
            {genResults.length > 0 && (
              <div className="mt-6">
                <div className={`${genResults.length > 1 ? "grid grid-cols-2 gap-4" : ""}`}>
                  {genResults.map((result, i) => (
                    <div key={i}>
                      <img
                        src={result.url}
                        alt={`Generiertes Bild ${i + 1}`}
                        className="w-full rounded-lg border border-gray-200 bg-gray-50 mb-2"
                      />
                      <button
                        onClick={() => {
                          const a = document.createElement("a");
                          a.href = result.url;
                          a.download = result.filename;
                          a.click();
                        }}
                        className="w-full px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
                      >
                        <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        PNG
                      </button>
                    </div>
                  ))}
                </div>
                {genResults.length > 1 && genJobUuid && (
                  <a
                    href={`/api/jobs/${genJobUuid}/download`}
                    download
                    className="mt-4 w-full px-3 py-1.5 bg-[#004261] text-white text-xs font-medium rounded-md hover:bg-[#003a56] transition-colors flex items-center justify-center gap-2"
                  >
                    <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Alle als ZIP
                  </a>
                )}
              </div>
            )}
          </section>
        )}

        {/* ── Tab 2: Bild bearbeiten ── */}
        {activeTab === "edit" && (
          <section>
            <UploadZone
              file={editFile}
              dragOver={editDragOver}
              disabled={editLoading}
              inputRef={editFileRef}
              onDragOver={(e) => { e.preventDefault(); setEditDragOver(true); }}
              onDragLeave={(e) => { e.preventDefault(); setEditDragOver(false); }}
              onDrop={(e) => {
                e.preventDefault();
                setEditDragOver(false);
                const f = e.dataTransfer.files?.[0];
                if (f) handleEditFileSelect(f);
              }}
              onChange={handleEditFileSelect}
            />

            {editPreviewUrl && (
              <div className="mb-4 rounded-lg overflow-hidden border border-gray-200">
                <img src={editPreviewUrl} alt="Vorschau" className="w-full max-h-64 object-contain bg-gray-50" />
              </div>
            )}

            <textarea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              rows={3}
              placeholder="Beschreiben Sie die gewünschte Änderung."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#004261] focus:ring-1 focus:ring-[#004261] focus:outline-none mb-4"
            />

            <button
              onClick={handleEditSubmit}
              disabled={!editFile || !editPrompt.trim() || editLoading}
              className="w-full px-4 py-3 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {editLoading ? "Wird verarbeitet…" : "Bild bearbeiten"}
            </button>

            {editLoading && <Spinner label={editSpinnerLabel} />}
            {editError && <p className="mt-4 text-sm text-red-600" role="alert">{editError}</p>}
            {editResultUrl && (
              <div className="mt-6">
                <img
                  src={editResultUrl}
                  alt="Bearbeitetes Bild"
                  className="w-full rounded-lg border border-gray-200 bg-gray-50"
                />
                <button
                  onClick={handleEditDownload}
                  className="mt-3 px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-md hover:bg-green-700 transition-colors flex items-center gap-2"
                >
                  <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Bild
                </button>
              </div>
            )}
          </section>
        )}

        {/* ── Tab 3: Bild analysieren ── */}
        {activeTab === "analyze" && (
          <section>
            <UploadZone
              file={analyzeFile}
              dragOver={analyzeDragOver}
              disabled={analyzeLoading}
              inputRef={analyzeFileRef}
              onDragOver={(e) => { e.preventDefault(); setAnalyzeDragOver(true); }}
              onDragLeave={(e) => { e.preventDefault(); setAnalyzeDragOver(false); }}
              onDrop={(e) => {
                e.preventDefault();
                setAnalyzeDragOver(false);
                const f = e.dataTransfer.files?.[0];
                if (f) handleAnalyzeFileSelect(f);
              }}
              onChange={handleAnalyzeFileSelect}
            />

            {analyzePreviewUrl && (
              <div className="mb-4 rounded-lg overflow-hidden border border-gray-200">
                <img src={analyzePreviewUrl} alt="Vorschau" className="w-full max-h-64 object-contain bg-gray-50" />
              </div>
            )}

            <textarea
              value={analyzePrompt}
              onChange={(e) => setAnalyzePrompt(e.target.value)}
              rows={3}
              placeholder="Spezifische Frage stellen (optional) – sonst wird das Bild automatisch vollständig beschrieben."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#004261] focus:ring-1 focus:ring-[#004261] focus:outline-none mb-4"
            />

            <button
              onClick={handleAnalyzeSubmit}
              disabled={!analyzeFile || analyzeLoading}
              className="w-full px-4 py-3 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzeLoading ? "Wird verarbeitet…" : "Analysieren"}
            </button>

            {analyzeLoading && <Spinner label={analyzeSpinnerLabel} />}
            {analyzeError && <p className="mt-4 text-sm text-red-600" role="alert">{analyzeError}</p>}
            {analyzeResultText && (
              <div className="mt-6">
                <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 mb-3">
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{analyzeResultText}</p>
                </div>
                <button
                  onClick={() => {
                    const blob = new Blob([analyzeResultText], { type: "text/plain" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = analyzeFile
                      ? analyzeFile.name.replace(/\.[^.]+$/, "_analyse.txt")
                      : "analyse.txt";
                    a.click();
                    URL.revokeObjectURL(url);
                  }}
                  className="text-xs text-[#004261] hover:underline flex items-center gap-1"
                >
                  <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  TXT
                </button>
              </div>
            )}
          </section>
        )}
      </div>
    </ProtectedRoute>
  );
}
