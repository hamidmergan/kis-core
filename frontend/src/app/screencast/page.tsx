"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScreencastStatus from "@/components/ScreencastStatus";
import { backendApi } from "@/lib/api";
import type {
  GlossaryEntry,
  ScreencastState,
  ScreencastStep,
  SlideData,
} from "@/types";

interface Voice {
  voice_id: string;
  label: string;
}

const ACCEPTED_EXTENSIONS = [".pptx"];

interface TranslateResponse {
  slide_count: number;
  slide_texts: string[];
  slide_images: string[];
  translated_pptx_b64: string;
  user_prompt?: string;
}

interface PrepareResponse {
  slide_images: string[];
}

interface ExtractTextsResponse {
  slide_count: number;
  slide_texts: string[];
}

interface GenerateScriptsResponse {
  scripts: string[];
}

interface SubtitleData {
  srt: string;
  vtt: string;

  txt: string;
  alignment_json: string;
}


function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

function estimateDuration(words: number): number {
  return Math.round((words / 150) * 60);
}

const STEP_LABELS = [
  "Upload",
  "Übersetzen",
  "Prüfen",
  "Anweisungen",
  "Skripte",
  "Einstellungen",
  "Rendern",
  "Fertig",
] as const;

function stepToIndex(step: ScreencastStep): number {
  switch (step) {
    case "upload":
      return 0;
    case "translating":
      return 1;
    case "translation-review":
      return 2;
    case "user-prompt":
      return 3;
    case "generating-scripts":
    case "script-review":
      return 4;
    case "tts-settings":
      return 5;
    case "rendering":
      return 6;
    case "done":
      return 7;
    default:
      return 0;
  }
}

