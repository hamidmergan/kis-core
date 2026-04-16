"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { api, parseDetail } from "@/lib/api";
import { checkAuthStatus } from "@/lib/auth";
import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import type {
  ScreencastStep,
  SlideData,
} from "@/types";

interface Voice {
  voice_id: string;
  label: string;
  description?: string | null;
  use_case?: string | null;
}

const DESCRIPTION_DE: Record<string, string> = {
  "Laid-Back": "Entspannt",
  "Casual": "Locker",
  "Formal": "Förmlich",
  "Friendly": "Freundlich",
  "Warm": "Warm",
  "Authoritative": "Autoritär",
  "Confident": "Selbstsicher",
  "Calm": "Ruhig",
  "Energetic": "Energetisch",
  "Upbeat": "Lebhaft",
  "Serious": "Sachlich",
  "Raspy": "Rau",
  "Smooth": "Weich",
  "Deep": "Tief",
  "Resonant": "Resonant",
  "Crisp": "Klar",
  "Soft": "Sanft",
  "Husky": "Heiser",
  "Clear": "Deutlich",
  "Conversational": "Gesprächig",
  "Narrative": "Erzählend",
  "Expressive": "Ausdrucksstark",
  "Melodic": "Melodisch",
  "Mature": "Reif",
  "Powerful": "Kraftvoll",
  "Bright": "Hell",
  "Grounded": "Geerdet",
  "Soothing": "Beruhigend",
  "Professional": "Professionell",
};

function translateDesc(description?: string | null): string | null {
  if (!description) return null;
  return description.split(",").map(d => {
    const key = d.trim();
    return DESCRIPTION_DE[key] ?? key;
  }).join(" · ");
}

const KOKORO_ACCENT_LABEL: Record<string, string> = { "American": "🇺🇸", "British": "🇬🇧" };

interface TranslateResponse {
  slide_count: number;
  slide_texts: string[];
  slide_images: string[];
  translate_job_uuid?: string;
  user_prompt?: string;
}

interface GenerateScriptsResponse {
  scripts: string[];
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
    case "upload": return 0;
    case "translating": return 1;
    case "translation-review": return 2;
    case "user-prompt": return 3;
    case "generating-scripts":
    case "script-review": return 4;
    case "tts-settings": return 5;
    case "rendering": return 6;
    case "done": return 7;
    default: return 0;
  }
}

const RENDER_SESSION_KEY = "kis_screencast_demo_active_render";
const SCREENCAST_MAX_CHARS = 100_000;

