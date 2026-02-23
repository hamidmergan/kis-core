"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScreencastStatus from "@/components/ScreencastStatus";
import GlossarySelector from "@/components/GlossarySelector";
import PromptChips from "@/components/PromptChips";
import { useGlossaries } from "@/hooks/useGlossaries";
import { backendApi } from "@/lib/api";
import type {
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
  file_id: string;
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
  const { mergeToApiJson } = useGlossaries();

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
  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [translatedPptxFileId, setTranslatedPptxFileId] = useState("");
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
  const [subtitleData, setSubtitleData] = useState<SubtitleData | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState("");
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [demoAvailable, setDemoAvailable] = useState(false);
  const [demoHasVideo, setDemoHasVideo] = useState(false);
  const [sourceLang, setSourceLang] = useState<"DE" | "EN">("DE");
  const [fastMode, setFastMode] = useState(true);

  const [maxReachedIdx, setMaxReachedIdx] = useState(0);

  const fileRef = useRef<HTMLInputElement>(null);
  const stepperRef = useRef<HTMLElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
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

  // ── Abort on unmount ──
  useEffect(() => {
    return () => { abortControllerRef.current?.abort(); };
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
    setGlossaryIds(["", "", ""]);
    setSlides([]);
    setTranslatedPptxFileId("");
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
    setSubtitleData(null);
    setAudioId("");
    setAudioCount(0);
    setAutoState("idle");
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setMaxReachedIdx(0);
    setSourceLang("DE");
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

  const newSignal = () => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = new AbortController();
    return abortControllerRef.current.signal;
  };

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

  // ── Auto mode submit ──
  const handleAutoSubmit = useCallback(async () => {
    if (!file) return;
    const signal = newSignal();
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setAutoState("processing");

    try {
      const glossaryJson = mergeToApiJson(glossaryIds);
      const fields: Record<string, string> = { speed: String(speed), voice_id: voiceId };
      if (glossaryJson) fields.glossary_json = glossaryJson;

      const { blob, filename } = await backendApi.uploadFileWithFields(
        "/screencast",
        file,
        fields,
        "file",
        signal,
      );
      setAutoDownloadBlob(blob);
      setAutoDownloadName(filename);
      setAutoState("done");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      setAutoError(err instanceof Error ? err.message : "Unbekannter Fehler");
      setAutoState("error");
    }
  }, [file, speed, voiceId, glossaryIds, mergeToApiJson]);

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

    setStep("translating");
    setLoading(true);
    const signal = newSignal();

    // ── EN path: skip DeepL, upload as-is, go directly to user-prompt ──
    if (sourceLang === "EN") {
      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await backendApi.fetch("/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          signal,
        });

        if (!response.ok) {
          const error = await response
            .json()
            .catch(() => ({ detail: "Unbekannter Fehler" }));
          throw new Error(error.detail || `Fehler: ${response.status}`);
        }

        const data: { file_id: string; slide_texts: string[]; slide_images: string[] } =
          await response.json();

        setTranslatedPptxFileId(data.file_id);
        setSlides(
          data.slide_texts.map((text, i) => ({
            index: i,
            imageBase64: data.slide_images[i] || "",
            extractedText: text,
            script: "",
          })),
        );

        setLoading(false);
        setStep("user-prompt");
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        goError(err instanceof Error ? err.message : "Unbekannter Fehler");
      }
      return;
    }

    // ── DE path: translate via DeepL, show translation review ──
    try {
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
      formData.append("fast_mode", String(fastMode));

      const response = await backendApi.fetch("/screencast/translate", {
        method: "POST",
        body: formData,
        signal,
      });

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(error.detail || `Fehler: ${response.status}`);
      }

      const data: TranslateResponse = await response.json();

      setTranslatedPptxFileId(data.file_id);
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
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [file, mode, sourceLang, fastMode, handleAutoSubmit, goError, glossaryIds, mergeToApiJson]);

  // ── Download translated PPTX ──
  const handleDownloadTranslatedPptx = useCallback(async () => {
    if (!translatedPptxFileId) return;
    try {
      const res = await backendApi.fetch(`/screencast/file/${translatedPptxFileId}`);
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
      a.download = `${stem}_EN.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PPTX download failed:", err);
    }
  }, [translatedPptxFileId, file]);

  // ── Upload corrected PPTX ──
  const handleUploadCorrectedPptx = useCallback(
    async (correctedFile: File) => {
      setLoading(true);
      const signal = newSignal();

      try {
        const formData = new FormData();
        formData.append("file", correctedFile);

        const response = await backendApi.fetch("/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          signal,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: "Fehler beim Hochladen" }));
          throw new Error(err.detail || `Fehler: ${response.status}`);
        }

        const data: { file_id: string; slide_texts: string[]; slide_images: string[] } =
          await response.json();

        setTranslatedPptxFileId(data.file_id);
        setSlides(
          data.slide_texts.map((text, i) => ({
            index: i,
            imageBase64: data.slide_images[i] || "",
            extractedText: text,
            script: "",
          })),
        );

        setCorrectedFileName(correctedFile.name);
        setLoading(false);
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return;
        goError(err instanceof Error ? err.message : "Unbekannter Fehler");
      }
    },
    [goError],
  );

  // ── Translation review → Generate scripts ──
  const handleAcceptTranslation = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);
    const signal = newSignal();

    try {
      const scriptsData =
        await backendApi.postJson<GenerateScriptsResponse>(
          "/screencast/generate-scripts",
          {
            slide_texts: slides.map((s) => s.extractedText),
            user_prompt: userPrompt || null,
            glossary_json: mergeToApiJson(glossaryIds),
          },
          signal,
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
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, userPrompt, glossaryIds, mergeToApiJson, goError]);

  // ── Accept scripts → TTS settings + fire-and-forget prerender ──
  const handleAcceptScripts = useCallback(() => {
    setStep("tts-settings");
    if (translatedPptxFileId) {
      backendApi.fetch("/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: translatedPptxFileId }),
      }).catch(() => {}); // fire and forget
    }
  }, [translatedPptxFileId]);

  // ── Demo handlers ──
  const handleDemoTranslate = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    const signal = newSignal();
    try {
      const data = await backendApi.postJson<TranslateResponse>(
        "/screencast/demo/translate",
        { fast_mode: fastMode },
        signal,
      );
      setTranslatedPptxFileId(data.file_id);
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
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Demo-Fehler");
    }
  }, [fastMode, goError]);

  const handleDemoGenerateScripts = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);
    const signal = newSignal();
    try {
      const data = await backendApi.postJson<GenerateScriptsResponse>(
        "/screencast/demo/generate-scripts",
        {},
        signal,
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
      if (err instanceof Error && err.name === "AbortError") return;
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
    const signal = newSignal();
    try {
      const response = await backendApi.fetch("/screencast/demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: translatedPptxFileId }),
        signal,
      });
      await processRenderResponse(response);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Demo-Fehler");
    }
  }, [translatedPptxFileId, goError, processRenderResponse]);

  // ── Start rendering ──
  const handleStartRender = useCallback(async () => {
    setStep("rendering");
    setLoading(true);
    const signal = newSignal();
    try {
      const response = await backendApi.fetch("/screencast/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scripts: slides.map((s) => s.script),
          file_id: translatedPptxFileId,
          voice_id: voiceId,
          speed,
          slide_pause: slidePause,
          embed_subtitles: embedSubtitles,
        }),
        signal,
      });
      await processRenderResponse(response);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, translatedPptxFileId, voiceId, speed, slidePause, embedSubtitles, goError, processRenderResponse]);

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
    setOpenAccordion(index);
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
                  const isSkipped = sourceLang === "EN" && (i === 1 || i === 2);
                  const isDone = !isSkipped && i < currentIdx;
                  const isActive = i === currentIdx;
                  const isReached = i <= maxReachedIdx;
                  const isClickable = !isSkipped && isReached && !isActive && i !== 0 && i !== 1 && i !== 6;
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
                            ${isSkipped ? "bg-gray-100 text-gray-300" : ""}
                            ${!isActive && !isDone && !isSkipped ? "bg-gray-100 text-gray-400" : ""}
                          `}
                          aria-current={isActive ? "step" : undefined}
                        >
                          {isSkipped ? (
                            <svg className="w-3 h-3 sm:w-3.5 sm:h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 12h12" />
                            </svg>
                          ) : isDone ? (
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
                            isSkipped
                              ? "text-gray-300 line-through"
                              : isActive
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
                            i < currentIdx && !isSkipped ? "bg-[#0066cc]" : "bg-gray-200"
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
            {/* English PPTX checkbox */}
            <label className="flex items-start gap-3 mb-4 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={sourceLang === "EN"}
                onChange={(e) => setSourceLang(e.target.checked ? "EN" : "DE")}
                disabled={autoState === "processing"}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc]"
              />
              <span className="text-sm font-medium text-gray-700">
                Präsentation ist bereits auf Englisch (Übersetzung überspringen)
              </span>
            </label>

            {fileError && (
              <p className="mb-4 text-sm text-red-600" role="alert">
                {fileError}
              </p>
            )}

            {/* Glossary — hidden for EN presentations (no translation needed) */}
            {sourceLang === "DE" && (
              <GlossarySelector
                values={glossaryIds}
                onChange={setGlossaryIds}
              />
            )}

            {/* Mode toggle */}
            <label className="flex items-start gap-3 mb-4 cursor-pointer select-none">
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

            {/* Fast mode — only relevant in manual mode */}
            {mode === "manual" && (
              <label className="flex items-center gap-2 cursor-pointer select-none mt-4 mb-6">
                <input
                  type="checkbox"
                  checked={fastMode}
                  onChange={(e) => setFastMode(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-[#0066cc] focus:ring-[#0066cc]"
                />
                <div>
                  <span className="text-sm font-medium text-gray-700">Schnellmodus</span>
                  <p className="text-xs text-gray-400 mt-0.5">Folienvorschau wird übersprungen – schnellere Verarbeitung.</p>
                </div>
              </label>
            )}

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
              {sourceLang === "EN"
                ? "Präsentation wird vorbereitet..."
                : "Präsentation wird übersetzt..."}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Das kann je nach Dateigröße einige Sekunden dauern.
            </p>
            <button
              onClick={() => { abortControllerRef.current?.abort(); setStep("upload"); setLoading(false); }}
              className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Abbrechen
            </button>
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
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-[#0066cc] focus:ring-1 focus:ring-[#0066cc] focus:outline-none"
            />
            <PromptChips
              onChipClick={(chip) =>
                setUserPrompt((prev) =>
                  prev.trim() ? `${prev.trimEnd()}\n- ${chip}` : `- ${chip}`,
                )
              }
            />

            <div className="flex gap-3 mt-4">
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

            {/* Thumbnail grid — hidden in fast mode */}
            {!fastMode && (
              <div className="flex flex-wrap gap-2 mb-6">
                {slides.map((slide, i) => (
                  <button
                    key={i}
                    onClick={() => setLightboxIndex(i)}
                    style={{ width: "100px" }}
                    className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-[#0066cc] transition-colors focus-visible:outline-2 focus-visible:outline-[#0066cc] group flex-shrink-0"
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
            )}

            {/* Lightbox modal — only when thumbnails are visible */}
            {!fastMode && lightboxIndex !== null && (
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
            <button
              onClick={() => { abortControllerRef.current?.abort(); setStep("translation-review"); setLoading(false); }}
              className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Abbrechen
            </button>
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
                        if (editingSlide !== null) {
                          cancelEdit();
                        }
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
                          {/* Slide image — hidden in fast mode */}
                          {!fastMode && (
                            <div className="flex-shrink-0" style={{ width: "100px" }}>
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
                          )}

                          {/* Script */}
                          <div className={`${fastMode ? "w-full" : "md:w-3/5"} flex flex-col`}>
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
            <button
              onClick={() => { abortControllerRef.current?.abort(); setStep("tts-settings"); setLoading(false); }}
              className="mt-6 px-4 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors inline-flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Abbrechen
            </button>
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
