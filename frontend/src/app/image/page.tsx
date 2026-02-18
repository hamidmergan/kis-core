"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { backendApi } from "@/lib/api";

type Tab = "generate" | "edit" | "analyze";

const SIZES = ["1024x1024", "1280x720", "720x1280"] as const;
const COUNTS = [1, 2, 3, 4] as const;
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
const ALLOWED_EXTS = new Set([".png", ".jpg", ".jpeg"]);

interface GeneratedImage {
  b64: string;
  index: number;
}

function validateImageFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTS.has(ext)) return "Nur PNG oder JPG erlaubt";
  if (file.size > MAX_IMAGE_BYTES) return "Bild zu groß (max 10 MB)";
  return null;
}

function downloadImage(b64: string, filename: string) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: "image/png" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex justify-center items-center gap-2 mt-6" role="status" aria-live="polite">
      <div className="inline-block animate-spin rounded-full h-5 w-5 border-b-2 border-[#0066cc]" />
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
          ? "border-[#0066cc] bg-[#0066cc]/5"
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
            <span className="text-[#0066cc] font-medium">durchsuchen</span>
          </p>
          <p className="text-xs text-gray-400 mt-1">PNG oder JPG, max. 10 MB</p>
        </>
      )}
    </div>
  );
}

export default function ImagePage() {
  const [activeTab, setActiveTab] = useState<Tab>("generate");
  const [lightboxSrc, setLightboxSrc] = useState<string | null>(null);

  // ── Tab 1: Text zu Bild ──
  const [genPrompt, setGenPrompt] = useState("");
  const [genSize, setGenSize] = useState("1024x1024");
  const [genN, setGenN] = useState(1);
  const [genLoading, setGenLoading] = useState(false);
  const [genImages, setGenImages] = useState<GeneratedImage[]>([]);
  const [genError, setGenError] = useState("");

  // ── Tab 2: Bild bearbeiten ──
  const [editFile, setEditFile] = useState<File | null>(null);
  const [editDragOver, setEditDragOver] = useState(false);
  const [editPrompt, setEditPrompt] = useState("");
  const [editLoading, setEditLoading] = useState(false);
  const [editResult, setEditResult] = useState("");
  const [editError, setEditError] = useState("");
  const [editPreviewUrl, setEditPreviewUrl] = useState<string | null>(null);
  const editFileRef = useRef<HTMLInputElement>(null);

  // ── Tab 3: Bild analysieren ──
  const [analyzeFile, setAnalyzeFile] = useState<File | null>(null);
  const [analyzeDragOver, setAnalyzeDragOver] = useState(false);
  const [analyzePrompt, setAnalyzePrompt] = useState("");
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState("");
  const [analyzeError, setAnalyzeError] = useState("");
  const [analyzePreviewUrl, setAnalyzePreviewUrl] = useState<string | null>(null);
  const [analyzeCopied, setAnalyzeCopied] = useState(false);
  const analyzeFileRef = useRef<HTMLInputElement>(null);

  // Manage object URLs for previews
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
    setGenError("");
    setGenImages([]);
    try {
      const formData = new FormData();
      formData.append("prompt", genPrompt);
      formData.append("size", genSize);
      formData.append("n", String(genN));
      const response = await backendApi.fetch("/image/generate", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(err.detail || `Fehler: ${response.status}`);
      }
      const data = await response.json();
      setGenImages(data.images);
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
    setEditResult("");
  }, []);

  const handleEditSubmit = useCallback(async () => {
    if (!editFile || !editPrompt.trim()) return;
    setEditLoading(true);
    setEditError("");
    setEditResult("");
    try {
      const formData = new FormData();
      formData.append("image", editFile);
      formData.append("prompt", editPrompt);
      const response = await backendApi.fetch("/image/edit", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(err.detail || `Fehler: ${response.status}`);
      }
      const data = await response.json();
      setEditResult(data.b64);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setEditLoading(false);
    }
  }, [editFile, editPrompt]);

  // ── Tab 3 handlers ──
  const handleAnalyzeFileSelect = useCallback((file: File) => {
    const error = validateImageFile(file);
    if (error) { setAnalyzeError(error); return; }
    setAnalyzeError("");
    setAnalyzeFile(file);
    setAnalyzeResult("");
  }, []);

  const handleAnalyzeSubmit = useCallback(async () => {
    if (!analyzeFile || !analyzePrompt.trim()) return;
    setAnalyzeLoading(true);
    setAnalyzeError("");
    setAnalyzeResult("");
    try {
      const formData = new FormData();
      formData.append("image", analyzeFile);
      formData.append("prompt", analyzePrompt);
      const response = await backendApi.fetch("/image/analyze", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(err.detail || `Fehler: ${response.status}`);
      }
      const data = await response.json();
      setAnalyzeResult(data.text);
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Unbekannter Fehler");
    } finally {
      setAnalyzeLoading(false);
    }
  }, [analyzeFile, analyzePrompt]);

  const handleCopyAnalyzeResult = async () => {
    await navigator.clipboard.writeText(analyzeResult);
    setAnalyzeCopied(true);
    setTimeout(() => setAnalyzeCopied(false), 2000);
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">Bild-KI</h1>
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
                  ? "border-[#0066cc] text-[#0066cc]"
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
              placeholder="Beschreiben Sie das gewünschte Bild auf Englisch..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none mb-4"
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
                        ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
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
                        ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
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
              className="w-full px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Bild generieren
            </button>

            {genLoading && <Spinner label="Bild wird generiert..." />}

            {genError && (
              <p className="mt-4 text-sm text-red-600" role="alert">{genError}</p>
            )}

            {genImages.length > 0 && (
              <div className={`mt-6 grid gap-4 ${genImages.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
                {genImages.map((img) => (
                  <div key={img.index}>
                    <button
                      onClick={() => setLightboxSrc(`data:image/png;base64,${img.b64}`)}
                      className="w-full block rounded-lg overflow-hidden border border-gray-200 hover:border-[#0066cc] transition-colors mb-2"
                      aria-label={`Bild ${img.index + 1} vergrößern`}
                    >
                      <img
                        src={`data:image/png;base64,${img.b64}`}
                        alt={`Generiertes Bild ${img.index + 1}`}
                        className="w-full"
                      />
                    </button>
                    <button
                      onClick={() => downloadImage(img.b64, `bild_${img.index + 1}.png`)}
                      className="w-full px-3 py-1.5 text-xs text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      Herunterladen
                    </button>
                  </div>
                ))}
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
                <img
                  src={editPreviewUrl}
                  alt="Vorschau"
                  className="w-full max-h-64 object-contain bg-gray-50"
                />
              </div>
            )}

            <textarea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              rows={3}
              placeholder="Beschreiben Sie die gewünschte Änderung auf Englisch, z.B. 'make style to Van Gogh'..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none mb-4"
            />

            <button
              onClick={handleEditSubmit}
              disabled={!editFile || !editPrompt.trim() || editLoading}
              className="w-full px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Bild bearbeiten
            </button>

            {editLoading && <Spinner label="Bild wird bearbeitet..." />}

            {editError && (
              <p className="mt-4 text-sm text-red-600" role="alert">{editError}</p>
            )}

            {editResult && (
              <div className="mt-6">
                <button
                  onClick={() => setLightboxSrc(`data:image/png;base64,${editResult}`)}
                  className="w-full block rounded-lg overflow-hidden border border-gray-200 hover:border-[#0066cc] transition-colors mb-2"
                  aria-label="Bearbeitetes Bild vergrößern"
                >
                  <img
                    src={`data:image/png;base64,${editResult}`}
                    alt="Bearbeitetes Bild"
                    className="w-full"
                  />
                </button>
                <button
                  onClick={() => downloadImage(editResult, "bild_bearbeitet.png")}
                  className="w-full px-3 py-1.5 text-xs text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                >
                  Herunterladen
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
                <img
                  src={analyzePreviewUrl}
                  alt="Vorschau"
                  className="w-full max-h-64 object-contain bg-gray-50"
                />
              </div>
            )}

            <textarea
              value={analyzePrompt}
              onChange={(e) => setAnalyzePrompt(e.target.value)}
              rows={3}
              placeholder="Was ist auf diesem Bild zu sehen? Oder stellen Sie eine spezifische Frage..."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none mb-4"
            />

            <button
              onClick={handleAnalyzeSubmit}
              disabled={!analyzeFile || !analyzePrompt.trim() || analyzeLoading}
              className="w-full px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Analysieren
            </button>

            {analyzeLoading && <Spinner label="Bild wird analysiert..." />}

            {analyzeError && (
              <p className="mt-4 text-sm text-red-600" role="alert">{analyzeError}</p>
            )}

            {analyzeResult && (
              <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200">
                  <span className="text-xs font-medium text-gray-500">Analyse</span>
                  <button
                    onClick={handleCopyAnalyzeResult}
                    className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
                  >
                    {analyzeCopied ? (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                        Kopiert
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                        Kopieren
                      </>
                    )}
                  </button>
                </div>
                <div className="px-4 py-3">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                    {analyzeResult}
                  </p>
                </div>
              </div>
            )}
          </section>
        )}

        {/* Lightbox */}
        {lightboxSrc && (
          <div
            className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
            onClick={() => setLightboxSrc(null)}
            role="dialog"
            aria-modal="true"
            aria-label="Bildvorschau"
          >
            <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={() => setLightboxSrc(null)}
                className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
                aria-label="Schließen"
              >
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <img src={lightboxSrc} alt="Vollansicht" className="w-full rounded-lg shadow-2xl" />
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