function ScreencastDemoPageInner() {
  const [ttsSettingsError, setTtsSettingsError] = useState("");
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [step, setStep] = useState<ScreencastStep>("upload");
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  const [regeneratingSlide, setRegeneratingSlide] = useState<number | null>(null);
  const [regenPrompt, setRegenPrompt] = useState("");
  const [regenProposal, setRegenProposal] = useState<string | null>(null);
  const [regenLoading, setRegenLoading] = useState(false);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [translateJobUuid, setTranslateJobUuid] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [openAccordion, setOpenAccordion] = useState<number>(0);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editBuffer, setEditBuffer] = useState("");
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{ voice_id: string; name: string; accent: string; gender: string }>>([]);
  const [mylabVoices, setMylabVoices] = useState<Array<{ voice_id: string; name: string; description: string }>>([]);
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<"elevenlabs" | "fish_speech" | "kokoro" | "mylab">("kokoro");
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(false);
  const [fishSpeechEnabled, setFishSpeechEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [audioId, setAudioId] = useState<string>("");
  const [, setAudioCount] = useState(0);
  const [fastMode, setFastMode] = useState(false);
  const [showSteps, setShowSteps] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [maxReachedIdx, setMaxReachedIdx] = useState(0);
  const [scriptInputMode, setScriptInputMode] = useState<"generate" | "manual" | "import">("generate");
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const stepperRef = useRef<HTMLElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isDraggingRef = useRef(false);
  const hasDraggedRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragScrollLeftRef = useRef(0);

  useEffect(() => {
    checkAuthStatus().then((status) => { setIsAdmin(!!status.is_admin); });
  }, []);

  useEffect(() => {
    api.getJson<{ elevenlabs_enabled: boolean; fish_speech_enabled: boolean; kokoro_enabled: boolean; mylab_enabled: boolean }>("/api/tts/providers").then((data) => {
      setElevenlabsEnabled(data.elevenlabs_enabled);
      setFishSpeechEnabled(data.fish_speech_enabled);
      setKokoroEnabled(data.kokoro_enabled ?? false);
      setMylabEnabled(data.mylab_enabled ?? false);
      if (data.kokoro_enabled) setTtsProvider("kokoro");
      else if (data.mylab_enabled) setTtsProvider("mylab");
      else if (data.fish_speech_enabled) setTtsProvider("fish_speech");
      else if (data.elevenlabs_enabled) setTtsProvider("elevenlabs");
      if (data.elevenlabs_enabled) {
        api.getJson<{ voices: Voice[] }>("/api/voices").then((vData) => {
          setVoices(vData.voices);
          if (vData.voices.length > 0) setVoiceId(vData.voices[0].voice_id);
        }).catch(() => {});
      }
      if (data.kokoro_enabled) {
        api.getJson<{ voices: Array<{ voice_id: string; name: string; accent: string; gender: string }> }>("/api/kokoro/voices")
          .then((kData) => {
            setKokoroVoices(kData.voices ?? []);
            if (kData.voices?.length > 0) setVoiceId(kData.voices[0].voice_id);
          }).catch(() => {});
      }
      if (data.mylab_enabled) {
        api.getJson<{ voices: Array<{ voice_id: string; name: string; description: string }> }>("/api/mylab/voices")
          .then((mData) => {
            setMylabVoices(mData.voices ?? []);
            if (mData.voices?.length > 0 && !data.kokoro_enabled) setVoiceId(mData.voices[0].voice_id);
          }).catch(() => {});
      }
    }).catch(() => { setElevenlabsEnabled(true); }).finally(() => { setProvidersLoaded(true); });
  }, []);

  useEffect(() => { return () => { abortControllerRef.current?.abort(); }; }, []);

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
    if (Math.abs(x - dragStartXRef.current) > 5) hasDraggedRef.current = true;
    el.scrollLeft = dragScrollLeftRef.current - (x - dragStartXRef.current) * 1.5;
  }, []);

  const handleStepperMouseUp = useCallback(() => {
    isDraggingRef.current = false;
    const el = stepperRef.current;
    if (el) { el.style.cursor = ""; el.style.userSelect = ""; }
  }, []);

  const resetAll = useCallback(() => {
    abortControllerRef.current?.abort();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setStep("upload");
    setSpeed(0.9);
    setSlidePause(0.5);
    setSlides([]);
    setTranslateJobUuid("");
    setDownloadBlob(null);
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl(null);
    setErrorMessage("");
    setLoading(false);
    setOpenAccordion(0);
    setEditingSlide(null);
    setEditBuffer("");
    setLightboxIndex(null);
    setAudioId("");
    setAudioCount(0);
    setRenderProgressLabel("");
    setMaxReachedIdx(0);
    setScriptInputMode("generate");
    setImportedScripts(null);
    setImportError(null);
    setTtsProvider(kokoroEnabled ? "kokoro" : fishSpeechEnabled ? "fish_speech" : elevenlabsEnabled ? "elevenlabs" : "kokoro");
  }, [videoUrl, kokoroEnabled, fishSpeechEnabled, elevenlabsEnabled]);

  const handleStepClick = useCallback((index: number) => {
    if (hasDraggedRef.current) return;
    if (step === "rendering" || step === "generating-scripts") return;
    if (index > maxReachedIdx) return;
    const targets: Record<number, ScreencastStep | null> = {
      0: null, 1: null, 2: "translation-review", 3: "user-prompt",
      4: "script-review", 5: "tts-settings", 6: null, 7: "done",
    };
    const target = targets[index];
    if (!target) return;
    setStep(target);
  }, [maxReachedIdx, step]);

  const goError = useCallback((msg: string) => {
    setErrorMessage(msg);
    setStep("error");
    setLoading(false);
  }, []);

  const handleDemoStart = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      const res = await fetch("/api/screencast-demo/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fast_mode: fastMode }),
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Fehler beim Laden der Demo" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${res.status}`));
      }
      const data: TranslateResponse = await res.json();
      setTranslateJobUuid(data.translate_job_uuid ?? "demo");
      setSlides(
        (data.slide_texts || []).map((text, i) => ({
          index: i,
          imageBase64: (data.slide_images || [])[i] || "",
          extractedText: text,
          script: "",
        })),
      );
      setLoading(false);
      setStep("translation-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [fastMode, goError]);

  const handleAcceptTranslation = useCallback(async () => {
    setStep("generating-scripts");
    setLoading(true);
    try {
      const res = await fetch("/api/screencast-demo/generate-scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Fehler beim Laden der Skripte" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${res.status}`));
      }
      const data: GenerateScriptsResponse = await res.json();
      setSlides((prev) => prev.map((s, i) => ({ ...s, script: data.scripts[i] || "" })));
      setLoading(false);
      setStep("script-review");
    } catch (err) {
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [goError]);

  const handleAcceptScripts = useCallback(() => { setStep("tts-settings"); }, []);

  const processRenderResponse = useCallback(async (response: Response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Render-Fehler" }));
      throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
    }
    const blob = await response.blob();
    const aId = response.headers.get("X-Audio-Id");
    const aCount = response.headers.get("X-Audio-Count");
    if (aId) setAudioId(aId);
    if (aCount) setAudioCount(parseInt(aCount, 10) || 0);
    setDownloadBlob(blob);
    const url = URL.createObjectURL(blob);
    setVideoUrl(url);
    setLoading(false);
    setStep("done");
  }, []);

  const handleStartRender = useCallback(async () => {
    setTtsSettingsError("");
    setStep("rendering");
    setLoading(true);
    try {
      const voiceLabel = ttsProvider === "kokoro"
        ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
        : (voices.find(x => x.voice_id === voiceId)?.label ?? voiceId);
      const response = await fetch("/api/screencast-demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          translate_job_uuid: translateJobUuid || "demo",
          voice_id: voiceId, voice_label: voiceLabel,
          speed, slide_pause: slidePause, dpi, provider: ttsProvider,
        }),
        credentials: "include",
      });
      await processRenderResponse(response);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [voiceId, speed, slidePause, dpi, ttsProvider, kokoroVoices, voices, translateJobUuid, goError, processRenderResponse]);

  const handleDemoStartDirect = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      // Step 1: translate
      const res1 = await fetch("/api/screencast-demo/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fast_mode: fastMode }),
        credentials: "include",
      });
      if (!res1.ok) {
        const err = await res1.json().catch(() => ({ detail: "Fehler beim Laden der Demo" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${res1.status}`));
      }
      const data1: TranslateResponse = await res1.json();
      const loadedSlides = (data1.slide_texts || []).map((text, i) => ({
        index: i,
        imageBase64: (data1.slide_images || [])[i] || "",
        extractedText: text,
        script: "",
      }));
      setTranslateJobUuid(data1.translate_job_uuid ?? "demo");
      setSlides(loadedSlides);

      // Step 2: generate scripts
      const res2 = await fetch("/api/screencast-demo/generate-scripts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      });
      if (!res2.ok) {
        const err = await res2.json().catch(() => ({ detail: "Fehler beim Laden der Skripte" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${res2.status}`));
      }
      const data2: GenerateScriptsResponse = await res2.json();
      setSlides(loadedSlides.map((s, i) => ({ ...s, script: data2.scripts[i] || "" })));

      // Step 3: render
      const voiceLabel = ttsProvider === "kokoro"
        ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
        : (voices.find(x => x.voice_id === voiceId)?.label ?? voiceId);
      const res3 = await fetch("/api/screencast-demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          translate_job_uuid: data1.translate_job_uuid ?? "demo",
          voice_id: voiceId, voice_label: voiceLabel,
          speed, slide_pause: slidePause, dpi, provider: ttsProvider,
        }),
        credentials: "include",
      });
      await processRenderResponse(res3);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [fastMode, ttsProvider, kokoroVoices, voiceId, voices, speed, slidePause, dpi, goError, processRenderResponse]);

  const handleJsonImport = useCallback((file: File) => {
    setImportError(null);
    if (!file.name.toLowerCase().endsWith(".json")) {
      setImportError("Bitte eine gültige JSON-Datei auswählen (.json).");
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const parsed = JSON.parse(e.target?.result as string);
        if (!Array.isArray(parsed) || !parsed.every((x) => typeof x === "string")) {
          setImportError("Die JSON-Datei muss ein Array von Strings sein, z.B. [\"Skript 1\", \"Skript 2\"].");
          return;
        }
        setImportedScripts(parsed);
      } catch {
        setImportError("Ungültige JSON-Datei – Parsing fehlgeschlagen.");
      }
    };
    reader.readAsText(file);
  }, []);

  const handleDownload = () => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "screencast_demo.mp4";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const startEdit = (index: number) => {
    setOpenAccordion(index);
    setEditingSlide(index);
    setEditBuffer(slides[index].script);
  };

  const saveEdit = (index: number) => {
    setSlides((prev) => prev.map((s, i) => i === index ? { ...s, script: editBuffer } : s));
    setEditingSlide(null);
    setEditBuffer("");
  };

  const cancelEdit = () => { setEditingSlide(null); setEditBuffer(""); };

  const openRegen = (index: number) => { setRegeneratingSlide(index); setRegenPrompt(""); setRegenProposal(null); };
  const closeRegen = () => { setRegeneratingSlide(null); setRegenPrompt(""); setRegenProposal(null); };

  const runRegen = async (index: number) => {
    setRegenLoading(true);
    setRegenProposal(null);
    try {
      const result = await api.postJson<{ script: string }>("/api/screencast/regenerate-slide-script", {
        slide_text: slides[index].extractedText,
        current_script: slides[index].script || "",
        user_prompt: regenPrompt || null,
        target_lang: "EN-US",
      });
      setRegenProposal(result.script);
    } catch { setRegenProposal(""); } finally { setRegenLoading(false); }
  };

  const applyRegen = (index: number) => {
    if (regenProposal === null) return;
    setSlides((prev) => prev.map((s, i) => i === index ? { ...s, script: regenProposal } : s));
    closeRegen();
  };

  const handleBackToScripts = () => { if (step === "rendering") return; setStep("script-review"); };

  useEffect(() => {
    const idx = stepToIndex(step);
    setMaxReachedIdx((prev) => Math.max(prev, idx));
    const container = stepperRef.current;
    if (!container) return;
    const activeEl = container.querySelector<HTMLElement>('[data-active="true"]');
    if (!activeEl) return;
    const containerRect = container.getBoundingClientRect();
    const activeRect = activeEl.getBoundingClientRect();
    const offset = activeRect.left - containerRect.left - containerRect.width / 2 + activeRect.width / 2;
    container.scrollBy({ left: offset, behavior: "smooth" });
  }, [step]);

  const showStepIndicator = step !== "upload" && step !== "error";
  const totalWords = slides.reduce((sum, s) => sum + wordCount(s.script), 0);
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;

  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        {showStepIndicator && (
          <>
            <nav
              ref={stepperRef}
              aria-label="Fortschritt"
              className="mb-6 overflow-x-auto scrollbar-hide cursor-grab touch-pan-x"
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
                  const isClickable = isReached && !isActive && i !== 0 && i !== 1 && i !== 6 && step !== "rendering";
                  return (
                    <li key={label} data-active={isActive} className="flex items-center gap-1 sm:gap-2">
                      <button
                        type="button"
                        onClick={() => handleStepClick(i)}
                        aria-disabled={!isClickable}
                        className={`inline-flex items-center gap-1 sm:gap-1.5 rounded-sm px-1 py-0.5 transition-colors select-none ${isClickable ? "cursor-pointer hover:bg-gray-100" : "cursor-default"}`}
                      >
                        <span
                          className={`inline-flex items-center justify-center w-6 h-6 sm:w-7 sm:h-7 rounded-full text-[10px] sm:text-xs font-medium transition-colors flex-shrink-0
                            ${isActive ? "bg-primary text-white" : ""}
                            ${isDone ? "bg-primary/20 text-primary" : ""}
                            ${!isActive && !isDone ? "bg-gray-100 text-gray-400" : ""}
                          `}
                          aria-current={isActive ? "step" : undefined}
                        >
                          {isDone ? (
                            <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (i + 1)}
                        </span>
                        <span className={`text-[10px] sm:text-xs whitespace-nowrap ${isActive ? "text-gray-900 font-medium" : isClickable ? "text-gray-600" : "text-gray-400"}`}>
                          {label}
                        </span>
                      </button>
                      {i < STEP_LABELS.length - 1 && (
                        <span className={`w-3 sm:w-8 h-px flex-shrink-0 ${i < currentIdx ? "bg-primary" : "bg-gray-200"}`} aria-hidden="true" />
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
            <div className="flex justify-between mb-6">
              <button
                onClick={() => resetAll()}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
              <button
                onClick={() => resetAll()}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-red-400 hover:text-red-600 border border-red-200 hover:border-red-400 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                Screencast abbrechen
              </button>
            </div>
          </>
        )}

        {/* ── Step: Upload (Demo Start) ── */}
        {step === "upload" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold">
                Screencast erstellen
              </h1>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200">
                Demo
              </span>
            </div>
            <p className="text-sm text-gray-500 mb-6">
              Laden Sie eine PowerPoint-Präsentation hoch. Die Präsentation wird
              per DeepL übersetzt und als vertontes Video exportiert.
            </p>

            {/* Disabled file drop zone */}
            <div className="mb-4 flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 transition-colors border-gray-200 bg-gray-50 opacity-50 cursor-not-allowed">
              <svg className="w-8 h-8 text-gray-400 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="text-sm text-gray-500">Datei hierher ziehen oder <span className="text-gray-400 font-medium">durchsuchen</span></p>
              <p className="text-xs text-gray-400 mt-1">Nur .pptx-Datei</p>
            </div>

            <label className="flex items-start gap-3 mb-4 select-none cursor-pointer">
              <input
                type="checkbox"
                checked={showSteps}
                onChange={(e) => setShowSteps(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer"
              />
              <div>
                <span className="text-sm font-medium text-gray-700">Zwischenschritte anzeigen und bearbeiten</span>
                <p className="text-xs text-gray-400 mt-0.5">Empfohlen für beste Ergebnisse</p>
              </div>
            </label>

            {isAdmin && (
              <label className="flex items-center gap-2 cursor-pointer select-none mt-4 mb-6">
                <input
                  type="checkbox"
                  checked={fastMode}
                  onChange={(e) => setFastMode(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                />
                <div>
                  <span className="text-sm font-medium text-gray-700">Schnellmodus</span>
                  <p className="text-xs text-gray-400 mt-0.5">Folienvorschau wird übersprungen, schnellere Verarbeitung.</p>
                </div>
              </label>
            )}

            <div className="flex gap-3 mt-6">
              <button
                onClick={showSteps ? handleDemoStart : handleDemoStartDirect}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
              >
                Demo starten
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Translating ── */}
        {step === "translating" && (
          <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">Demo wird geladen...</p>
            <p className="text-xs text-gray-400 mt-2">Das kann je nach Dateigröße einige Sekunden dauern.</p>
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
            <h2 className="text-lg font-bold mb-1">Wie sollen die Skripte erstellt werden?</h2>
            <div className="mt-3 space-y-2">
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input type="radio" name="scriptInputMode" value="generate" checked={scriptInputMode === "generate"}
                  onChange={() => { setScriptInputMode("generate"); setImportedScripts(null); setImportError(null); }}
                  className="mt-0.5 accent-primary" />
                <div>
                  <span className="text-sm font-medium text-gray-900">KI-Generierung</span>
                  <p className="text-xs text-gray-500 mt-0.5">KI erstellt Skripte automatisch basierend auf den Folieninhalten.</p>
                </div>
              </label>
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input type="radio" name="scriptInputMode" value="manual" checked={scriptInputMode === "manual"}
                  onChange={() => { setScriptInputMode("manual"); setImportedScripts(null); setImportError(null); }}
                  className="mt-0.5 accent-primary" />
                <div>
                  <span className="text-sm font-medium text-gray-900">Manuell eingeben</span>
                  <p className="text-xs text-gray-500 mt-0.5">Alle Textfelder bleiben leer – Sie tippen die Skripte selbst ein.</p>
                </div>
              </label>
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input type="radio" name="scriptInputMode" value="import" checked={scriptInputMode === "import"}
                  onChange={() => setScriptInputMode("import")} className="mt-0.5 accent-primary" />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900">Skript importieren</span>
                  <p className="text-xs text-gray-500 mt-0.5">JSON-Datei hochladen – Array von Strings, ein Eintrag pro Folie.</p>
                  {scriptInputMode === "import" && (
                    <div className="mt-2">
                      <label className="inline-flex items-center gap-2 px-3 py-1.5 text-xs text-primary border border-primary rounded-md hover:bg-primary/5 cursor-pointer transition-colors">
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                        </svg>
                        JSON-Datei auswählen
                        <input type="file" accept=".json" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleJsonImport(f); }} />
                      </label>
                      {importedScripts && (
                        <p className="mt-1.5 text-xs text-green-600 flex items-center gap-1">
                          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          {importedScripts.length} Skript{importedScripts.length !== 1 ? "e" : ""} geladen
                        </p>
                      )}
                      {importError && (
                        <p className="mt-1.5 text-xs text-red-600 flex items-center gap-1">
                          <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          {importError}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </label>
            </div>
            {scriptInputMode === "generate" && <div className="mt-5 space-y-4" />}
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => {
                  if (scriptInputMode === "manual") {
                    setSlides((prev) => prev.map((s) => ({ ...s, script: "" })));
                    setStep("script-review");
                  } else if (scriptInputMode === "import") {
                    if (!importedScripts) { setImportError("Bitte zuerst eine JSON-Datei auswählen."); return; }
                    setSlides((prev) => prev.map((s, i) => ({ ...s, script: importedScripts[i] ?? "" })));
                    setStep("script-review");
                  } else {
                    handleAcceptTranslation();
                  }
                }}
                disabled={loading}
                className="flex-1 px-4 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Weiter
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Translation Review ── */}
        {step === "translation-review" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-1">Übersetzung prüfen</h2>
            <p className="text-sm text-gray-500 mb-4">
              Die Präsentation wurde übersetzt. Sie können die übersetzte
              PPTX herunterladen, prüfen und optional eine korrigierte
              Version hochladen.
            </p>

            {!fastMode && (
              <div className="flex flex-wrap justify-center gap-2 mb-6">
                {slides.map((slide, i) => (
                  <button key={i} onClick={() => setLightboxIndex(i)} style={{ width: "100px" }}
                    className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-primary transition-colors focus-visible:outline-2 focus-visible:outline-primary group flex-shrink-0"
                    aria-label={`Folie ${i + 1} vergrößern`}
                  >
                    {slide.imageBase64 ? (
                      <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full object-cover" />
                    ) : (
                      <div className="aspect-video bg-gray-100 flex items-center justify-center text-xs text-gray-400">Wird geladen...</div>
                    )}
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors flex items-center justify-center">
                      <span className="opacity-0 group-hover:opacity-100 bg-white/90 text-xs font-medium text-gray-700 px-2 py-1 rounded transition-opacity">Folie {i + 1}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {!fastMode && lightboxIndex !== null && (
              <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
                onClick={() => setLightboxIndex(null)} role="dialog" aria-modal="true" aria-label={`Folie ${lightboxIndex + 1}`}
              >
                <div className="relative max-w-4xl w-full" onClick={(e) => e.stopPropagation()}>
                  <button onClick={() => setLightboxIndex(null)} className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors" aria-label="Schließen">
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  <p className="text-white text-sm text-center mb-2">Folie {lightboxIndex + 1} von {slides.length}</p>
                  <img src={`data:image/png;base64,${slides[lightboxIndex].imageBase64}`} alt={`Folie ${lightboxIndex + 1}`} className="w-full rounded-lg shadow-2xl" />
                  <div className="flex justify-center gap-4 mt-4">
                    <button onClick={() => setLightboxIndex(Math.max(0, lightboxIndex - 1))} disabled={lightboxIndex === 0}
                      className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30">← Zurück</button>
                    <button onClick={() => setLightboxIndex(Math.min(slides.length - 1, lightboxIndex + 1))} disabled={lightboxIndex === slides.length - 1}
                      className="px-4 py-2 text-sm text-white border border-white/30 rounded-md hover:bg-white/10 transition-colors disabled:opacity-30">Weiter →</button>
                  </div>
                </div>
              </div>
            )}

            <div className="flex gap-3">
              <button
                onClick={() => { setMaxReachedIdx((v) => Math.max(v, 3)); setStep("user-prompt"); }}
                disabled={loading}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Übersetzung übernehmen und weiter
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Generating Scripts ── */}
        {step === "generating-scripts" && (
          <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">Sprechskripte werden generiert...</p>
            <p className="text-xs text-gray-400 mt-2">Die KI erstellt Skripte für {slides.length} Folien.</p>
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
            <h2 className="text-lg font-bold mb-1">Skripte überprüfen und anpassen</h2>
            <p className="text-sm text-gray-500 mb-4">
              Überprüfen Sie die generierten Skripte für jede Folie.
              Klicken Sie auf den Stift um zu bearbeiten.
            </p>

            <div className="space-y-2 mb-6">
              {slides.map((slide, i) => {
                const isOpen = openAccordion === i;
                const isEditing = editingSlide === i;
                const wc = wordCount(isEditing ? editBuffer : slide.script);
                const dur = estimateDuration(wc);
                const preview = slide.script.slice(0, 60) + (slide.script.length > 60 ? "..." : "");
                return (
                  <div key={i} className="border border-gray-200 rounded-lg overflow-hidden">
                    <button
                      onClick={() => { if (editingSlide !== null) cancelEdit(); setOpenAccordion(isOpen ? -1 : i); }}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                      aria-expanded={isOpen} aria-controls={`slide-panel-${i}`}
                    >
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-900">Folie {i + 1}</span>
                        {!isOpen && <span className="ml-2 text-xs text-gray-400 truncate">{preview}</span>}
                      </div>
                      <svg className={`w-4 h-4 text-gray-400 transition-transform ${isOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {isOpen && (
                      <div id={`slide-panel-${i}`} className="border-t border-gray-200 p-4 animate-[fadeIn_0.2s_ease-out]">
                        <div className="flex flex-col md:flex-row gap-4">
                          {!fastMode && (
                            <div className="flex-shrink-0" style={{ width: "100px" }}>
                              {slide.imageBase64 ? (
                                <img src={`data:image/png;base64,${slide.imageBase64}`} alt={`Folie ${i + 1}`} className="w-full rounded border border-gray-200" />
                              ) : (
                                <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center text-sm text-gray-400">Kein Bild</div>
                              )}
                            </div>
                          )}
                          <div className={`${fastMode ? "w-full" : "md:w-3/5"} flex flex-col`}>
                            {isEditing ? (
                              <>
                                <textarea value={editBuffer} onChange={(e) => setEditBuffer(e.target.value)} rows={8}
                                  className="w-full rounded-md border border-primary px-3 py-2 text-sm font-mono text-gray-900 focus:ring-1 focus:ring-primary focus:outline-none"
                                  aria-label={`Skript für Folie ${i + 1} bearbeiten`} />
                                <div className="flex items-center justify-between mt-2">
                                  <span className="text-xs text-gray-400">ca. {wc} Wörter · ~{dur} Sek</span>
                                  <div className="flex gap-2">
                                    <button onClick={cancelEdit} className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition-colors">Abbrechen</button>
                                    <button onClick={() => saveEdit(i)} className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition-colors">Speichern</button>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <>
                                <div className="flex items-start justify-between mb-2">
                                  <span className="text-xs text-gray-400">ca. {wc} Wörter · ~{dur} Sek</span>
                                  <div className="flex items-center gap-1">
                                    <button onClick={() => openRegen(i)} disabled
                                      className="w-7 h-7 flex items-center justify-center rounded-full text-gray-300 cursor-not-allowed"
                                      aria-label={`Skript für Folie ${i + 1} per KI neu generieren`}
                                      title="Nicht in der Demo verfügbar"
                                    >
                                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                                      </svg>
                                    </button>
                                    <button onClick={() => startEdit(i)} className="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-100 transition-colors" aria-label={`Skript für Folie ${i + 1} bearbeiten`}>
                                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                      </svg>
                                    </button>
                                  </div>
                                </div>
                                <p className="text-sm font-mono text-gray-700 whitespace-pre-wrap leading-relaxed">
                                  {slide.script || <span className="text-gray-400 italic">Kein Skript (leere Folie)</span>}
                                </p>
                                {regeneratingSlide === i && (
                                  <div className="mt-3 border border-purple-200 rounded-lg p-3 bg-purple-50 space-y-2">
                                    <p className="text-xs font-medium text-purple-700">KI-Anweisung für diese Folie (optional)</p>
                                    <textarea value={regenPrompt} onChange={(e) => setRegenPrompt(e.target.value)} rows={2}
                                      placeholder="z.B. Erkläre das Konzept vereinfacht für Einsteiger."
                                      className="w-full rounded-md border border-purple-200 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-purple-400 focus:ring-1 focus:ring-purple-400 focus:outline-none bg-white" />
                                    <div className="flex gap-2 justify-end">
                                      <button onClick={closeRegen} className="px-3 py-1 text-xs text-gray-600 border border-gray-300 rounded hover:bg-gray-50 transition-colors">Abbrechen</button>
                                      <button onClick={() => runRegen(i)} disabled={regenLoading}
                                        className="px-3 py-1 text-xs bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 transition-colors flex items-center gap-1.5">
                                        {regenLoading && <Spinner size="xs" color="current" />}
                                        {regenLoading ? "Generiere…" : "Generieren"}
                                      </button>
                                    </div>
                                    {regenProposal !== null && (
                                      <div>
                                        <p className="text-xs font-medium text-purple-700 mb-1">Vorschlag</p>
                                        <textarea value={regenProposal} onChange={(e) => setRegenProposal(e.target.value)} rows={4}
                                          className="w-full rounded-md border border-purple-300 px-3 py-2 text-sm font-mono text-gray-900 focus:border-purple-400 focus:ring-1 focus:ring-purple-400 focus:outline-none bg-white" />
                                        <div className="flex justify-end mt-2">
                                          <button onClick={() => applyRegen(i)} className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition-colors">Übernehmen</button>
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )}
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

            {slides.filter((s) => !s.script.trim()).length > 0 && (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-300 rounded-md px-3 py-2">
                {slides.filter((s) => !s.script.trim()).length} Folie(n) haben kein Skript. Bitte füllen Sie diese aus, bevor Sie fortfahren.
              </p>
            )}

            <div className="flex gap-3">
              <button onClick={handleAcceptScripts} disabled={editingSlide !== null}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                Alle Skripte übernehmen
              </button>
            </div>
          </section>
        )}

        {/* ── Step: TTS Settings ── */}
        {step === "tts-settings" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-6">Einstellungen</h2>

            {providersLoaded && (elevenlabsEnabled || fishSpeechEnabled || kokoroEnabled || mylabEnabled) && (
              <div className="mb-2">
                <label htmlFor="sc-provider-select" className="block text-sm font-medium text-gray-700 mb-2">TTS-Anbieter</label>
                <select id="sc-provider-select" value={ttsProvider}
                  onChange={(e) => {
                    const p = e.target.value as "elevenlabs" | "fish_speech" | "kokoro" | "mylab";
                    setTtsProvider(p);
                    if (p === "fish_speech") setVoiceId("default");
                    else if (p === "kokoro" && kokoroVoices.length > 0) setVoiceId(kokoroVoices[0].voice_id);
                    else if (p === "mylab" && mylabVoices.length > 0) setVoiceId(mylabVoices[0].voice_id);
                    else if (p === "elevenlabs" && voices.length > 0) setVoiceId(voices[0].voice_id);
                  }}
                  className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary"
                >
                  {kokoroEnabled && <option value="kokoro">Kokoro TTS</option>}
                  {mylabEnabled && <option value="mylab">THL myLab (XTTS-v2)</option>}
                  {fishSpeechEnabled && <option value="fish_speech">Fish Speech 1.5.1</option>}
                  {elevenlabsEnabled && <option value="elevenlabs">ElevenLabs</option>}
                </select>
              </div>
            )}

            {providersLoaded && (elevenlabsEnabled || fishSpeechEnabled || kokoroEnabled || mylabEnabled) && (
              <div className="mb-6 mt-4 space-y-3">
                <div>
                  <label htmlFor="sc-voice-select" className="block text-sm font-medium text-gray-700 mb-2">Stimme</label>
                  <select id="sc-voice-select" value={voiceId} onChange={(e) => setVoiceId(e.target.value)}
                    disabled={ttsProvider === "fish_speech"}
                    className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {ttsProvider === "fish_speech" ? (
                      <option value="default">Standard</option>
                    ) : ttsProvider === "kokoro" ? (
                      kokoroVoices.map((v) => {
                        const flag = v.accent === "American" ? "🇺🇸" : v.accent === "British" ? "🇬🇧" : "";
                        return <option key={v.voice_id} value={v.voice_id}>{flag} {v.name}</option>;
                      })
                    ) : ttsProvider === "mylab" ? (
                      mylabVoices.map((v) => (
                        <option key={v.voice_id} value={v.voice_id}>{v.name} – {v.description}</option>
                      ))
                    ) : (
                      voices.map((v) => {
                        const desc = translateDesc(v.description);
                        return <option key={v.voice_id} value={v.voice_id}>{desc ? `${v.label} – ${desc}` : v.label}</option>;
                      })
                    )}
                  </select>
                </div>
                {ttsProvider === "elevenlabs" && (
                  <a href="/tools/tts/voices" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">Stimmen anhören →</a>
                )}
                {ttsProvider === "kokoro" && (
                  <a href="/tools/tts/voices?tab=kokoro" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">Stimmen anhören →</a>
                )}
                {ttsProvider === "mylab" && (
                  <a href="/tools/tts/voices?tab=mylab" target="_blank" rel="noopener noreferrer" className="text-sm text-primary hover:underline">Stimmen anhören →</a>
                )}
              </div>
            )}

            <div className="mb-6">
              <label htmlFor="speed-slider" className="block text-sm font-medium text-gray-700 mb-2">Geschwindigkeit: {speed.toFixed(1)}x</label>
              <input id="speed-slider" type="range" min="0.7" max="1.2" step="0.1" value={speed}
                onChange={(e) => setSpeed(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary" />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>Langsam (0.7x)</span><span>Schnell (1.2x)</span>
              </div>
              <p className="text-xs text-gray-400 mt-2">Langsamere Geschwindigkeit empfohlen für Lehrvideos</p>
            </div>

            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">Pause zwischen Folien: {slidePause.toFixed(1)}s</label>
              <input type="range" min={0} max={3} step={0.1} value={slidePause}
                onChange={(e) => setSlidePause(parseFloat(e.target.value))}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary" />
              <div className="flex justify-between text-xs text-gray-400 mt-1"><span>0s</span><span>3s</span></div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Bildqualität</p>
              <div className="flex flex-col gap-2">
                {[{ val: 96, label: "Geringe Qualität", desc: "Schnellere Verarbeitung, geringere Bildschärfe" },
                  { val: 144, label: "Standard", desc: "Empfohlen, gute Bildqualität" },
                  { val: 300, label: "Maximale Qualität", desc: "Höchste Bildschärfe, ca. 4–5× längere Bearbeitungszeit" }
                ].map(({ val, label, desc }) => (
                  <label key={val} className="flex items-start gap-3 cursor-pointer">
                    <input type="radio" name="dpi" value={val} checked={dpi === val} onChange={() => setDpi(val)}
                      className="mt-0.5 h-4 w-4 text-primary focus:ring-primary" />
                    <div>
                      <span className="text-sm font-medium text-gray-700">{label}</span>
                      <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="mb-4 rounded-lg bg-gray-50 px-4 py-3">
              <p className="text-sm text-gray-700">
                <span className="font-medium">{slides.length}</span> Folien · ca.{" "}
                <span className="font-medium">{totalWords}</span> Wörter ·{" "}
                <span className={`font-medium ${scriptOverLimit ? "text-red-600" : ""}`}>{totalChars.toLocaleString("de-DE")}</span>{" "}
                / {SCREENCAST_MAX_CHARS.toLocaleString("de-DE")} Zeichen
              </p>
            </div>

            {scriptOverLimit && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
                <span className="text-red-500 mt-0.5">⚠</span>
                <div className="flex-1">
                  <p className="text-sm font-medium text-red-700">Skript zu lang</p>
                  <p className="text-sm text-red-600 mt-0.5">
                    Das Skript hat {totalChars.toLocaleString("de-DE")} Zeichen (max. {SCREENCAST_MAX_CHARS.toLocaleString("de-DE")}). Bitte kürzen Sie die Folien-Texte.
                  </p>
                  <button onClick={handleBackToScripts} className="mt-2 px-3 py-1.5 text-sm font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-100 transition-colors">
                    Zurück zum Skript bearbeiten
                  </button>
                </div>
              </div>
            )}

            {ttsSettingsError && (
              <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-3">{ttsSettingsError}</p>
            )}

            <div className="flex gap-3">
              <button onClick={handleBackToScripts} className="px-4 py-3 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">Zurück</button>
              <button onClick={handleStartRender} disabled={scriptOverLimit}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed">
                Screencast erstellen
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Rendering ── */}
        {step === "rendering" && (
          <section className="animate-[fadeIn_0.3s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700">{renderProgressLabel || "Video wird erstellt..."}</p>
            {!renderProgressLabel && <p className="text-xs text-gray-400 mt-2">Vertonung und Videoproduktion, das kann ein paar Minuten dauern.</p>}
            <button
              onClick={() => { abortControllerRef.current?.abort(); setRenderProgressLabel(""); setStep("tts-settings"); setLoading(false); }}
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
                <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            </div>
            <h2 className="text-lg font-bold mb-2 text-center">Fertig! Ihr Screencast ist bereit.</h2>

            {videoUrl && (
              <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
                <video key={videoUrl} controls className="w-full">
                  <source src={videoUrl} type="video/mp4" />
                  Ihr Browser unterstützt kein HTML5-Video.
                </video>
              </div>
            )}

            <div className="flex justify-center gap-3 mb-4">
              <button onClick={handleDownload} aria-label="MP4"
                className="px-6 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors flex items-center gap-2">
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                MP4
              </button>
              <button
                onClick={() => {
                  const endpoint = audioId ? `/api/jobs/${audioId}/bundle` : "/api/screencast-demo/bundle";
                  const a = document.createElement("a");
                  a.href = endpoint;
                  a.download = "";
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                }}
                aria-label="Alles herunterladen (ZIP)"
                className="px-6 py-2 bg-white text-primary border border-primary text-sm font-medium rounded-md hover:bg-primary/5 transition-colors flex items-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Alles herunterladen (ZIP)
              </button>
            </div>

            <div className="flex justify-center">
              <button onClick={() => resetAll()} aria-label="Neue Präsentation hochladen"
                className="px-6 py-2 text-sm text-red-600 border border-red-300 rounded-md hover:bg-red-50 transition-colors">
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
                <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            </div>
            <h2 className="text-lg font-bold text-red-700 mb-2">Fehler bei der Screencast-Erstellung</h2>
            {errorMessage && <p className="text-sm text-red-600 mb-3">{errorMessage}</p>}
            <div className="flex gap-3 justify-center">
              <button onClick={() => resetAll()} aria-label="Neue Präsentation hochladen"
                className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors">
                Neue Präsentation
              </button>
            </div>
          </section>
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastDemoPage() {
  return (
    <Suspense>
      <ScreencastDemoPageInner />
    </Suspense>
  );
}
