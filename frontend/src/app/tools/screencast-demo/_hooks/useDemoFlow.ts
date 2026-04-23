"use client";

import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { parseDetail } from "@/lib/api";
import { KOKORO_ACCENT_LABEL } from "@/lib/voice-labels";
import { stepToIndex } from "@/components/screencast/steps";
import type { ScreencastStep, SlideData } from "@/types";
import type { DemoVoice, DemoTtsProvider } from "./useDemoProviders";

const RENDER_SESSION_KEY = "kis_screencast_demo_active_render";

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

interface Options {
  fastMode: boolean;
  ttsProvider: DemoTtsProvider;
  voiceId: string;
  kokoroVoices: Array<{ voice_id: string; name: string; accent: string; gender: string }>;
  voices: DemoVoice[];
  resetScriptEditing: () => void;
  setTtsProvider: (v: DemoTtsProvider) => void;
  kokoroEnabled: boolean;
  fishSpeechEnabled: boolean;
  elevenlabsEnabled: boolean;
  slides: SlideData[];
  setSlides: Dispatch<SetStateAction<SlideData[]>>;
}


export function useDemoFlow(opts: Options) {
  const { slides, setSlides } = opts;
  const [step, setStep] = useState<ScreencastStep>("upload");
  const [translateJobUuid, setTranslateJobUuid] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [audioId, setAudioId] = useState<string>("");
  const [, setAudioCount] = useState(0);
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [ttsSettingsError, setTtsSettingsError] = useState("");
  const [maxReachedIdx, setMaxReachedIdx] = useState(0);
  const [speed, setSpeed] = useState(1.0);
  const [slidePauseLocal, setSlidePauseLocal] = useState<number>(0.5);
  const [dpiLocal, setDpiLocal] = useState(144);
  const [scriptInputMode, setScriptInputMode] = useState<"generate" | "manual" | "import">("generate");
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => { return () => { abortControllerRef.current?.abort(); }; }, []);

  useEffect(() => {
    const idx = stepToIndex(step);
    setMaxReachedIdx((prev) => Math.max(prev, idx));
  }, [step]);

  const goError = useCallback((msg: string) => {
    setErrorMessage(msg);
    setStep("error");
    setLoading(false);
  }, []);

  const resetAll = useCallback(() => {
    abortControllerRef.current?.abort();
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setStep("upload");
    setSpeed(0.9);
    setSlidePauseLocal(0.5);
    setSlides([]);
    setTranslateJobUuid("");
    setDownloadBlob(null);
    if (videoUrl) URL.revokeObjectURL(videoUrl);
    setVideoUrl(null);
    setErrorMessage("");
    setLoading(false);
    opts.resetScriptEditing();
    setLightboxIndex(null);
    setAudioId("");
    setAudioCount(0);
    setRenderProgressLabel("");
    setMaxReachedIdx(0);
    setScriptInputMode("generate");
    setImportedScripts(null);
    setImportError(null);
    opts.setTtsProvider(
      opts.kokoroEnabled ? "kokoro" : opts.fishSpeechEnabled ? "fish_speech" : opts.elevenlabsEnabled ? "elevenlabs" : "kokoro",
    );
  }, [videoUrl, opts.kokoroEnabled, opts.fishSpeechEnabled, opts.elevenlabsEnabled]);

  const handleStepClick = useCallback((index: number) => {
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

  const handleDemoStart = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      const res = await fetch("/api/screencast-demo/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fast_mode: opts.fastMode }),
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
  }, [opts.fastMode, goError]);

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
    setVideoUrl(URL.createObjectURL(blob));
    setLoading(false);
    setStep("done");
  }, []);

  const computeVoiceLabel = useCallback(() => {
    if (opts.ttsProvider === "kokoro") {
      const v = opts.kokoroVoices.find((x) => x.voice_id === opts.voiceId);
      return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : opts.voiceId;
    }
    return opts.voices.find((x) => x.voice_id === opts.voiceId)?.label ?? opts.voiceId;
  }, [opts.ttsProvider, opts.kokoroVoices, opts.voiceId, opts.voices]);

  const handleStartRender = useCallback(async () => {
    setTtsSettingsError("");
    setStep("rendering");
    setLoading(true);
    try {
      const response = await fetch("/api/screencast-demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          translate_job_uuid: translateJobUuid || "demo",
          voice_id: opts.voiceId, voice_label: computeVoiceLabel(),
          speed, slide_pause: slidePauseLocal, dpi: dpiLocal, provider: opts.ttsProvider,
        }),
        credentials: "include",
      });
      await processRenderResponse(response);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [translateJobUuid, opts.voiceId, speed, slidePauseLocal, dpiLocal, opts.ttsProvider, computeVoiceLabel, goError, processRenderResponse]);

  const handleDemoStartDirect = useCallback(async () => {
    setStep("translating");
    setLoading(true);
    try {
      const res1 = await fetch("/api/screencast-demo/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fast_mode: opts.fastMode }),
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

      const res3 = await fetch("/api/screencast-demo/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          translate_job_uuid: data1.translate_job_uuid ?? "demo",
          voice_id: opts.voiceId, voice_label: computeVoiceLabel(),
          speed, slide_pause: slidePauseLocal, dpi: dpiLocal, provider: opts.ttsProvider,
        }),
        credentials: "include",
      });
      await processRenderResponse(res3);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [opts.fastMode, opts.voiceId, speed, slidePauseLocal, dpiLocal, opts.ttsProvider, computeVoiceLabel, goError, processRenderResponse]);

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

  const handleDownload = useCallback(() => {
    if (!downloadBlob) return;
    const url = URL.createObjectURL(downloadBlob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "screencast_demo.mp4";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [downloadBlob]);

  const handleBackToScripts = useCallback(() => {
    if (step === "rendering") return;
    setStep("script-review");
  }, [step]);

  const handleCancelTranslating = useCallback(() => {
    abortControllerRef.current?.abort();
    setStep("upload");
    setLoading(false);
  }, []);

  const handleCancelGeneratingScripts = useCallback(() => {
    abortControllerRef.current?.abort();
    setStep("translation-review");
    setLoading(false);
  }, []);

  const handleCancelRendering = useCallback(() => {
    abortControllerRef.current?.abort();
    setRenderProgressLabel("");
    setStep("tts-settings");
    setLoading(false);
  }, []);

  const handleAcceptTranslationAndAdvance = useCallback(() => {
    setMaxReachedIdx((v) => Math.max(v, 3));
    setStep("user-prompt");
  }, []);

  return {
    // state
    step, translateJobUuid, videoUrl, errorMessage, loading,
    lightboxIndex, setLightboxIndex, audioId, renderProgressLabel,
    ttsSettingsError, maxReachedIdx,
    speed, setSpeed, slidePause: slidePauseLocal, setSlidePause: setSlidePauseLocal,
    dpi: dpiLocal, setDpi: setDpiLocal,
    scriptInputMode, setScriptInputMode, importedScripts, setImportedScripts,
    importError, setImportError,
    // handlers
    resetAll, handleStepClick, goError,
    handleDemoStart, handleAcceptTranslation, handleAcceptScripts,
    handleStartRender, handleDemoStartDirect,
    handleJsonImport, handleDownload, handleBackToScripts,
    handleCancelTranslating, handleCancelGeneratingScripts, handleCancelRendering,
    handleAcceptTranslationAndAdvance,
  };
}
