"use client";

import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import { pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import type { VideoDubbingState } from "@/types";

const ACCEPTED_EXTENSIONS = [".mp4", ".mp3"];

interface SubtitleResult {
  srt: string;
  vtt: string;
  txt: string;
  json: string;
}

interface DubbingResponse extends SubtitleResult {
  video_b64?: string;
  audio_b64?: string;
}

export default function VideoDubbingPage() {
  const [state, setState] = useState<VideoDubbingState>("idle");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [dropBackground, setDropBackground] = useState(false);
  const [softSubtitles, setSoftSubtitles] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [progressLabel, setProgressLabel] = useState("");

  // Result state
  const [videoBlob, setVideoBlob] = useState<Blob | null>(null);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [outputName, setOutputName] = useState("");
  const [subtitles, setSubtitles] = useState<SubtitleResult | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);

  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); setState("idle"); };
  }, []);

  const isProcessing = state === "uploading" || state === "processing";
  const isVideo = (f: File | null) => f?.name.toLowerCase().endsWith(".mp4") ?? false;
  const stem = file?.name.replace(/\.[^.]+$/, "") ?? "dubbed";

  // ── File handling ──────────────────────────────────────────────────────
  const handleFileSelect = useCallback((f: File) => {
    setFileError(null);
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setFileError("Nur .mp4 und .mp3 Dateien erlaubt");
      return;
    }
    setFile(f);
    if (ext === ".mp3") setSoftSubtitles(false);
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => { e.preventDefault(); setDragOver(true); }, []);
  const handleDragLeave = useCallback((e: DragEvent) => { e.preventDefault(); setDragOver(false); }, []);
  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFileSelect(f);
  }, [handleFileSelect]);

  // ── Submit ─────────────────────────────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    if (!file) return;

    // Check job limit + storage limit before submitting
    try {
      const res = await fetch("/api/jobs/check/video_dubbing", { credentials: "include" });
      const data = await res.json();
      if (data.has_active_job) {
        setErrorMessage("Sie haben bereits einen laufenden Dubbing-Job. Bitte warten Sie, bis er fertig ist.");
        return;
      }

    } catch { /* ignore, backend handles it */ }

    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    const signal = abortControllerRef.current.signal;

    setVideoBlob(null);
    setAudioBlob(null);
    setOutputName("");
    setSubtitles(null);
    setErrorMessage("");
    setProgressLabel("Wird hochgeladen…");
    setState("uploading");

    try {
      // Upload file → get job_uuid
      const formData = new FormData();
      formData.append("file", file);
      formData.append("source_lang", "de");
      formData.append("target_lang", "en");
      formData.append("drop_background_audio", String(dropBackground));
      formData.append("num_speakers", "0");
      formData.append("soft_subtitles", String(softSubtitles && isVideo(file)));

      const uploadRes = await fetch("/api/video-dubbing", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, `Fehler ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      setState("processing");
      setProgressLabel("In der Warteschlange…");

      // Poll until done
      const jobResult = await pollJob(
        job_uuid,
        (status) => {
          const step = (status.progress as { step?: string; dubbing_id?: string } | null)?.step;
          if (step === "submit") setProgressLabel("Wird bei ElevenLabs eingereicht…");
          else if (step === "dubbing") setProgressLabel("Dubbing läuft (kann 5-20 Min. dauern)…");
          else if (step === "download") setProgressLabel("Ergebnis wird heruntergeladen…");
          else setProgressLabel("In der Warteschlange…");
        },
        5000,
        signal,
      );

      // Get subtitle meta
      const meta = jobResult.meta as SubtitleResult | null;
      if (meta) {
        setSubtitles({ srt: meta.srt || "", vtt: meta.vtt || "", txt: meta.txt || "", json: meta.json || "" });
      }

      // Download media result
      setProgressLabel("Datei wird heruntergeladen…");
      const fileIsVideo = isVideo(file);
      const { blob, filename } = await downloadJobAsBlob(
        jobResult.job_uuid,
        fileIsVideo ? `${stem}_dubbed_en.mp4` : `${stem}_dubbed_en.mp3`,
      );

      if (fileIsVideo) {
        setVideoBlob(blob);
        setOutputName(filename || `${stem}_dubbed_en.mp4`);
      } else {
        setAudioBlob(blob);
        setOutputName(filename || `${stem}_dubbed_en.mp3`);
      }

      currentJobUuidRef.current = null;
      setState("done");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      currentJobUuidRef.current = null;
      setErrorMessage(err instanceof Error ? err.message : "Unbekannter Fehler");
      setState("error");
    }
  }, [file, dropBackground, softSubtitles, stem]);

  // ── Downloads ──────────────────────────────────────────────────────────
  const downloadBlob = (blob: Blob, name: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadText = (text: string, name: string, mime: string) => {
    downloadBlob(new Blob([text], { type: mime }), name);
  };

  const handleReset = () => {
    setState("idle");
    setFile(null);
    setVideoBlob(null);
    setAudioBlob(null);
    setOutputName("");
    setSubtitles(null);
    setErrorMessage("");
    setProgressLabel("");
    setFileError(null);
    setSoftSubtitles(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        <section>
          <h1 className="text-xl font-bold text-gray-900 mb-1">Video-Dubbing</h1>

          <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <strong>Derzeit nicht verfügbar.</strong> Video-Dubbing über ElevenLabs ist aufgrund zu hoher Kosten deaktiviert. Eine eigene Dubbing-Pipeline ist in Planung.
          </div>

          <p className="text-sm text-gray-500 mb-6">
            Laden Sie ein Video (.mp4) oder Audio (.mp3) hoch, um es automatisch
            von Deutsch nach Englisch zu synchronisieren.
          </p>

          {/* Fixed language display */}
          <div className="mb-4 grid grid-cols-2 gap-3">
            <div>
              <p className="text-sm font-medium text-gray-500 mb-1">Quellsprache</p>
              <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-400 select-none">
                Deutsch (DE)
              </div>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500 mb-1">Zielsprache</p>
              <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-400 select-none">
                Englisch (EN)
              </div>
            </div>
          </div>

          {/* Drag & Drop zone */}
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-1">Datei</p>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !isProcessing && fileRef.current?.click()}
              className={`
                relative flex flex-col items-center justify-center
                rounded-lg border-2 border-dashed px-6 py-8 cursor-pointer transition-colors
                ${dragOver ? "border-[#004261] bg-[#004261]/5" : ""}
                ${file && !dragOver ? "border-green-400 bg-green-50" : ""}
                ${!file && !dragOver ? "border-gray-300 hover:border-gray-400" : ""}
                ${isProcessing ? "opacity-50 pointer-events-none" : ""}
              `}
            >
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFileSelect(f);
                }}
              />
              {file ? (
                <>
                  <svg className="w-7 h-7 text-green-500 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-400 mt-1">Klicken oder eine andere Datei hierher ziehen</p>
                </>
              ) : (
                <>
                  <svg className="w-7 h-7 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="text-sm text-gray-600">
                    Eine Datei hierher ziehen oder{" "}
                    <span className="text-[#004261] font-medium">durchsuchen</span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">Nur eine .mp4- oder .mp3-Datei</p>
                </>
              )}
            </div>
            {fileError && <p className="mt-2 text-sm text-red-600" role="alert">{fileError}</p>}
          </div>

          {/* Options */}
          <div className="mb-6 space-y-3">
            <label className="flex items-start gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={dropBackground}
                onChange={(e) => setDropBackground(e.target.checked)}
                disabled={isProcessing}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#004261] focus:ring-[#004261] disabled:opacity-50"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">Hintergrundgeräusche entfernen</span>
                <p className="text-xs text-gray-400 mt-0.5">Entfernt Hintergrundmusik für eine klarere Synchronisation.</p>
              </div>
            </label>

            {/* Soft subtitles — only for MP4 */}
            {isVideo(file) && (
              <label className="flex items-start gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={softSubtitles}
                  onChange={(e) => setSoftSubtitles(e.target.checked)}
                  disabled={isProcessing}
                  className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#004261] focus:ring-[#004261] disabled:opacity-50"
                />
                <div>
                  <span className="text-sm font-medium text-gray-700">Soft Subtitles in MP4 einbetten</span>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Fügt einen ausschaltbaren Untertiteltrack ins MP4 ein.
                  </p>
                </div>
              </label>
            )}
          </div>

          {/* Submit */}
          <div className="flex items-center gap-3">
            <button
              onClick={handleSubmit}
              disabled={!file || isProcessing}
              className="flex-1 px-4 py-3 bg-[#004261] text-white text-sm font-medium rounded-md hover:bg-[#003a56] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#004261] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Dubbing starten
            </button>
            {isProcessing && (
              <button
                onClick={() => {
                  const uuid = currentJobUuidRef.current;
                  currentJobUuidRef.current = null;
                  abortControllerRef.current?.abort();
                  if (uuid) { fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {}); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }
                  setState("idle");
                }}
                className="px-4 py-3 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors flex items-center gap-2 shrink-0"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Abbrechen
              </button>
            )}
          </div>

          {/* ── Status & Results ── */}
          {state !== "idle" && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-white p-6" role="status" aria-live="polite">

              {/* Processing */}
              {isProcessing && (
                <div className="flex items-center gap-3">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[#004261] flex-shrink-0" />
                  <div>
                    <p className="text-sm text-gray-700">{progressLabel || "Dubbing läuft..."}</p>
                    {state === "processing" && (
                      <p className="text-xs text-gray-400 mt-1">Das kann 5-20 Minuten dauern.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Done */}
              {state === "done" && (
                <div className="space-y-5">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-green-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-sm font-medium text-gray-900">Fertig!</span>
                  </div>

                  {/* Audio result */}
                  {audioBlob && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Audio</p>
                      <button
                        onClick={() => downloadBlob(audioBlob, outputName || `${stem}_dubbed_en.mp3`)}
                        className="px-4 py-2 bg-[#004261] text-white text-sm rounded-md hover:bg-[#003a56] transition-colors flex items-center gap-2"
                      >
                        <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        MP3
                      </button>
                    </div>
                  )}

                  {/* Video result */}
                  {videoBlob && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Video</p>
                      <button
                        onClick={() => downloadBlob(videoBlob, outputName || `${stem}_dubbed_en.mp4`)}
                        className="px-4 py-2 bg-[#004261] text-white text-sm rounded-md hover:bg-[#003a56] transition-colors flex items-center gap-2"
                      >
                        <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                        </svg>
                        MP4
                      </button>
                    </div>
                  )}

                  {/* Subtitles */}
                  {subtitles && (subtitles.srt || subtitles.vtt || subtitles.txt || subtitles.json) && (
                    <div>
                      <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Untertitel</p>
                      <div className="flex flex-wrap gap-2">
                        {subtitles.srt && (
                          <button
                            onClick={() => downloadText(subtitles.srt, `${stem}_dubbed_en.srt`, "application/x-subrip")}
                            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                          >
                            SRT
                          </button>
                        )}
                        {subtitles.vtt && (
                          <button
                            onClick={() => downloadText(subtitles.vtt, `${stem}_dubbed_en.vtt`, "text/vtt")}
                            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                          >
                            VTT
                          </button>
                        )}
                        {subtitles.txt && (
                          <button
                            onClick={() => downloadText(subtitles.txt, `${stem}_dubbed_en.txt`, "text/plain")}
                            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                          >
                            TXT
                          </button>
                        )}
                        {subtitles.json && (
                          <button
                            onClick={() => downloadText(subtitles.json, `${stem}_dubbed_en.json`, "application/json")}
                            className="px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                          >
                            JSON
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                  >
                    Neue Datei
                  </button>
                </div>
              )}

              {/* Error */}
              {state === "error" && (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <svg className="h-5 w-5 text-red-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    <span className="text-sm font-medium text-red-700">Fehler beim Video-Dubbing</span>
                  </div>
                  {errorMessage && <p className="text-xs text-red-600">{errorMessage}</p>}
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
                  >
                    Erneut versuchen
                  </button>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </ProtectedRoute>
  );
}