export default function ScreencastPage() {
  // ── Auto mode state ──
  const [autoState, setAutoState] = useState<ScreencastState>("idle");
  const [autoDownloadBlob, setAutoDownloadBlob] = useState<Blob | null>(null);
  const [autoDownloadName, setAutoDownloadName] = useState("");
  const [autoError, setAutoError] = useState("");

  // ── Step-by-step state ──
  const [step, setStep] = useState<ScreencastStep>("upload");
  const [mode, setMode] = useState<"auto" | "manual">("manual");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [speed, setSpeed] = useState(0.9);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [userPrompt, setUserPrompt] = useState("");
  const [glossary, setGlossary] = useState<GlossaryEntry[]>([]);
  const [glossaryOpen, setGlossaryOpen] = useState(false);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [translatedPptxB64, setTranslatedPptxB64] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [openAccordion, setOpenAccordion] = useState<number>(0);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editBuffer, setEditBuffer] = useState("");
  const [correctedFileName, setCorrectedFileName] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [embedSubtitles, setEmbedSubtitles] = useState(true);
  const [imageDpi, setImageDpi] = useState(150);
  const [videoCrf, setVideoCrf] = useState(23);
  const [subtitleData, setSubtitleData] = useState<SubtitleData | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [demoAvailable, setDemoAvailable] = useState(false);
  const [demoHasVideo, setDemoHasVideo] = useState(false);

  const [maxReachedIdx, setMaxReachedIdx] = useState(0);

  const fileRef = useRef<HTMLInputElement>(null);
  const stepperRef = useRef<HTMLElement>(null);
  const isDraggingRef = useRef(false);
  const hasDraggedRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragScrollLeftRef = useRef(0);

  // ── Stepper drag-to-scroll ──

  const handleStepperMouseDown = useCallback((e: React.MouseEvent) => {
    const el = stepperRef.current;
    if (!el) return;
    isDraggingRef.current = true;
    hasDraggedRef.current = false;
    dragStartXRef.current = e.pageX - el.offsetLeft;
    dragScrollLeftRef.current = el.scrollLeft;
    el.style.cursor = "grabbing";
    el.style.userSelect = "none";
  }, []);

  const handleStepperMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    e.preventDefault();
    const el = stepperRef.current;
    if (!el) return;
    const x = e.pageX - el.offsetLeft;
    if (Math.abs(x - dragStartXRef.current) > 5) {
      hasDraggedRef.current = true;
    }
    const walk = (x - dragStartXRef.current) * 1.5;
    el.scrollLeft = dragScrollLeftRef.current - walk;
  }, []);

  const handleStepperMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    const el = stepperRef.current;
    if (el) {
      el.style.cursor = "";
      el.style.userSelect = "";
    }
  }, []);

  // ── Fetch available voices ──
  useEffect(() => {
    backendApi.getJson<{ voices: Voice[] }>("/voices").then((data) => {
      setVoices(data.voices);
      if (data.voices.length > 0) setVoiceId(data.voices[0].voice_id);
    }).catch(() => {});
  }, []);

  // ── Check demo availability ──
  useEffect(() => {
    backendApi.getJson<{ available: boolean; has_video: boolean }>("/screencast/demo-available").then((data) => {
      setDemoAvailable(data.available);
      setDemoHasVideo(data.has_video);
    }).catch(() => {});
  }, []);

  // ── Helpers ──

  const resetAll = useCallback(() => {
    setStep("upload");
    setFile(null);
    setFileError(null);
    setDragOver(false);
    setSpeed(0.9);
    setSlidePause(0.5);
    setUserPrompt("");
    setGlossary([]);
    setGlossaryOpen(false);
    setSlides([]);
    setTranslatedPptxB64("");
    setDownloadBlob(null);
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl(null);
    setErrorMessage("");
    setLoading(false);
    setOpenAccordion(0);
    setEditingSlide(null);
    setEditBuffer("");
    setCorrectedFileName(null);
    setLightboxIndex(null);
    setEmbedSubtitles(true);
    setImageDpi(150);
    setVideoCrf(23);
    setSubtitleData(null);
    setAudioId("");
    setAudioCount(0);
    setAutoState("idle");
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setMaxReachedIdx(0);
    if (fileRef.current) fileRef.current.value = "";
  }, [videoUrl]);

  const handleStepClick = useCallback((index: number) => {
    if (hasDraggedRef.current) return;
    if (index > maxReachedIdx) return;
    const targets: Record<number, ScreencastStep | null> = {
      0: null,
      1: null,
      2: "translation-review",
      3: "user-prompt",
      4: "script-review",
      5: "tts-settings",
      6: null,
      7: "done",
    };
    const target = targets[index];
    if (!target) return;
    setStep(target);
  }, [maxReachedIdx]);

  const goError = useCallback((msg: string) => {
    setErrorMessage(msg);
    setStep("error");
    setLoading(false);
  }, []);

  const handleFileSelect = useCallback((f: File) => {
    setFileError(null);
    const ext = "." + f.name.split(".").pop()?.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setFileError("Nur .pptx-Dateien erlaubt");
      return;
    }
    setFile(f);
  }, []);

  // ── Drag & Drop ──
  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files?.[0];
      if (f) handleFileSelect(f);
    },
    [handleFileSelect],
  );

  // ── Glossary helpers ──
  const addGlossaryRow = () => {
    setGlossary((prev) => [...prev, { source: "", target: "" }]);
  };

  const updateGlossaryRow = (
    idx: number,
    field: "source" | "target",
    value: string,
  ) => {
    setGlossary((prev) =>
      prev.map((entry, i) =>
        i === idx ? { ...entry, [field]: value } : entry,
      ),
    );
  };

  const removeGlossaryRow = (idx: number) => {
    setGlossary((prev) => prev.filter((_, i) => i !== idx));
  };

  const glossaryToJson = (): string => {
    const entries = glossary.filter(
      (e) => e.source.trim() && e.target.trim(),
    );
    if (entries.length === 0) return "";
    const obj: Record<string, string> = {};
    for (const e of entries) {
      obj[e.source.trim()] = e.target.trim();
    }
    return JSON.stringify(obj);
  };

  // ── Auto mode submit ──
  const handleAutoSubmit = useCallback(async () => {
    if (!file) return;
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setAutoState("processing");

    try {
      const fields: Record<string, string> = { speed: String(speed), voice_id: voiceId };
      const gj = glossaryToJson();
      if (gj) fields.glossary_json = gj;

      const { blob, filename } = await backendApi.uploadFileWithFields(
        "/screencast",
        file,
        fields,
        "file",
      );
      setAutoDownloadBlob(blob);
      setAutoDownloadName(filename);
      setAutoState("done");
    } catch (err) {
      setAutoError(err instanceof Error ? err.message : "Unbekannter Fehler");
      setAutoState("error");
    }
  }, [file, speed, voiceId, glossary]);

  const handleAutoDownload = () => {
    if (!autoDownloadBlob) return;
    const url = URL.createObjectURL(autoDownloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = autoDownloadName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── Step: Upload → Translating (or auto) ──
  const handleUploadNext = useCallback(async () => {
    if (!file) return;
    if (mode === "auto") {
      handleAutoSubmit();
      return;
    }
    // Start translation
    setStep("translating");
    setLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const gj = glossaryToJson();
      if (gj) formData.append("glossary_json", gj);

      const response = await backendApi.fetch("/screencast/translate", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(error.detail || `Fehler: ${response.status}`);
      }

      const data: TranslateResponse = await response.json();

      setTranslatedPptxB64(data.translated_pptx_b64);
      setSlides(
        data.slide_texts.map((text, i) => ({
          index: i,
          imageBase64: data.slide_images[i] || "",
          extractedText: text,
          script: "",
        })),
      );

      setLoading(false);
      setStep("translation-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [file, mode, handleAutoSubmit, goError, glossary]);

  // ── Download translated PPTX ──
  const handleDownloadTranslatedPptx = useCallback(() => {
    if (!translatedPptxB64) return;
    const bytes = Uint8Array.from(atob(translatedPptxB64), (c) =>
      c.charCodeAt(0),
    );
    const blob = new Blob([bytes], {
      type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
    a.download = `${stem}_EN.pptx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [translatedPptxB64, file]);

  // ── Upload corrected PPTX ──
  const handleUploadCorrectedPptx = useCallback(
    async (correctedFile: File) => {
      setLoading(true);

      try {
        const b64 = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => {
            const dataUrl = reader.result as string;
            resolve(dataUrl.split(",")[1]);
          };
          reader.onerror = () => reject(new Error("Datei konnte nicht gelesen werden"));
          reader.readAsDataURL(correctedFile);
        });

        setTranslatedPptxB64(b64);

        const [textsData, prepareData] = await Promise.all([
          backendApi.postJson<ExtractTextsResponse>(
            "/screencast/extract-texts",
            { pptx_b64: b64 },
          ),
          backendApi.postJson<PrepareResponse>(
            "/screencast/prepare",
            { translated_pptx_b64: b64 },
          ),
        ]);

        setSlides(
          textsData.slide_texts.map((text, i) => ({
            index: i,
            imageBase64: prepareData.slide_images[i] || "",
            extractedText: text,
            script: "",
          })),
        );

        setCorrectedFileName(correctedFile.name);
        setLoading(false);
      } catch (err) {
        goError(err instanceof Error ? err.message : "Unbekannter Fehler");
      }
    },
    [goError],
  );

  // ── Translation review → Generate scripts ──
  const handleAcceptTranslation = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);

    try {
      const scriptsData =
        await backendApi.postJson<GenerateScriptsResponse>(
          "/screencast/generate-scripts",
          {
            slide_texts: slides.map((s) => s.extractedText),
            user_prompt: userPrompt || null,
          },
        );

      setSlides((prev) =>
        prev.map((s, i) => ({
          ...s,
          script: scriptsData.scripts[i] || "",
        })),
      );

      setLoading(false);
      setStep("script-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, userPrompt, goError]);

  // ── Accept scripts → TTS settings ──
  const handleAcceptScripts = useCallback(() => {
    setStep("tts-settings");
  }, []);

  // ── Demo handlers ──
  const handleDemoTranslate = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      const data = await backendApi.postJson<TranslateResponse>(
        "/screencast/demo/translate",
        {},
      );
      setTranslatedPptxB64(data.translated_pptx_b64);
      setSlides(
        data.slide_texts.map((text, i) => ({
          index: i,
          imageBase64: data.slide_images[i] || "",
          extractedText: text,
          script: "",
        })),
      );
      if (data.user_prompt) setUserPrompt(data.user_prompt);
      setLoading(false);
      setStep("translation-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Demo-Fehler");
    }
  }, [goError]);

  const handleDemoGenerateScripts = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);
    try {
      const data = await backendApi.postJson<GenerateScriptsResponse>(
        "/screencast/demo/generate-scripts",
        {},
      );
      setSlides((prev) =>
        prev.map((s, i) => ({
          ...s,
          script: data.scripts[i] || "",
        })),
      );
      setLoading(false);
      setStep("script-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Demo-Fehler");
    }
  }, [goError]);

  // ── Shared: process render response (binary video + subtitles in header) ──
  const processRenderResponse = useCallback(async (response: Response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Render-Fehler" }));
      throw new Error(err.detail || `Fehler: ${response.status}`);
    }

    // Video comes as raw binary bytes
    const blob = await response.blob();
    console.log("[Screencast] Video blob size:", blob.size, "bytes");

    // Subtitles come as base64-encoded JSON in X-Subtitles header
    const subtitleHeader = response.headers.get("X-Subtitles");
    let subs: SubtitleData | null = null;
    if (subtitleHeader) {
      try {
        const decoded = atob(subtitleHeader);
        subs = JSON.parse(decoded);
      } catch {
        console.warn("[Screencast] Failed to parse X-Subtitles header");
      }
    }

    // Audio download info from headers
    const aId = response.headers.get("X-Audio-Id");
    const aCount = response.headers.get("X-Audio-Count");
    if (aId) setAudioId(aId);
    if (aCount) setAudioCount(parseInt(aCount, 10) || 0);

    setDownloadBlob(blob);
    const url = URL.createObjectURL(blob);
    setVideoUrl(url);
    if (subs) setSubtitleData(subs);
    setLoading(false);
    setStep("done");
  }, []);

  const handleDemoRender = useCallback(async () => {
    setStep("rendering");
    setLoading(true);
    try {
      const response = await backendApi.fetch("/screencast/demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      await processRenderResponse(response);
    } catch (err) {
      goError(err instanceof Error ? err.message : "Demo-Fehler");
    }
  }, [goError, processRenderResponse]);

  // ── Start rendering ──
  const handleStartRender = useCallback(async () => {
    setStep("rendering");
    setLoading(true);
    try {
      const response = await backendApi.fetch("/screencast/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scripts: slides.map((s) => s.script),
          translated_pptx_b64: translatedPptxB64,
          slide_images_b64: slides.map((s) => s.imageBase64),
          voice_id: voiceId,
          speed,
          slide_pause: slidePause,
          embed_subtitles: embedSubtitles,
          image_dpi: imageDpi,
          video_crf: videoCrf,
        }),
      });
      await processRenderResponse(response);
    } catch (err) {
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, translatedPptxB64, voiceId, speed, slidePause, embedSubtitles, imageDpi, videoCrf, goError, processRenderResponse]);

  // ── Download MP4 ──
  const handleDownload = () => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
    const a = document.createElement("a");
    a.href = url;
    const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
    a.download = `${stem}_screencast_EN.mp4`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ── Edit helpers ──
  const startEdit = (index: number) => {
    setEditingSlide(index);
    setEditBuffer(slides[index].script);
  };

  const saveEdit = (index: number) => {
    setSlides((prev) =>
      prev.map((s, i) =>
        i === index ? { ...s, script: editBuffer } : s,
      ),
    );
    setEditingSlide(null);
    setEditBuffer("");
  };

  const cancelEdit = () => {
    setEditingSlide(null);
    setEditBuffer("");
  };

  // ── Back to script review (from tts-settings) ──
  const handleBackToScripts = () => {
    setStep("script-review");
  };

  // ── VTT blob URL for in-browser subtitle track ──
  const vttUrl = useMemo(() => {
    if (!subtitleData?.vtt) return null;
    return URL.createObjectURL(new Blob([subtitleData.vtt], { type: "text/vtt" }));
  }, [subtitleData]);

  useEffect(() => {
    return () => {
      if (vttUrl) URL.revokeObjectURL(vttUrl);
    };
  }, [vttUrl]);

  // ── Track max reached step + auto-scroll active step to center ──
  useEffect(() => {
    const idx = stepToIndex(step);
    setMaxReachedIdx((prev) => Math.max(prev, idx));

    const container = stepperRef.current;
    if (!container) return;
    const activeEl = container.querySelector<HTMLElement>('[data-active="true"]');
    if (!activeEl) return;
    const containerRect = container.getBoundingClientRect();
    const activeRect = activeEl.getBoundingClientRect();
    const offset =
      activeRect.left -
      containerRect.left -
      containerRect.width / 2 +
      activeRect.width / 2;
    container.scrollBy({ left: offset, behavior: "smooth" });
  }, [step]);

  const isAutoMode =
    mode === "auto" && step === "upload" && autoState !== "idle";
  const showStepIndicator = step !== "upload" && step !== "error";

  const totalWords = slides.reduce(
    (sum, s) => sum + wordCount(s.script),
    0,
  );
  const totalDuration = estimateDuration(totalWords);

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Step indicator */}
        {showStepIndicator && (
          <>
            <nav
              ref={stepperRef}
              aria-label="Fortschritt"
              className="mb-2 overflow-x-auto scrollbar-hide cursor-grab touch-pan-x"
              onMouseDown={handleStepperMouseDown}
              onMouseMove={handleStepperMouseMove}
              onMouseUp={handleStepperMouseUp}
              onMouseLeave={handleStepperMouseUp}
            >
              <ol className="flex items-center gap-1 sm:gap-2 min-w-0 w-max sm:w-full">
                {STEP_LABELS.map((label, i) => {
                  const currentIdx = stepToIndex(step);
                  const isDone = i < currentIdx;
                  const isActive = i === currentIdx;
                  const isReached = i <= maxReachedIdx;
                  const isClickable = isReached && !isActive && i !== 0 && i !== 1 && i !== 6;
                  return (
                    <li key={label} data-active={isActive} className="flex items-center gap-1 sm:gap-2">
                      <button
                        type="button"
                        onClick={() => handleStepClick(i)}
                        aria-disabled={!isClickable}
                        className={`
                          inline-flex items-center gap-1 sm:gap-1.5 rounded-sm px-1 py-0.5 transition-colors select-none
                          ${isClickable ? "cursor-pointer hover:bg-gray-100" : "cursor-default"}
                        `}
                      >
                        <span
                          className={`
                            inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full text-[10px] sm:text-xs font-medium transition-colors flex-shrink-0
                            ${isActive ? "bg-[#0066cc] text-white" : ""}
                            ${isDone ? "bg-[#0066cc]/20 text-[#0066cc]" : ""}
                            ${!isActive && !isDone ? "bg-gray-100 text-gray-400" : ""}
                          `}
                          aria-current={isActive ? "step" : undefined}
                        >
                          {isDone ? (
                            <svg
                              className="w-3 h-3 sm:w-4 sm:h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              aria-hidden="true"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M5 13l4 4L19 7"
                              />
                            </svg>
                          ) : (
                            i + 1
                          )}
                        </span>
                        <span
                          className={`text-[10px] sm:text-xs whitespace-nowrap ${
                            isActive
                              ? "text-gray-900 font-medium"
                              : isClickable
                                ? "text-gray-600"
                                : "text-gray-400"
                          }`}
                        >
                          {label}
                        </span>
                      </button>
                      {i < STEP_LABELS.length - 1 && (
                        <span
                          className={`w-3 sm:w-8 h-px flex-shrink-0 ${
                            i < currentIdx ? "bg-[#0066cc]" : "bg-gray-200"
                          }`}
                          aria-hidden="true"
                        />
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
            <div className="flex justify-start mb-6">
              <button
                onClick={resetAll}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
            </div>
          </>
        )}

        {/* ── Step: Upload ── */}
        {step === "upload" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h1 className="text-xl font-bold text-gray-900 mb-1">
              Screencast erstellen
            </h1>
            <p className="text-sm text-gray-500 mb-6">
              Laden Sie eine deutsche PowerPoint-Präsentation hoch.
              Die Präsentation wird ins Englische übersetzt und als
              vertontes Video exportiert.
            </p>

            {/* Drag & Drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              className={`
                relative mb-4 flex flex-col items-center justify-center
                rounded-lg border-2 border-dashed px-6 py-10 cursor-pointer
                transition-colors
                ${
                  dragOver
                    ? "border-[#0066cc] bg-[#0066cc]/5"
                    : file
                      ? "border-green-400 bg-green-50"
                      : "border-gray-300 hover:border-gray-400"
                }
                ${autoState === "processing" ? "opacity-50 pointer-events-none" : ""}
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
                  <svg
                    className="w-8 h-8 text-green-500 mb-2"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  <p className="text-sm font-medium text-gray-900">
                    {file.name}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Klicken oder ziehen Sie eine andere Datei hierher
                  </p>
                </>
              ) : (
                <>
                  <svg
                    className="w-8 h-8 text-gray-400 mb-2"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    />
                  </svg>
                  <p className="text-sm text-gray-600">
                    Datei hierher ziehen oder{" "}
                    <span className="text-[#0066cc] font-medium">
                      durchsuchen
                    </span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Nur .pptx-Datei
                  </p>
                </>
              )}
            </div>
            {fileError && (
              <p className="mb-4 text-sm text-red-600" role="alert">
                {fileError}
              </p>
            )}

            {/* Glossary */}
            <div className="mb-6">
              <button
                type="button"
                onClick={() => setGlossaryOpen(!glossaryOpen)}
                className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors"
              >
                <svg
                  className={`w-4 h-4 text-gray-400 transition-transform ${glossaryOpen ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
                Glossar (optional)
              </button>

              {glossaryOpen && (
                <div className="mt-3 animate-[fadeIn_0.2s_ease-out]">
                  <p className="text-xs text-gray-400 mb-2">
                    Fachbegriffe, die bei der Übersetzung beibehalten oder
                    gezielt übersetzt werden sollen.
                  </p>
                  {glossary.length > 0 && (
                    <div className="space-y-2 mb-3">
                      <div className="grid grid-cols-[1fr_1fr_auto] gap-2 text-xs font-medium text-gray-500">
                        <span>Deutsch</span>
                        <span>Englisch</span>
                        <span className="w-8" />
                      </div>
                      {glossary.map((entry, idx) => (
                        <div
                          key={idx}
                          className="grid grid-cols-[1fr_1fr_auto] gap-2"
                        >
                          <input
                            type="text"
                            value={entry.source}
                            onChange={(e) =>
                              updateGlossaryRow(
                                idx,
                                "source",
                                e.target.value,
                              )
                            }
                            placeholder="Quellbegriff"
                            className="rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none"
                          />
                          <input
                            type="text"
                            value={entry.target}
                            onChange={(e) =>
                              updateGlossaryRow(
                                idx,
                                "target",
                                e.target.value,
                              )
                            }
                            placeholder="Zielbegriff"
                            className="rounded border border-gray-300 px-2 py-1.5 text-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none"
                          />
                          <button
                            onClick={() => removeGlossaryRow(idx)}
                            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-red-500 transition-colors"
                            aria-label="Eintrag entfernen"
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M6 18L18 6M6 6l12 12"
                              />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <button
                    onClick={addGlossaryRow}
                    className="text-sm text-[#0066cc] hover:text-[#0055aa] font-medium transition-colors"
                  >
                    + Eintrag hinzufügen
                  </button>
                </div>
              )}
            </div>

            {/* Mode toggle */}
            <label className="flex items-start gap-3 mb-6 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={mode === "manual"}
                onChange={(e) =>
                  setMode(e.target.checked ? "manual" : "auto")
                }
                disabled={autoState === "processing"}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc]"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">
                  Zwischenschritte anzeigen und bearbeiten
                </span>
                <p className="text-xs text-gray-400 mt-0.5">
                  Empfohlen für beste Ergebnisse
                </p>
              </div>
            </label>

            {/* Submit */}
            <div className="flex gap-3">
              <button
                onClick={handleUploadNext}
                disabled={!file || autoState === "processing"}
                className="flex-1 px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {mode === "auto" ? "Screencast erstellen" : "Weiter"}
              </button>
              {demoAvailable && (
                <button
                  onClick={handleDemoTranslate}
                  disabled={autoState === "processing"}
                  className="px-4 py-3 text-sm font-medium text-amber-700 border-2 border-amber-400 bg-amber-50 rounded-md hover:bg-amber-100 transition-colors disabled:opacity-50"
                >
                  Demo
                </button>
              )}
            </div>

            {/* Auto mode status */}
            {isAutoMode && (
              <ScreencastStatus
                state={autoState}
                fileName={autoDownloadName}
                errorMessage={autoError}
                onDownload={handleAutoDownload}
                onReset={resetAll}
              />
            )}
          </section>
        )}

        {/* ── Step: Translating (loading) ── */}
        {step === "translating" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066cc] mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">
              Präsentation wird übersetzt...
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Das kann je nach Dateigröße einige Sekunden dauern.
            </p>
          </section>
        )}

        {/* ── Step: User Prompt ── */}
        {step === "user-prompt" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold text-gray-900 mb-1">
              Anweisungen für die Skript-Erstellung (optional)
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Haben Sie spezielle Wünsche für die Skript-Erstellung?
            </p>

            <textarea
              value={userPrompt}
              onChange={(e) => setUserPrompt(e.target.value)}
              rows={4}
              placeholder="z.B. Beende das Skript der letzten Folie mit: Vielen Dank fürs Zuhören."
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none mb-4"
            />

            <div className="flex gap-3">
              <button
                onClick={handleAcceptTranslation}
                className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Überspringen
              </button>
              <button
                onClick={handleAcceptTranslation}
                className="flex-1 px-4 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
              >
                Weiter
              </button>
              {demoAvailable && (
                <button
                  onClick={handleDemoGenerateScripts}
                  className="px-4 py-2 text-sm font-medium text-amber-700 border-2 border-amber-400 bg-amber-50 rounded-md hover:bg-amber-100 transition-colors"
                >
                  Demo
                </button>
              )}
            </div>
          </section>
        )}

        {/* ── Step: Translation Review ── */}
        {step === "translation-review" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold text-gray-900 mb-1">
              Übersetzung prüfen
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Die Präsentation wurde übersetzt. Sie können die übersetzte
              PPTX herunterladen, prüfen und optional eine korrigierte
              Version hochladen.
            </p>

            {/* Thumbnail grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-6">
              {slides.map((slide, i) => (
                <button
                  key={i}
                  onClick={() => setLightboxIndex(i)}
                  className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-[#0066cc] transition-colors focus-visible:outline-2 focus-visible:outline-[#0066cc] group"
                  aria-label={`Folie ${i + 1} vergrößern`}
                >
                  {slide.imageBase64 ? (
                    <img
                      src={`data:image/png;base64,${slide.imageBase64}`}
                      alt={`Folie ${i + 1}`}
                      className="w-full object-cover"
                    />
                  ) : (
                    <div className="aspect-video bg-gray-100 flex items-center justify-center text-xs text-gray-400">
                      Wird geladen...
                    </div>
                  )}
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                    <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-xs font-medium text-gray-700 px-2 py-1 rounded transition-opacity">
                      Folie {i + 1}
                    </span>
                  </div>
                </button>
              ))}
            </div>

            {/* Lightbox modal */}
            {lightboxIndex !== null && (
              <div
                className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
                onClick={() => setLightboxIndex(null)}
                role="dialog"
                aria-modal="true"
                aria-label={`Folie ${lightboxIndex + 1}`}
              >
                <div
                  className="relative max-w-4xl w-full"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => setLightboxIndex(null)}
                    className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors"
                    aria-label="Schließen"
                  >
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  <p className="text-white text-sm text-center mb-2">
                    Folie {lightboxIndex + 1} von {slides.length}
                  </p>
                  <img
                    src={`data:image/png;base64,${slides[lightboxIndex].imageBase64}`}
                    alt={`Folie ${lightboxIndex + 1}`}
                    className="w-full rounded-lg shadow-2xl"
                  />
                  <div className="flex justify-center gap-4 mt-4">
                    <button
                      onClick={() => setLightboxIndex(Math.max(0, lightboxIndex - 1))}
                      disabled={lightboxIndex === 0}
                      className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
                    >
                      ← Zurück
                    </button>
                    <button
                      onClick={() => setLightboxIndex(Math.min(slides.length - 1, lightboxIndex + 1))}
                      disabled={lightboxIndex === slides.length - 1}
                      className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30"
                    >
                      Weiter →
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col gap-3 mb-4">
              <button
                onClick={handleDownloadTranslatedPptx}
                className="w-full px-4 py-2 text-sm text-[#0066cc] border border-[#0066cc] rounded-md hover:bg-[#0066cc]/5 transition-colors"
              >
                Übersetzte PPTX herunterladen
              </button>

              <div className="relative">
                <label className="block w-full px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors text-center cursor-pointer">
                  {loading
                    ? "Wird verarbeitet..."
                    : "Korrigierte PPTX hochladen (optional)"}
                  <input
                    type="file"
                    accept=".pptx"
                    className="hidden"
                    disabled={loading}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleUploadCorrectedPptx(f);
                    }}
                  />
                </label>
                {correctedFileName && (
                  <p className="mt-2 text-sm text-green-600 flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    {correctedFileName} wurde hochgeladen
                  </p>
                )}
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setStep("user-prompt")}
                disabled={loading}
                className="flex-1 px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Übersetzung übernehmen und weiter
              </button>
              {demoAvailable && (
                <button
                  onClick={handleDemoGenerateScripts}
                  disabled={loading}
                  className="px-4 py-3 text-sm font-medium text-amber-700 border-2 border-amber-400 bg-amber-50 rounded-md hover:bg-amber-100 transition-colors disabled:opacity-50"
                >
                  Demo
                </button>
              )}
            </div>
          </section>
        )}

        {/* ── Step: Generating Scripts (loading) ── */}
        {step === "generating-scripts" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066cc] mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">
              Sprechskripte werden generiert...
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Die KI erstellt Skripte für {slides.length} Folien.
            </p>
          </section>
        )}

        {/* ── Step: Script Review ── */}
        {step === "script-review" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold text-gray-900 mb-1">
              Skripte überprüfen und anpassen
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Überprüfen Sie die generierten Skripte für jede Folie.
              Klicken Sie auf den Stift um zu bearbeiten.
            </p>

            <div className="space-y-2 mb-6">
              {slides.map((slide, i) => {
                const isOpen = openAccordion === i;
                const isEditing = editingSlide === i;
                const wc = wordCount(
                  isEditing ? editBuffer : slide.script,
                );
                const dur = estimateDuration(wc);
                const preview =
                  slide.script.slice(0, 60) +
                  (slide.script.length > 60 ? "..." : "");

                return (
                  <div
                    key={i}
                    className="border border-gray-200 rounded-lg overflow-hidden"
                  >
                    {/* Accordion header */}
                    <button
                      onClick={() => {
                        if (isEditing) return;
                        setOpenAccordion(isOpen ? -1 : i);
                      }}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc]"
                      aria-expanded={isOpen}
                      aria-controls={`slide-panel-${i}`}
                    >
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-900">
                          Folie {i + 1}
                        </span>
                        {!isOpen && (
                          <span className="ml-2 text-xs text-gray-400 truncate">
                            {preview}
                          </span>
                        )}
                      </div>
                      <svg
                        className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        aria-hidden="true"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 9l-7 7-7-7"
                        />
                      </svg>
                    </button>

                    {/* Accordion body */}
                    {isOpen && (
                      <div
                        id={`slide-panel-${i}`}
                        className="border-t border-gray-200 p-4 animate-[fadeIn_0.2s_ease-out]"
                      >
                        <div className="flex flex-col md:flex-row gap-4">
                          {/* Slide image */}
                          <div className="md:w-2/5 flex-shrink-0">
                            {slide.imageBase64 ? (
                              <img
                                src={`data:image/png;base64,${slide.imageBase64}`}
                                alt={`Folie ${i + 1}`}
                                className="w-full rounded border border-gray-200"
                              />
                            ) : (
                              <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center text-sm text-gray-400">
                                Kein Bild
                              </div>
                            )}
                          </div>

                          {/* Script */}
                          <div className="md:w-3/5 flex flex-col">
                            {isEditing ? (
                              <>
                                <textarea
                                  value={editBuffer}
                                  onChange={(e) =>
                                    setEditBuffer(e.target.value)
                                  }
                                  rows={8}
                                  className="w-full rounded-md border border-[#0066cc] px-3 py-2 text-sm font-mono text-gray-900 focus:ring-1 focus:ring-[#0066cc] focus:outline-none"
                                  aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                                />
                                <div className="flex items-center justify-between mt-2">
                                  <span className="text-xs text-gray-400">
                                    ca. {wc} Wörter · ~{dur}{" "}
                                    Sek
                                  </span>
                                  <div className="flex gap-2">
                                    <button
                                      onClick={cancelEdit}
                                      className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                                    >
                                      Abbrechen
                                    </button>
                                    <button
                                      onClick={() =>
                                        saveEdit(i)
                                      }
                                      className="px-3 py-1 text-xs bg-[#0066cc] text-white rounded hover:bg-[#0055aa] transition-colors"
                                    >
                                      Speichern
                                    </button>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <>
                                <div className="flex items-start justify-between mb-2">
                                  <span className="text-xs text-gray-400">
                                    ca. {wc} Wörter · ~{dur}{" "}
                                    Sek
                                  </span>
                                  <button
                                    onClick={() =>
                                      startEdit(i)
                                    }
                                    className="p-1 text-gray-400 hover:text-[#0066cc] transition-colors"
                                    aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                                  >
                                    <svg
                                      className="w-4 h-4"
                                      fill="none"
                                      viewBox="0 0 24 24"
                                      stroke="currentColor"
                                      aria-hidden="true"
                                    >
                                      <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                                      />
                                    </svg>
                                  </button>
                                </div>
                                <p className="text-sm font-mono text-gray-700 whitespace-pre-wrap leading-relaxed">
                                  {slide.script || (
                                    <span className="text-gray-400 italic">
                                      Kein Skript (leere
                                      Folie)
                                    </span>
                                  )}
                                </p>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleAcceptScripts}
                disabled={editingSlide !== null}
                className="flex-1 px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Alle Skripte übernehmen
              </button>
              {demoAvailable && (
                <button
                  onClick={handleAcceptScripts}
                  disabled={editingSlide !== null}
                  className="px-4 py-3 text-sm font-medium text-amber-700 border-2 border-amber-400 bg-amber-50 rounded-md hover:bg-amber-100 transition-colors disabled:opacity-50"
                >
                  Demo
                </button>
              )}
            </div>
          </section>
        )}

        {/* ── Step: TTS Settings ── */}
        {step === "tts-settings" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold text-gray-900 mb-1">
              Spracheinstellungen
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Passen Sie Stimme, Geschwindigkeit und Pausen an.
            </p>

            {/* Stimme – Dropdown */}
            {voices.length > 1 && (
              <div className="mb-6">
                <label htmlFor="sc-voice-select" className="block text-sm font-medium text-gray-700 mb-2">
                  Stimme
                </label>
                <select
                  id="sc-voice-select"
                  value={voiceId}
                  onChange={(e) => setVoiceId(e.target.value)}
                  className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc]"
                >
                  {voices.map((v) => (
                    <option key={v.voice_id} value={v.voice_id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="mb-6">
              <label
                htmlFor="speed-slider"
                className="block text-sm font-medium text-gray-700 mb-2"
              >
                Geschwindigkeit: {speed.toFixed(1)}x
              </label>
              <input
                id="speed-slider"
                type="range"
                min="0.7"
                max="1.2"
                step="0.1"
                value={speed}
                onChange={(e) =>
                  setSpeed(parseFloat(e.target.value))
                }
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc]"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>Langsam (0.7x)</span>
                <span>Schnell (1.2x)</span>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Langsamere Geschwindigkeit empfohlen für
                Lehrvideos
              </p>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Pause zwischen Folien: {slidePause.toFixed(1)}s
              </label>
              <input
                type="range"
                min={0}
                max={3}
                step={0.1}
                value={slidePause}
                onChange={(e) =>
                  setSlidePause(parseFloat(e.target.value))
                }
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#0066cc]"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0s</span>
                <span>3s</span>
              </div>
            </div>

            {/* Subtitle checkbox */}
            <label className="flex items-start gap-3 mb-6 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={embedSubtitles}
                onChange={(e) => setEmbedSubtitles(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc]"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">
                  Untertitel in MP4 einbetten
                </span>
                <p className="text-xs text-gray-400 mt-0.5">
                  Soft-Subtitles als separate Spur (ein-/ausschaltbar im Player)
                </p>
              </div>
            </label>

            {/* Bildqualität */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bildqualität
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setImageDpi(150)}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
                    imageDpi === 150
                      ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
                      : "border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Standard (150 DPI)
                </button>
                <button
                  type="button"
                  onClick={() => setImageDpi(300)}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
                    imageDpi === 300
                      ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
                      : "border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Hoch (300 DPI)
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Höhere Auflösung der Folienbilder im Video
              </p>
            </div>

            {/* Videoqualität */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Videoqualität
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setVideoCrf(23)}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
                    videoCrf === 23
                      ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
                      : "border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Standard
                </button>
                <button
                  type="button"
                  onClick={() => setVideoCrf(18)}
                  className={`flex-1 px-4 py-2 text-sm font-medium rounded-md border transition-colors ${
                    videoCrf === 18
                      ? "border-[#0066cc] bg-[#0066cc]/10 text-[#0066cc]"
                      : "border-gray-300 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Hoch
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Höhere Qualität erzeugt größere Dateien
              </p>
            </div>

            {/* Summary */}
            <div className="mb-6 rounded-lg bg-gray-50 px-4 py-3">
              <p className="text-sm text-gray-700">
                <span className="font-medium">{slides.length}</span>{" "}
                Folien · ca.{" "}
                <span className="font-medium">{totalWords}</span>{" "}
                Wörter · geschätzte Dauer{" "}
                <span className="font-medium">~{totalDuration} Sek</span>
              </p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={handleBackToScripts}
                className="px-4 py-3 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Zurück
              </button>
              <button
                onClick={handleStartRender}
                className="flex-1 px-4 py-3 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
              >
                Screencast erstellen
              </button>
              {demoAvailable && (
                <button
                  onClick={handleDemoRender}
                  className="px-4 py-3 text-sm font-medium text-amber-700 border-2 border-amber-400 bg-amber-50 rounded-md hover:bg-amber-100 transition-colors"
                >
                  Demo
                </button>
              )}
            </div>
          </section>
        )}

        {/* ── Step: Rendering (loading) ── */}
        {step === "rendering" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-[#0066cc] mb-4" />
            <p className="text-sm text-gray-700">
              Video wird erstellt...
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Vertonung und Videoproduktion – das kann 1-3 Minuten
              dauern.
            </p>
          </section>
        )}

        {/* ── Step: Done ── */}
        {step === "done" && (
          <section className="animate-[fadeIn_0.3s_ease-out] py-8">
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-green-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-lg font-bold text-gray-900 mb-2 text-center">
              Fertig! Ihr Screencast ist bereit.
            </h2>
            <p className="text-xs text-gray-400 mb-6 text-center">
              {slides.length} Folien · ca. {totalDuration} Sek
              Gesamtdauer
            </p>

            {/* Video player */}
            {videoUrl && (
              <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
                <video
                  key={videoUrl}
                  controls
                  className="w-full"
                >
                  <source src={videoUrl} type="video/mp4" />
                  {vttUrl && (
                    <track
                      kind="subtitles"
                      src={vttUrl}
                      srcLang="en"
                      label="English"
                      default
                    />
                  )}
                  Ihr Browser unterstützt kein HTML5-Video.
                </video>
              </div>
            )}

            {/* Row 1: MP4 Download */}
            <div className="flex justify-center mb-4">
              <button
                onClick={handleDownload}
                aria-label="MP4 herunterladen"
                className="px-6 py-2 bg-[#0066cc] text-white text-sm font-medium rounded-md hover:bg-[#0055aa] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
              >
                MP4 herunterladen
              </button>
            </div>

            {/* Row 2: Transcript downloads */}
            {subtitleData && (
              <div className="mb-4">
                <p className="text-xs text-gray-400 text-center mb-2">Transkript herunterladen</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {([
                    ["SRT", subtitleData.srt, "transcript.srt", "text/plain"],
                    ["VTT", subtitleData.vtt, "transcript.vtt", "text/vtt"],
                    ["TXT", subtitleData.txt, "transcript.txt", "text/plain"],
                  ] as [string, string, string, string][]).map(([label, content, filename, mime]) => (
                    <button
                      key={label}
                      onClick={() => {
                        const blob = new Blob([content], { type: mime });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                      }}
                      className="px-3 py-1.5 text-xs text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Row 3: Audio downloads */}
            {audioId && audioCount > 0 && (
              <div className="mb-4">
                <p className="text-xs text-gray-400 text-center mb-2">Audio pro Folie herunterladen</p>
                <div className="flex flex-wrap justify-center gap-2">
                  {Array.from({ length: audioCount }, (_, i) => (
                    <button
                      key={i}
                      onClick={async () => {
                        try {
                          const res = await backendApi.fetch(`/screencast/audio/${audioId}/${i}`);
                          if (!res.ok) throw new Error("Download fehlgeschlagen");
                          const blob = await res.blob();
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `slide_${String(i + 1).padStart(2, "0")}.mp3`;
                          document.body.appendChild(a);
                          a.click();
                          document.body.removeChild(a);
                          URL.revokeObjectURL(url);
                        } catch {
                          console.error("Audio download failed for slide", i + 1);
                        }
                      }}
                      className="px-3 py-1.5 text-xs text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
                    >
                      Folie {i + 1}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Row 4: Reset */}
            <div className="flex justify-center">
              <button
                onClick={resetAll}
                aria-label="Neue Präsentation hochladen"
                className="px-6 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors"
              >
                Neue Präsentation
              </button>
            </div>
          </section>
        )}

        {/* ── Error state ── */}
        {step === "error" && (
          <section className="animate-[fadeIn_0.3s_ease-out] text-center py-12">
            <div className="flex justify-center mb-4">
              <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                <svg
                  className="w-6 h-6 text-red-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
            </div>
            <h2 className="text-lg font-bold text-red-700 mb-2">
              Fehler bei der Screencast-Erstellung
            </h2>
            {errorMessage && (
              <p className="text-sm text-red-600 mb-6">
                {errorMessage}
              </p>
            )}
            <button
              onClick={resetAll}
              aria-label="Erneut versuchen"
              className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0066cc] transition-colors"
            >
              Erneut versuchen
            </button>
          </section>
        )}
      </div>
    </ProtectedRoute>
  );
}
