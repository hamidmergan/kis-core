"use client";

import { Suspense, useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/Header";
import ProtectedRoute from "@/components/ProtectedRoute";
import ScreencastStatus from "@/components/ScreencastStatus";
import GlossarySelector from "@/components/GlossarySelector";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail, type JobStatus } from "@/lib/api";
import { checkAuthStatus } from "@/lib/auth";
import BackLink from "@/components/BackLink";
import Spinner from "@/components/Spinner";
import type {
  ScreencastState,
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

const ACCEPTED_EXTENSIONS = [".pptx"];

const KOKORO_ACCENT_LABEL: Record<string, string> = { "American": "🇺🇸", "British": "🇬🇧" };

interface TranslateResponse {
  slide_count: number;
  slide_texts: string[];
  slide_images: string[];
  translate_job_uuid?: string;
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


const MAX_REGEN_TEXTAREA_HEIGHT = 480; // ~20 lines at text-sm leading-relaxed

function RegenTextarea({ value, onChange, className }: { value: string; onChange: (v: string) => void; className: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, MAX_REGEN_TEXTAREA_HEIGHT) + "px";
  }, [value]);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={1}
      className={className}
    />
  );
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

const RENDER_SESSION_KEY = "kis_screencast_active_render";
const SCREENCAST_MAX_CHARS = 100_000;

function ScreencastPageInner() {
  const { mergeToApiJson } = useGlossaries();

  // ── Auto mode state ──
  const [autoState, setAutoState] = useState<ScreencastState>("idle");
  const [autoDownloadBlob, setAutoDownloadBlob] = useState<Blob | null>(null);
  const [autoDownloadName, setAutoDownloadName] = useState("");
  const [autoError, setAutoError] = useState("");
  const [renderProgressLabel, setRenderProgressLabel] = useState("");
  const [failedRenderJobUuid, setFailedRenderJobUuid] = useState<string | null>(null);
  const [failedRenderIsAuto, setFailedRenderIsAuto] = useState(false);
  const [ttsSettingsError, setTtsSettingsError] = useState("");

  // ── Step-by-step state ──
  const [step, setStep] = useState<ScreencastStep>("upload");
  const [mode, setMode] = useState<"auto" | "manual">("manual");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  // Per-slide AI regeneration state
  const [regeneratingSlide, setRegeneratingSlide] = useState<number | null>(null);
  const [regenPrompt, setRegenPrompt] = useState("");
  const [regenMessages, setRegenMessages] = useState<{ role: "user" | "assistant"; content: string }[]>([]);
  const [regenLoading, setRegenLoading] = useState(false);
  const [regenAnchorText, setRegenAnchorText] = useState("");
  const [regenAnchorSlide, setRegenAnchorSlide] = useState<number | null>(null);
  const regeneratingSlideRef = useRef<number | null>(null);
  const regenChatBottomRef = useRef<HTMLDivElement>(null);
  const regenChatAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = () => {
      if (regeneratingSlideRef.current !== null) return;
      if (!window.getSelection()?.toString().trim()) {
        setRegenAnchorText("");
        setRegenAnchorSlide(null);
      }
    };
    document.addEventListener("selectionchange", handler);
    return () => document.removeEventListener("selectionchange", handler);
  }, []);

  useEffect(() => {
    regenChatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [regenMessages, regenLoading]);


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [translateJobUuid, setTranslateJobUuid] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [openAccordion, setOpenAccordion] = useState<number>(0);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editBuffer, setEditBuffer] = useState("");
  const [correctedFileName, setCorrectedFileName] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const [voices, setVoices] = useState<Voice[]>([]);
  const [kokoroVoices, setKokoroVoices] = useState<Array<{ voice_id: string; name: string; accent: string; gender: string }>>([]);
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<"elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten">("kokoro");
  const [elevenlabsEnabled, setElevenlabsEnabled] = useState(false);
  const [fishSpeechEnabled, setFishSpeechEnabled] = useState(false);
  const [kokoroEnabled, setKokoroEnabled] = useState(false);
  const [mylabEnabled, setMylabEnabled] = useState(false);
  const [thorstenEnabled, setThorstenEnabled] = useState(false);
  const [mylabVoices, setMylabVoices] = useState<Array<{ voice_id: string; name: string; description: string }>>([]);
  const [thorstenVoices, setThorstenVoices] = useState<Array<{ voice_id: string; name: string; language: string }>>([]);
  const [providersLoaded, setProvidersLoaded] = useState(false);
  const [audioId, setAudioId] = useState<string>("");
  const [audioCount, setAudioCount] = useState(0);
  const [languages, setLanguages] = useState<{ id: string; label: string }[]>([]);
  const [sourceLang, setSourceLang] = useState<string>("DE");
  const [targetLang, setTargetLang] = useState<string>("EN-US");
  const [fastMode, setFastMode] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isAdminLoaded, setIsAdminLoaded] = useState(false);
  const [showDemoLink, setShowDemoLink] = useState(false);

  const [maxReachedIdx, setMaxReachedIdx] = useState(0);
  const [hasActiveJob, setHasActiveJob] = useState<boolean | null>(null);
  const [isResumedJob, setIsResumedJob] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);

  useEffect(() => {
    checkAuthStatus().then((status) => {
      setIsAdmin(!!status.is_admin);
      setIsAdminLoaded(true);
    });
    fetch("/api/admin/tools", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => {
        const tool = (d.tools ?? []).find((t: { key: string; enabled: boolean }) => t.key === "screencast-demo");
        setShowDemoLink(!tool || tool.enabled);
      })
      .catch(() => {});
  }, []);

  // ── Script input mode (user-prompt step) ──
  const [scriptInputMode, setScriptInputMode] = useState<"generate" | "manual" | "import">("generate");
  const [importedScripts, setImportedScripts] = useState<string[] | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [jsonDragOver, setJsonDragOver] = useState(false);
  const jsonFileRef = useRef<HTMLInputElement>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const stepperRef = useRef<HTMLElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);
  const isDraggingRef = useRef(false);
  const hasDraggedRef = useRef(false);
  const dragStartXRef = useRef(0);
  const dragScrollLeftRef = useRef(0);
  const scriptAutosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isGeneratingScriptsRef = useRef(false);

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

  // ── Fetch language config ──
  useEffect(() => {
    // Provide a sensible default so dropdowns are always visible
    setLanguages([
      { id: "DE", label: "Deutsch" },
      { id: "EN-US", label: "Englisch" },
      { id: "EN-GB", label: "Englisch (UK)" },
      { id: "FR", label: "Französisch" },
      { id: "ES", label: "Spanisch" },
      { id: "IT", label: "Italienisch" },
    ]);
    api
      .getJson<{ languages: { id: string; label: string }[]; default_source: string; default_target: string }>(
        "/api/translate/config",
      )
      .then((data) => {
        if (data.languages?.length) setLanguages(data.languages);
        if (data.default_source) setSourceLang(data.default_source);
        if (data.default_target) setTargetLang(data.default_target);
      })
      .catch(() => {});
  }, []);

  // ── Fetch available voices + providers ──
  useEffect(() => {
    api.getJson<{ elevenlabs_enabled: boolean; fish_speech_enabled: boolean; kokoro_enabled: boolean; mylab_enabled: boolean; thorsten_enabled: boolean }>("/api/tts/providers").then((data) => {
      setElevenlabsEnabled(data.elevenlabs_enabled);
      setFishSpeechEnabled(data.fish_speech_enabled);
      setKokoroEnabled(data.kokoro_enabled ?? false);
      setMylabEnabled(data.mylab_enabled ?? false);
      setThorstenEnabled(data.thorsten_enabled ?? false);
      // Default priority: kokoro > mylab > thorsten > fish_speech > elevenlabs
      if (data.kokoro_enabled) setTtsProvider("kokoro");
      else if (data.mylab_enabled) setTtsProvider("mylab");
      else if (data.thorsten_enabled) setTtsProvider("thorsten");
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
            if (kData.voices?.length > 0) {
              setVoiceId(kData.voices[0].voice_id);
            }
          }).catch(() => {});
      }
      if (data.mylab_enabled) {
        api.getJson<{ voices: Array<{ voice_id: string; name: string; description: string }> }>("/api/mylab/voices")
          .then((mData) => {
            setMylabVoices(mData.voices ?? []);
            if (mData.voices?.length > 0 && !data.kokoro_enabled) {
              setVoiceId(mData.voices[0].voice_id);
            }
          }).catch(() => {});
      }
      if (data.thorsten_enabled) {
        api.getJson<{ voices: Array<{ voice_id: string; name: string; language: string }> }>("/api/thorsten/voices")
          .then((tData) => {
            setThorstenVoices(tData.voices ?? []);
            if (tData.voices?.length > 0 && !data.kokoro_enabled && !data.mylab_enabled) {
              setVoiceId(tData.voices[0].voice_id);
            }
          }).catch(() => {});
      }
    }).catch(() => {
      setElevenlabsEnabled(true);
    }).finally(() => {
      setProvidersLoaded(true);
    });
  }, []);

  const searchParams = useSearchParams();

  // ── Resume awaiting_user job from ?resume=<uuid> URL param ──
  useEffect(() => {
    const resumeUuid = searchParams.get("resume");
    if (!resumeUuid) return;
    setResumeLoading(true);
    fetch(`/api/screencast/resume/${resumeUuid}`, { credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("Job nicht gefunden oder nicht im Eingabe-Status");
        return r.json();
      })
      .then((data: { tool: string; step: string; slide_texts: string[]; scripts: string[]; slide_images: string[]; original_filename: string; user_prompt: string }) => {
        setTranslateJobUuid(resumeUuid);
        setIsResumedJob(true);

        const imgs = data.slide_images ?? [];
        const texts = data.slide_texts ?? [];
        const scripts = data.scripts ?? [];

        const slideCount = Math.max(texts.length, scripts.length, imgs.length);
        if (slideCount > 0) {
          setSlides(Array.from({ length: slideCount }, (_, i) => ({
            index: i,
            imageBase64: imgs[i] ?? "",
            extractedText: texts[i] ?? scripts[i] ?? "",
            script: scripts[i] ?? texts[i] ?? "",
          })));
        }

        const targetStep = (
          data.step === "tts-settings" ? "tts-settings" :
          data.step === "translation-review" ? "translation-review" :
          data.step === "user-prompt" ? "user-prompt" :
          "script-review"
        ) as import("@/types").ScreencastStep;

        const stepIdx = targetStep === "tts-settings" ? 5 : targetStep === "translation-review" ? 2 : targetStep === "user-prompt" ? 3 : 4;
        setMaxReachedIdx(stepIdx);
        setStep(targetStep);
      })
      .catch(() => {
        // Resume failed (job expired/cancelled) — stay on upload
      })
      .finally(() => setResumeLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Lazy-load slide images if missing after resume ──
  useEffect(() => {
    if (!translateJobUuid || !slides.length) return;
    if (slides.some((s) => s.imageBase64)) return; // already have images
    fetch(`/api/screencast/${translateJobUuid}/images`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (!data?.slide_images?.length) return;
        setSlides((prev) => prev.map((s, i) => ({
          ...s,
          imageBase64: data.slide_images[i] ?? s.imageBase64,
        })));
      })
      .catch(() => {});
  }, [translateJobUuid, slides.length]);

  // ── Check for active job on mount (blocks upload if already running) ──
  useEffect(() => {
    fetch("/api/jobs/check/screencast", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        setHasActiveJob(!!data.has_active_job);
      })
      .catch(() => setHasActiveJob(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Submit guard: check active jobs + storage limit ──
  const checkBeforeSubmit = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetch("/api/jobs/check/screencast", { credentials: "include" });
      const data = await res.json();
      setHasActiveJob(!!data.has_active_job);
      if (data.has_active_job) {
        return false;
      }
    } catch {
      // Ignore network errors, let backend handle it
    }
    return true;
  }, []);

  // ── Guard: check that a specific resumed job is still in a submittable state ──
  const checkJobStillValid = useCallback(async (jobUuid: string): Promise<"ok" | "running" | "deleted"> => {
    try {
      const res = await fetch(`/api/jobs/${jobUuid}`, { credentials: "include" });
      if (!res.ok) return "deleted";
      const job = await res.json();
      if (job.status === "awaiting_user" || job.status === "success" || job.status === "failed") return "ok";
      if (job.status === "pending" || job.status === "running") return "running";
      return "deleted";
    } catch {
      return "ok"; // Network error — let backend decide
    }
  }, []);

  // ── Helpers ──

  const resetAll = useCallback((deleteJob = true) => {
    // Abort any in-flight request and optionally delete the current job (DB + MinIO)
    abortControllerRef.current?.abort();
    if (deleteJob) {
      const uuidToDelete = translateJobUuid || currentJobUuidRef.current;
      if (uuidToDelete) {
        fetch(`/api/jobs/${uuidToDelete}`, { method: "DELETE", credentials: "include" }).catch(() => {});
        window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      }
    }
    currentJobUuidRef.current = null;

    setStep("upload");
    setFile(null);
    setFileError(null);
    setDragOver(false);
    setSpeed(0.9);
    setSlidePause(0.5);
    setGlossaryIds(["", "", ""]);
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
    setCorrectedFileName(null);
    setLightboxIndex(null);
    setAudioId("");
    setAudioCount(0);
    setAutoState("idle");
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setFailedRenderJobUuid(null);
    setFailedRenderIsAuto(false);
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    setMaxReachedIdx(0);
    setSourceLang("DE");
    setTargetLang("EN-US");
    setScriptInputMode("generate");
    setImportedScripts(null);
    setImportError(null);
    setTtsProvider(kokoroEnabled ? "kokoro" : fishSpeechEnabled ? "fish_speech" : elevenlabsEnabled ? "elevenlabs" : "kokoro");
    if (fileRef.current) fileRef.current.value = "";
  }, [videoUrl, translateJobUuid]);

  const handleStepClick = useCallback((index: number) => {
    if (hasDraggedRef.current) return;
    if (step === "rendering" || step === "generating-scripts") return;
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
  }, [maxReachedIdx, step]);

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

  const checkJobFolder = useCallback(async (): Promise<boolean> => {
    if (!translateJobUuid) return true;
    try {
      const res = await fetch(`/api/screencast/folder-exists/${translateJobUuid}`, { credentials: "include" });
      const data = await res.json();
      if (!data.exists) {
        goError("Job-Daten nicht mehr verfügbar — bitte neuen Screencast starten");
        return false;
      }
    } catch {
      // Ignore network errors, let backend handle it
    }
    return true;
  }, [translateJobUuid, goError]);

  const onRenderProgress = useCallback((status: import("@/lib/api").JobStatus) => {
    const p = status.progress as { step?: string; current?: number; total?: number } | null;
    if (!p?.step) { setRenderProgressLabel("In der Warteschlange…"); return; }
    if (p.step === "translate") setRenderProgressLabel("Präsentation wird übersetzt…");
    else if (p.step === "extract") setRenderProgressLabel("Folien werden analysiert…");
    else if (p.step === "scripts" && p.total != null)
      setRenderProgressLabel(`Skripte werden generiert… (${p.total} Folien)`);
    else if (p.step === "scripts") setRenderProgressLabel("Skripte werden generiert…");
    else if (p.step === "images") setRenderProgressLabel("Folienbilder werden vorbereitet…");
    else if (p.step === "tts" && p.current != null && p.total != null)
      setRenderProgressLabel(`Sprachsynthese: Folie ${p.current} von ${p.total}…`);
    else if (p.step === "tts") setRenderProgressLabel("Sprachsynthese läuft…");
    else if (p.step === "video" && p.current != null && p.total != null)
      setRenderProgressLabel(`Video-Clip ${p.current} von ${p.total} wird gerendert…`);
    else if (p.step === "video") setRenderProgressLabel("Video-Clips werden gerendert…");
    else if (p.step === "concat") setRenderProgressLabel("Videos werden zusammengefügt…");
    else if (p.step === "subtitles") setRenderProgressLabel("Untertitel werden eingebettet…");
    else setRenderProgressLabel("Video wird erstellt…");
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
    const ok = await checkBeforeSubmit();
    if (!ok) return;
    const signal = newSignal();
    setAutoDownloadBlob(null);
    setAutoDownloadName("");
    setAutoError("");
    setAutoState("processing");
    setStep("rendering");
    setLoading(true);

    try {
      const glossaryJson = mergeToApiJson(glossaryIds);
      const formData = new FormData();
      const voiceLabel = ttsProvider === "kokoro"
        ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
        : (voices.find(x => x.voice_id === voiceId)?.label ?? voiceId);

      formData.append("file", file);
      formData.append("speed", String(speed));
      formData.append("dpi", String(dpi));
      formData.append("voice_id", voiceId);
      formData.append("voice_label", voiceLabel);
      formData.append("provider", ttsProvider);
      formData.append("source_lang", sourceLang);
      formData.append("target_lang", targetLang);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);

      const uploadRes = await fetch("/api/screencast", { method: "POST", body: formData, credentials: "include", signal });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Upload fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid, isAuto: true }));
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      const jobResult = await pollJob(job_uuid, onRenderProgress, 5000, signal, () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000);
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");
      const meta = jobResult.meta ?? {};
      const aId = meta.audio_id as string | undefined;
      const aCount = meta.audio_count as number | undefined;
      if (aId) setAudioId(aId);
      if (aCount !== undefined) setAudioCount(aCount);
      const stem = file?.name?.replace(/\.pptx$/i, "") || "screencast";
      setAutoDownloadBlob(blob);
      setAutoDownloadName(`${stem}_screencast.mp4`);
      setLoading(false);
      setAutoState("done");
      setStep("upload");
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      setFailedRenderJobUuid(currentJobUuidRef.current);
      setFailedRenderIsAuto(true);
      setAutoState("error");
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file, speed, dpi, voiceId, sourceLang, targetLang, glossaryIds, mergeToApiJson, checkBeforeSubmit, onRenderProgress, goError]);

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

  const handleAutoZipDownload = useCallback(() => {
    if (!audioId) return;
    // Direct navigation — browser handles the download natively (instant start)
    const a = document.createElement("a");
    a.href = `/api/jobs/${audioId}/bundle`;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [audioId]);

  // ── Step: Upload → Translating (or auto) ──
  const handleUploadNext = useCallback(async () => {
    if (!file) return;
    if (mode === "auto") {
      handleAutoSubmit();
      return;
    }

    const ok = await checkBeforeSubmit();
    if (!ok) return;

    setStep("translating");
    setLoading(true);
    const signal = newSignal();

    // ── Same-language path: skip DeepL, upload as-is, go directly to user-prompt ──
    if (sourceLang === targetLang) {
      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch("/api/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          credentials: "include",
          signal,
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Unbekannter Fehler" }));
          throw new Error(parseDetail(error.detail, `Fehler: ${response.status}`));
        }

        const data: { translate_job_uuid: string; slide_texts: string[]; slide_images: string[] } =
          await response.json();

        if (data.translate_job_uuid) {
          setTranslateJobUuid(data.translate_job_uuid);
          window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
        }

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

    // ── DE path: translate via DeepL → queue job, poll, then show review ──
    try {
      const formData = new FormData();
      formData.append("file", file);
      const glossaryJson = mergeToApiJson(glossaryIds);
      if (glossaryJson) formData.append("glossary_json", glossaryJson);
      formData.append("fast_mode", String(fastMode));
      formData.append("source_lang", sourceLang);
      formData.append("target_lang", targetLang);

      const uploadRes = await fetch("/api/screencast/translate", {
        method: "POST",
        body: formData,
        credentials: "include",
        signal,
      });

      if (!uploadRes.ok) {
        const error = await uploadRes.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        throw new Error(parseDetail(error.detail, `Fehler: ${uploadRes.status}`));
      }

      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      setTranslateJobUuid(job_uuid);
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      // Poll until translation job completes (stops at awaiting_user)
      const jobResult = await pollJob(job_uuid, undefined, 3000, signal);
      currentJobUuidRef.current = null;

      // Result comes inline from the jobs endpoint for JSON-result jobs
      const data = (jobResult.result ?? {}) as unknown as TranslateResponse;

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
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [file, mode, sourceLang, targetLang, fastMode, handleAutoSubmit, checkBeforeSubmit, goError, glossaryIds, mergeToApiJson]);

  // ── Download translated PPTX ──
  const handleDownloadTranslatedPptx = useCallback(async () => {
    if (!translateJobUuid) return;
    try {
      const res = await fetch(`/api/screencast/pptx/${translateJobUuid}`, { credentials: "include" });
      if (!res.ok) throw new Error("Download fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const stem = file?.name?.replace(/\.pptx$/i, "") || "presentation";
      a.download = `${stem}.pptx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PPTX download failed:", err);
    }
  }, [translateJobUuid, file]);

  // ── Upload corrected PPTX ──
  const handleUploadCorrectedPptx = useCallback(
    async (correctedFile: File) => {
      setLoading(true);
      const signal = newSignal();

      try {
        const formData = new FormData();
        formData.append("file", correctedFile);
        if (translateJobUuid) formData.append("translate_job_uuid", translateJobUuid);

        const response = await fetch("/api/screencast/upload-corrected", {
          method: "POST",
          body: formData,
          credentials: "include",
          signal,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({ detail: "Fehler beim Hochladen" }));
          throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
        }

        const data: { slide_texts: string[]; slide_images: string[] } =
          await response.json();

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
    [goError, translateJobUuid],
  );

  // ── JSON script import handler ──
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

  // ── Translation review → Generate scripts ──
  const handleAcceptTranslation = useCallback(async () => {
    if (isGeneratingScriptsRef.current) return;
    // If we have a specific job to continue, check its current status directly.
    // checkBeforeSubmit would block here because awaiting_user now counts as active.
    if (translateJobUuid) {
      const validity = await checkJobStillValid(translateJobUuid);
      if (validity === "running") {
        goError("Dieser Job wird bereits in einem anderen Tab verarbeitet. Bitte wechseln Sie zur Jobliste.");
        return;
      }
      if (validity === "deleted") {
        goError("Der Job wurde gelöscht oder abgebrochen. Bitte starten Sie einen neuen Screencast.");
        return;
      }
    } else {
      const ok = await checkBeforeSubmit();
      if (!ok) { window.location.href = "/my-jobs"; return; }
    }
    if (!await checkJobFolder()) return;
    isGeneratingScriptsRef.current = true;
    if (translateJobUuid) currentJobUuidRef.current = translateJobUuid;
    setStep("generating-scripts");
    setLoading(true);
    window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
    const signal = newSignal();

    try {
      const scriptsData = await api.postJson<GenerateScriptsResponse>(
        "/api/screencast/generate-scripts",
        {
          slide_texts: slides.map((s) => s.extractedText),
          glossary_json: mergeToApiJson(glossaryIds),
          translate_job_uuid: translateJobUuid || null,
          add_greeting: true,
          add_closing: true,
          min_chars: 1500,
          max_chars: 2000,
          source_lang: sourceLang,
          target_lang: targetLang,
        },
        signal,
      );

      const updatedSlides = slides.map((s, i) => ({
        ...s,
        script: scriptsData.scripts[i] || "",
      }));
      setSlides(updatedSlides);

      currentJobUuidRef.current = null;
      setLoading(false);
      setStep("script-review");
      isGeneratingScriptsRef.current = false;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
    } catch (err) {
      isGeneratingScriptsRef.current = false;
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      if (err instanceof Error && err.name === "AbortError") return;
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, glossaryIds, mergeToApiJson, goError, checkJobFolder, checkBeforeSubmit, checkJobStillValid, translateJobUuid]);

  // ── Script autosave to bucket (debounced) ──
  const autosaveScripts = useCallback((updatedScripts: string[], accepted = false) => {
    if (!translateJobUuid) return;
    if (!accepted) {
      if (scriptAutosaveTimerRef.current) clearTimeout(scriptAutosaveTimerRef.current);
      scriptAutosaveTimerRef.current = setTimeout(() => {
        fetch(`/api/screencast/scripts/${translateJobUuid}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scripts: updatedScripts, accepted: false }),
          credentials: "include",
        }).catch(() => {});
      }, 1500);
    } else {
      fetch(`/api/screencast/scripts/${translateJobUuid}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scripts: updatedScripts, accepted: true }),
        credentials: "include",
      }).catch(() => {});
    }
  }, [translateJobUuid]);

  // ── Accept scripts → TTS settings + fire-and-forget prerender + save ──
  const handleAcceptScripts = useCallback(() => {
    autosaveScripts(slides.map((s) => s.script), true); // save accepted_scripts.json
    setStep("tts-settings");
    if (translateJobUuid) {
      fetch("/api/screencast/prerender-images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translate_job_uuid: translateJobUuid }),
        credentials: "include",
      }).catch(() => {}); // fire and forget
    }
  }, [translateJobUuid, slides, autosaveScripts]);

  // ── Shared: process render response (binary video + subtitles in header) ──
  const processRenderResponse = useCallback(async (response: Response) => {
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Render-Fehler" }));
      throw new Error(parseDetail(err.detail, `Fehler: ${response.status}`));
    }

    // Video comes as raw binary bytes
    const blob = await response.blob();
    console.log("[Screencast] Video blob size:", blob.size, "bytes");

    // Audio download info from headers
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

  // ── Parse job result for render jobs (meta: audio_id, audio_count) ──
  const processRenderResultFromJob = useCallback(async (jobResult: JobStatus) => {
    sessionStorage.removeItem(RENDER_SESSION_KEY);
    const { blob } = await downloadJobAsBlob(jobResult.job_uuid, "screencast.mp4");

    const meta = jobResult.meta ?? {};
    const aId = meta.audio_id as string | undefined;
    const aCount = meta.audio_count as number | undefined;

    if (aId) setAudioId(aId);
    if (aCount !== undefined) setAudioCount(aCount);
    setDownloadBlob(blob);
    const url = URL.createObjectURL(blob);
    setVideoUrl(url);
    setLoading(false);
    setStep("done");
  }, []);

  // ── Start rendering ──
  const handleStartRender = useCallback(async () => {
    setTtsSettingsError("");
    if (!translateJobUuid) {
      const ok = await checkBeforeSubmit();
      if (!ok) return;
    }
    setStep("rendering");
    setLoading(true);
    const signal = newSignal();
    try {
      // No signal on the POST — ensures we always get job_uuid before checking abort.
      // If signal fires during the POST, the job still starts on the backend.
      // We catch that case below and cancel immediately.
      const uploadRes = await fetch("/api/screencast/render", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scripts: slides.map((s) => s.script),
          translate_job_uuid: translateJobUuid,
          voice_id: voiceId,
          voice_label: ttsProvider === "kokoro"
            ? (() => { const v = kokoroVoices.find(x => x.voice_id === voiceId); return v ? `${KOKORO_ACCENT_LABEL[v.accent] ?? ""} ${v.name}`.trim() : voiceId; })()
            : (voices.find(x => x.voice_id === voiceId)?.label ?? voiceId),
          speed,
          slide_pause: slidePause,
          dpi,
          provider: ttsProvider,
        }),
        credentials: "include",
      });
      if (!uploadRes.ok) {
        const err = await uploadRes.json().catch(() => ({ detail: "Render-Fehler" }));
        // 409 = previous render still stopping — stay on settings, show inline message
        if (uploadRes.status === 409) {
          setStep("tts-settings");
          setLoading(false);
          setTtsSettingsError("Der vorherige Render wird noch beendet. Bitte einen Moment warten und erneut versuchen.");
          return;
        }
        throw new Error(parseDetail(err.detail, `Fehler: ${uploadRes.status}`));
      }
      const { job_uuid } = await uploadRes.json();
      currentJobUuidRef.current = job_uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid: job_uuid, isAuto: false }));
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));

      // If user clicked cancel while POST was in flight, cancel the job now
      if (signal.aborted) {
        await fetch(`/api/jobs/${job_uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
        currentJobUuidRef.current = null;
        return;
      }

      const jobResult = await pollJob(job_uuid, onRenderProgress, 5000, signal, () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000);
      currentJobUuidRef.current = null;
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      setFailedRenderJobUuid(currentJobUuidRef.current);
      setFailedRenderIsAuto(false);
      goError(err instanceof Error ? err.message : "Unbekannter Fehler");
    }
  }, [slides, translateJobUuid, voiceId, speed, slidePause, dpi, goError, processRenderResultFromJob, checkBeforeSubmit, onRenderProgress]);

  // ── Retry failed render job ──
  const handleRetryRender = useCallback(async () => {
    const uuid = failedRenderJobUuid;
    if (!uuid) return;
    try {
      const res = await fetch(`/api/jobs/${uuid}/retry`, { method: "POST", credentials: "include" });

      if (res.status === 409) {
        // Job already running or succeeded — check actual status and continue accordingly
        const jobRes = await fetch(`/api/jobs/${uuid}`, { credentials: "include" });
        const jobData = await jobRes.json();
        if (jobData.status === "failed") {
          // Still failed → blocked by concurrent job limit
          const err = await res.json().catch(() => ({}));
          throw new Error(parseDetail(err.detail, "Zu viele laufende Jobs. Bitte warten bis ein Job abgeschlossen ist."));
        }
        if (jobData.status === "success") {
          setFailedRenderJobUuid(null);
          if (failedRenderIsAuto) setAutoState("done");
          await processRenderResultFromJob(jobData);
          return;
        }
        // Job is running — fall through to polling below
      } else if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Retry fehlgeschlagen" }));
        throw new Error(parseDetail(err.detail, "Retry fehlgeschlagen"));
      }

      setRenderProgressLabel("In der Warteschlange…");
      currentJobUuidRef.current = uuid;
      sessionStorage.setItem(RENDER_SESSION_KEY, JSON.stringify({ uuid, isAuto: failedRenderIsAuto }));
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      setStep("rendering");
      setErrorMessage("");
      setLoading(true);
      if (failedRenderIsAuto) { setAutoState("processing"); setAutoError(""); }
      const signal = newSignal();
      const jobResult = await pollJob(
        uuid, onRenderProgress, 3000, signal,
        () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000,
      );
      currentJobUuidRef.current = null;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      setFailedRenderJobUuid(null);
      window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
      if (failedRenderIsAuto) setAutoState("done");
      await processRenderResultFromJob(jobResult);
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return;
      sessionStorage.removeItem(RENDER_SESSION_KEY);
      const msg = err instanceof Error ? err.message : "Retry fehlgeschlagen";
      setFailedRenderJobUuid(uuid);
      if (failedRenderIsAuto) { setAutoState("error"); setAutoError(msg); }
      goError(msg);
    }
  }, [failedRenderJobUuid, failedRenderIsAuto, file, onRenderProgress, processRenderResultFromJob, newSignal, goError]);

  // ── Resume active render job after page refresh ──
  useEffect(() => {
    const saved = sessionStorage.getItem(RENDER_SESSION_KEY);
    if (!saved) return;
    let parsed: { uuid: string; isAuto: boolean };
    try { parsed = JSON.parse(saved); } catch { sessionStorage.removeItem(RENDER_SESSION_KEY); return; }
    const { uuid, isAuto } = parsed;

    fetch(`/api/jobs/${uuid}`, { credentials: "include" })
      .then(r => r.json())
      .then(job => {
        if (job.status === "success") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          return; // job already done, show upload form — result in Jobs Panel
        }
        if (job.status === "failed") {
          sessionStorage.removeItem(RENDER_SESSION_KEY);
          setFailedRenderJobUuid(uuid);
          setFailedRenderIsAuto(isAuto);
          if (isAuto) { setAutoError(job.error || "Job fehlgeschlagen"); setAutoState("error"); }
          else { goError(job.error || "Job fehlgeschlagen"); }
          return;
        }
        // Still running/pending — resume polling
        currentJobUuidRef.current = uuid;
        setFailedRenderIsAuto(isAuto);
        setRenderProgressLabel("Verbindung wiederhergestellt…");
        setStep("rendering");
        setLoading(true);
        if (isAuto) setAutoState("processing");
        const ctrl = new AbortController();
        abortControllerRef.current = ctrl;
        pollJob(uuid, onRenderProgress, 3000, ctrl.signal,
          () => setRenderProgressLabel("Kein Fortschritt seit 60 Sek. — falls der Job hängt, bitte Wiederholen klicken…"), 60_000)
          .then(jobResult => {
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            currentJobUuidRef.current = null;
            setFailedRenderJobUuid(null);
            window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
            if (isAuto) setAutoState("done");
            processRenderResultFromJob(jobResult);
          })
          .catch(err => {
            if (err instanceof Error && err.name === "AbortError") return;
            sessionStorage.removeItem(RENDER_SESSION_KEY);
            setFailedRenderJobUuid(uuid);
            if (isAuto) { setAutoState("error"); }
            goError(err.message);
          });
      })
      .catch(() => sessionStorage.removeItem(RENDER_SESSION_KEY));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    const updated = slides.map((s, i) => i === index ? { ...s, script: editBuffer } : s);
    setSlides(updated);
    setEditingSlide(null);
    setEditBuffer("");
    autosaveScripts(updated.map((s) => s.script));
  };

  const cancelEdit = () => {
    setEditingSlide(null);
    setEditBuffer("");
  };

  // ── Per-slide AI regeneration ──
  const openRegen = (index: number) => {
    regeneratingSlideRef.current = index;
    setRegeneratingSlide(index);
    setRegenPrompt("");
    setRegenMessages([]);
  };

  const closeRegen = () => {
    regeneratingSlideRef.current = null;
    setRegeneratingSlide(null);
    setRegenPrompt("");
    setRegenMessages([]);
    setRegenAnchorText("");
    setRegenAnchorSlide(null);
  };

  const runRegen = async (index: number) => {
    const userText = regenPrompt.trim();
    if (!userText) return;
    const newMessages: { role: "user" | "assistant"; content: string }[] = [
      ...regenMessages,
      { role: "user", content: userText },
    ];
    setRegenMessages(newMessages);
    setRegenPrompt("");
    setRegenLoading(true);
    try {
      const result = await api.postJson<{ script: string }>(
        "/api/screencast/regenerate-slide-script",
        {
          slide_text: slides[index].extractedText,
          current_script: slides[index].script || "",
          messages: newMessages,
          selected_text: regenAnchorText || null,
          target_lang: targetLang,
        },
      );
      setRegenMessages([...newMessages, { role: "assistant", content: result.script }]);
    } catch {
      setRegenMessages([...newMessages, { role: "assistant", content: "Fehler beim Generieren." }]);
    } finally {
      setRegenLoading(false);
    }
  };

  const applyRegen = (index: number, mode: "replace-selection" | "insert-before" | "insert-after" | "replace-all", content: string) => {
    const current = slides[index].script || "";
    let newScript = current;
    if (mode === "replace-all" || !regenAnchorText) {
      newScript = content;
    } else if (mode === "replace-selection") {
      newScript = current.replace(regenAnchorText, content);
    } else if (mode === "insert-before") {
      newScript = current.replace(regenAnchorText, content + " " + regenAnchorText);
    } else if (mode === "insert-after") {
      newScript = current.replace(regenAnchorText, regenAnchorText + " " + content);
    }
    const updated = slides.map((s, i) => i === index ? { ...s, script: newScript } : s);
    setSlides(updated);
    autosaveScripts(updated.map((s) => s.script));
    closeRegen();
  };

  // ── Back to script review (from tts-settings) ──
  const handleBackToScripts = () => {
    if (step === "rendering") return;
    setStep("script-review");
  };

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
  const totalChars = slides.reduce((sum, s) => sum + (s.script?.length ?? 0), 0);
  const scriptOverLimit = totalChars > SCREENCAST_MAX_CHARS;


  return (
    <ProtectedRoute>
      <Header showLogout />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <BackLink />
        {/* Step indicator */}
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
                  const isSkipped = sourceLang === "EN" && (i === 1 || i === 2);
                  const isDone = !isSkipped && i < currentIdx;
                  const isActive = i === currentIdx;
                  const isReached = i <= maxReachedIdx;
                  const isClickable = !isSkipped && isReached && !isActive && i !== 0 && i !== 1 && i !== 6 && step !== "rendering";
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
                            ${isActive ? "bg-primary text-white" : ""}
                            ${isDone ? "bg-primary/20 text-primary" : ""}
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
                            i < currentIdx && !isSkipped ? "bg-primary" : "bg-gray-200"
                          }`}
                          aria-hidden="true"
                        />
                      )}
                    </li>
                  );
                })}
              </ol>
            </nav>
            <div className="flex justify-between mb-6">
              <button
                onClick={() => resetAll(step !== "done")}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs text-gray-400 hover:text-red-500 rounded transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                Neu starten
              </button>
              <button
                onClick={() => resetAll(step !== "done")}
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

        {/* ── Resume loading ── */}
        {resumeLoading && (
          <section className="animate-[fadeIn_0.2s_ease-out] text-center py-16" role="status" aria-live="polite">
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700">Screencast wird wiederhergestellt…</p>
          </section>
        )}

        {/* ── Step: Upload ── */}
        {!resumeLoading && step === "upload" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <div className="flex items-baseline justify-between mb-1">
              <h1 className="text-xl font-bold">Screencast erstellen</h1>
              {showDemoLink && (
                <a href="/tools/screencast-demo" className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-200 hover:bg-amber-200 transition-colors">
                  Demo ansehen →
                </a>
              )}
            </div>
            <p className="text-sm text-gray-500 mb-6">
              Laden Sie eine PowerPoint-Präsentation hoch. Die Präsentation wird
              per DeepL übersetzt und als vertontes Video exportiert.
            </p>

            {/* Banner: active job → hard block */}
            {hasActiveJob === true && (
              <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-4">
                <p className="text-sm font-semibold text-red-800">
                  Sie haben bereits 5 Jobs in der Warteschlange, kein weiterer ist möglich.
                </p>
                <p className="mt-1 text-sm text-red-700">
                  Warten Sie bis ein Job abgeschlossen ist oder löschen Sie einen in der{" "}
                  <a href="/my-jobs" className="underline hover:text-red-900 font-medium">
                    Jobliste
                  </a>{" "}
                  .
                </p>
              </div>
            )}

            {/* Drag & Drop zone */}
            <div
              onDragOver={hasActiveJob ? undefined : handleDragOver}
              onDragLeave={hasActiveJob ? undefined : handleDragLeave}
              onDrop={hasActiveJob ? undefined : handleDrop}
              onClick={hasActiveJob ? undefined : () => fileRef.current?.click()}
              className={`
                relative mb-4 flex flex-col items-center justify-center
                rounded-lg border-2 border-dashed px-6 py-10
                transition-colors
                ${hasActiveJob
                  ? "border-gray-200 bg-gray-50 opacity-40 cursor-not-allowed"
                  : "cursor-pointer"
                }
                ${!hasActiveJob && (
                  dragOver
                    ? "border-primary bg-primary/5"
                    : file
                      ? "border-green-400 bg-green-50"
                      : "border-gray-300 hover:border-gray-400"
                )}
                ${autoState === "processing" ? "opacity-50 pointer-events-none" : ""}
              `}
            >
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                className="hidden"
                disabled={!!hasActiveJob}
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
                    <span className="text-primary font-medium">
                      durchsuchen
                    </span>
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Nur .pptx-Datei
                  </p>
                </>
              )}
            </div>

            {/* Skip translation checkbox */}
            <label className="flex items-start gap-3 mb-4 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={sourceLang === targetLang}
                onChange={(e) => {
                  if (e.target.checked) {
                    // mark as "already translated" by setting source == target
                    setSourceLang(targetLang);
                  } else {
                    // restore default source
                    setSourceLang("DE");
                  }
                }}
                disabled={autoState === "processing"}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <span className="text-sm font-medium text-gray-700">
                Präsentation bereits übersetzt (Übersetzung überspringen)
              </span>
            </label>

            {/* Language selection + Glossary — only when translation is needed */}
            {sourceLang !== targetLang && (
              <>
                {languages.length > 0 && (
                  <div className="flex gap-3 mb-4">
                    <div className="flex-1">
                      <label className="block text-xs font-medium text-gray-500 mb-1">Quellsprache</label>
                      <select
                        value={sourceLang}
                        onChange={(e) => setSourceLang(e.target.value)}
                        disabled
                        className="w-full rounded-md border border-gray-300 text-sm py-2 px-3 focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50"
                      >
                        {languages.map((l) => (
                          <option key={l.id} value={l.id}>{l.label}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex-1">
                      <label className="block text-xs font-medium text-gray-500 mb-1">Zielsprache</label>
                      <select
                        value={targetLang}
                        onChange={(e) => setTargetLang(e.target.value)}
                        disabled
                        className="w-full rounded-md border border-gray-300 text-sm py-2 px-3 focus:ring-2 focus:ring-primary focus:border-primary disabled:opacity-50"
                      >
                        {languages.map((l) => (
                          <option key={l.id} value={l.id}>{l.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                )}

                <GlossarySelector
                  values={glossaryIds}
                  onChange={setGlossaryIds}
                />
              </>
            )}

            {fileError && (
              <p className="mb-4 text-sm text-red-600" role="alert">
                {fileError}
              </p>
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
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
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

            {/* Fast mode — only relevant in manual mode and for admins */}
            {mode === "manual" && isAdmin && (
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



            {/* Submit */}
            <div className="flex gap-3">
              <button
                onClick={handleUploadNext}
                disabled={!file || autoState === "processing" || !!hasActiveJob}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {mode === "auto" ? "Screencast erstellen" : "Weiter"}
              </button>
            </div>

            {/* Auto mode status */}
            {isAutoMode && (
              <ScreencastStatus
                state={autoState}
                fileName={autoDownloadName}
                errorMessage={autoError}
                progressLabel={autoState === "processing" ? renderProgressLabel : undefined}
                onDownload={handleAutoDownload}
                onReset={resetAll}
                onRetry={failedRenderJobUuid ? handleRetryRender : undefined}
                hasZip={!!audioId}
                onZipDownload={handleAutoZipDownload}
              />
            )}
          </section>
        )}

        {/* ── Step: Translating (loading) ── */}
        {!resumeLoading && step === "translating" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">
              {sourceLang === targetLang
                ? "Präsentation wird vorbereitet..."
                : "Präsentation wird übersetzt..."}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Das kann je nach Dateigröße einige Sekunden dauern.
            </p>
            <button
              onClick={() => {
                const uuid = currentJobUuidRef.current;
                currentJobUuidRef.current = null;
                abortControllerRef.current?.abort();
                if (uuid) { fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {}); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }
                setStep("upload"); setLoading(false);
              }}
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
        {!resumeLoading && step === "user-prompt" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-1">
              Wie sollen die Skripte erstellt werden?
            </h2>

            {/* ── Script input mode selection ── */}
            <div className="mt-3 space-y-2">
              {/* Option: generate (default) */}
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "generate" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input
                  type="radio"
                  name="scriptInputMode"
                  value="generate"
                  checked={scriptInputMode === "generate"}
                  onChange={() => { setScriptInputMode("generate"); setImportedScripts(null); setImportError(null); }}
                  className="mt-0.5 accent-primary"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900">KI-Generierung</span>
                  <p className="text-xs text-gray-500 mt-0.5">KI erstellt Skripte automatisch basierend auf den Folieninhalten.</p>
                </div>
              </label>

              {/* Option: manual */}
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "manual" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input
                  type="radio"
                  name="scriptInputMode"
                  value="manual"
                  checked={scriptInputMode === "manual"}
                  onChange={() => { setScriptInputMode("manual"); setImportedScripts(null); setImportError(null); }}
                  className="mt-0.5 accent-primary"
                />
                <div>
                  <span className="text-sm font-medium text-gray-900">Manuell eingeben</span>
                  <p className="text-xs text-gray-500 mt-0.5">Alle Textfelder bleiben leer – Sie tippen die Skripte selbst ein.</p>
                </div>
              </label>

              {/* Option: import JSON */}
              <label className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${scriptInputMode === "import" ? "border-primary bg-primary/5" : "border-gray-200 hover:border-gray-300"}`}>
                <input
                  type="radio"
                  name="scriptInputMode"
                  value="import"
                  checked={scriptInputMode === "import"}
                  onChange={() => setScriptInputMode("import")}
                  className="mt-0.5 accent-primary"
                />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-gray-900">Skript importieren</span>
                  <p className="text-xs text-gray-500 mt-0.5">JSON-Datei hochladen – Array von Strings, ein Eintrag pro Folie.</p>
                  {scriptInputMode === "import" && (
                    <div className="mt-2">
                      <div
                        onDragOver={(e) => { e.preventDefault(); setJsonDragOver(true); }}
                        onDragLeave={() => setJsonDragOver(false)}
                        onDrop={(e) => { e.preventDefault(); setJsonDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) handleJsonImport(f); }}
                        onClick={() => jsonFileRef.current?.click()}
                        className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed px-4 py-5 cursor-pointer transition-colors
                          ${importedScripts
                            ? "border-green-400 bg-green-50"
                            : jsonDragOver
                              ? "border-primary bg-primary/5"
                              : "border-gray-300 hover:border-gray-400"
                          }`}
                      >
                        <input
                          ref={jsonFileRef}
                          type="file"
                          accept=".json"
                          className="hidden"
                          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleJsonImport(f); e.target.value = ""; }}
                        />
                        {importedScripts ? (
                          <>
                            <svg className="w-6 h-6 text-green-500 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            <p className="text-xs font-medium text-green-700">{importedScripts.length} Skript{importedScripts.length !== 1 ? "e" : ""} geladen</p>
                            <p className="text-xs text-gray-400 mt-0.5">Klicken oder ziehen zum Ersetzen</p>
                          </>
                        ) : (
                          <>
                            <svg className="w-6 h-6 text-gray-400 mb-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                            <p className="text-xs text-gray-600">JSON-Datei hierher ziehen oder <span className="text-primary font-medium">auswählen</span></p>
                          </>
                        )}
                      </div>
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

            {/* Einstellungen — nur bei KI-Generierung */}
            {scriptInputMode === "generate" && (
              <div className="mt-5 space-y-4">
                {/* Skriptstil */}
              </div>
            )}

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
        {!resumeLoading && step === "translation-review" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-1">
              Übersetzung prüfen
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Die Präsentation wurde übersetzt. Sie können die übersetzte
              PPTX herunterladen, prüfen und optional eine korrigierte
              Version hochladen.
            </p>

            {/* Thumbnail grid — hidden in fast mode */}
            {!fastMode && (
              <div className="flex flex-wrap justify-center gap-2 mb-6">
                {slides.map((slide, i) => (
                  <button
                    key={i}
                    onClick={() => setLightboxIndex(i)}
                    style={{ width: "100px" }}
                    className="relative rounded-lg overflow-hidden border border-gray-200 hover:border-primary transition-colors focus-visible:outline-2 focus-visible:outline-primary group flex-shrink-0"
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

            {/* Actions */}
            <div className="flex flex-col gap-3 mb-4">
              <button
                onClick={handleDownloadTranslatedPptx}
                className="w-full px-4 py-2 text-sm text-primary border border-primary rounded-md hover:bg-primary/5 transition-colors flex items-center justify-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                PPTX
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
                onClick={() => { setMaxReachedIdx((v) => Math.max(v, 3)); setStep("user-prompt"); }}
                disabled={loading}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Übersetzung übernehmen und weiter
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Generating Scripts (loading) ── */}
        {!resumeLoading && step === "generating-scripts" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700 animate-pulse">
              Sprechskripte werden generiert...
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Die KI erstellt Skripte für {slides.length} Folien.
            </p>
            <button
              onClick={() => {
                const uuid = currentJobUuidRef.current;
                currentJobUuidRef.current = null;
                abortControllerRef.current?.abort();
                if (uuid) { fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {}); window.dispatchEvent(new CustomEvent("kis-jobs-changed")); }
                setStep("translation-review"); setLoading(false);
              }}
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
        {!resumeLoading && step === "script-review" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-1">
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
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
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
                        <div className="flex flex-col gap-4">
                          {/* Slide image — hidden in fast mode */}
                          {!fastMode && (
                            <div className="flex-shrink-0" style={{ width: "100px" }}>
                              {slide.imageBase64 ? (
                                <button
                                  onClick={() => { setLightboxIndex(i); }}
                                  className="w-full rounded border border-gray-200 hover:border-primary transition-colors overflow-hidden cursor-zoom-in focus-visible:outline-2 focus-visible:outline-primary"
                                  aria-label={`Folie ${i + 1} vergrößern`}
                                >
                                  <img
                                    src={`data:image/png;base64,${slide.imageBase64}`}
                                    alt={`Folie ${i + 1}`}
                                    className="w-full"
                                  />
                                </button>
                              ) : (
                                <div className="w-full aspect-video bg-gray-100 rounded flex items-center justify-center">
                                  <Spinner size="sm" />
                                </div>
                              )}
                            </div>
                          )}

                          {/* Script */}
                          <div className="w-full flex flex-col">
                            {isEditing ? (
                              <>
                                <textarea
                                  value={editBuffer}
                                  onChange={(e) =>
                                    setEditBuffer(e.target.value)
                                  }
                                  rows={8}
                                  className="w-full rounded-md border border-primary px-3 py-2 text-sm font-mono text-gray-900 focus:ring-1 focus:ring-primary focus:outline-none"
                                  aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                                />
                                <div className="flex items-center justify-between mt-2">
                                  <span className="text-xs text-gray-400">
                                    ca. {wc} Wörter
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
                                      className="px-3 py-1 text-xs bg-primary text-white rounded hover:bg-primary-hover transition-colors"
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
                                    ca. {wc} Wörter
                                  </span>
                                  <div className="flex items-center gap-1">
                                    {/* KI-Regenerierung */}
                                    <button
                                      onClick={() => openRegen(i)}
                                      className={`w-7 h-7 flex items-center justify-center rounded-full transition-colors hover:text-primary hover:bg-gray-100 ${regenAnchorSlide === i && regenAnchorText ? "text-primary" : "text-gray-400"}`}
                                      aria-label={`Skript für Folie ${i + 1} per KI neu generieren`}
                                      title="Mit KI neu generieren"
                                    >
                                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                                      </svg>
                                    </button>
                                    {/* Manuell bearbeiten */}
                                    <button
                                      onClick={() => startEdit(i)}
                                      className="w-7 h-7 flex items-center justify-center rounded-full text-gray-400 hover:text-primary hover:bg-gray-100 transition-colors"
                                      aria-label={`Skript für Folie ${i + 1} bearbeiten`}
                                    >
                                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                      </svg>
                                    </button>
                                  </div>
                                </div>
                                <p
                                  className="text-sm font-mono text-gray-700 whitespace-pre-wrap leading-relaxed"
                                  onMouseUp={() => {
                                    const text = window.getSelection()?.toString().trim();
                                    setRegenAnchorText(text || "");
                                    setRegenAnchorSlide(text ? i : null);
                                  }}
                                >
                                  {slide.script || (
                                    <span className="text-gray-400 italic">
                                      Kein Skript (leere Folie)
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

            {slides.filter((s) => !s.script.trim()).length > 0 && (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-300 rounded-md px-3 py-2">
                {slides.filter((s) => !s.script.trim()).length} Folie(n) haben kein Skript. Bitte füllen Sie diese aus, bevor Sie fortfahren.
              </p>
            )}

            <div className="flex gap-3">
              <button
                onClick={handleAcceptScripts}
                disabled={editingSlide !== null}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Alle Skripte übernehmen
              </button>
            </div>
          </section>
        )}

        {/* ── Step: TTS Settings ── */}
        {!resumeLoading && step === "tts-settings" && (
          <section className="animate-[fadeIn_0.3s_ease-out]">
            <h2 className="text-lg font-bold mb-6">
              Einstellungen
            </h2>

            {/* TTS-Anbieter */}
            {providersLoaded && (elevenlabsEnabled || fishSpeechEnabled || kokoroEnabled || mylabEnabled || thorstenEnabled) && (
            <div className="mb-2">
              <label htmlFor="sc-provider-select" className="block text-sm font-medium text-gray-700 mb-2">
                TTS-Anbieter
              </label>
              <select
                id="sc-provider-select"
                value={ttsProvider}
                onChange={(e) => {
                  const p = e.target.value as "elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten";
                  setTtsProvider(p);
                  if (p === "fish_speech") setVoiceId("default");
                  else if (p === "kokoro" && kokoroVoices.length > 0) setVoiceId(kokoroVoices[0].voice_id);
                  else if (p === "mylab" && mylabVoices.length > 0) setVoiceId(mylabVoices[0].voice_id);
                  else if (p === "thorsten" && thorstenVoices.length > 0) setVoiceId(thorstenVoices[0].voice_id);
                  else if (p === "elevenlabs" && voices.length > 0) setVoiceId(voices[0].voice_id);
                }}
                className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary"
              >
                {kokoroEnabled && <option value="kokoro">Kokoro TTS</option>}
                {mylabEnabled && <option value="mylab">THL myLab (XTTS-v2)</option>}
                {thorstenEnabled && <option value="thorsten">Thorsten (deutsch, lokal)</option>}
                {fishSpeechEnabled && <option value="fish_speech">Fish Speech 1.5.1</option>}
                {elevenlabsEnabled && <option value="elevenlabs">ElevenLabs</option>}
              </select>
            </div>
            )}

            {/* Stimme */}
            {providersLoaded && (elevenlabsEnabled || fishSpeechEnabled || kokoroEnabled || mylabEnabled || thorstenEnabled) && (
            <div className="mb-6 mt-4 space-y-3">
              <div>
                <label htmlFor="sc-voice-select" className="block text-sm font-medium text-gray-700 mb-2">
                  Stimme
                </label>
                <select
                  id="sc-voice-select"
                  value={voiceId}
                  onChange={(e) => setVoiceId(e.target.value)}
                  disabled={ttsProvider === "fish_speech" || ttsProvider === "thorsten"}
                  className="block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 shadow-sm focus:border-primary focus:ring-1 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {ttsProvider === "fish_speech" ? (
                    <option value="default">Standard</option>
                  ) : ttsProvider === "kokoro" ? (
                    kokoroVoices.map((v) => {
                      const flag = v.accent === "American" ? "🇺🇸" : v.accent === "British" ? "🇬🇧" : "";
                      return (
                        <option key={v.voice_id} value={v.voice_id}>
                          {flag} {v.name}
                        </option>
                      );
                    })
                  ) : ttsProvider === "mylab" ? (
                    mylabVoices.map((v) => (
                      <option key={v.voice_id} value={v.voice_id}>
                        {v.name} – {v.description}
                      </option>
                    ))
                  ) : ttsProvider === "thorsten" ? (
                    thorstenVoices.map((v) => (
                      <option key={v.voice_id} value={v.voice_id}>
                        {v.name}
                      </option>
                    ))
                  ) : (
                    voices.map((v) => {
                      const desc = translateDesc(v.description);
                      return (
                        <option key={v.voice_id} value={v.voice_id}>
                          {desc ? `${v.label} – ${desc}` : v.label}
                        </option>
                      );
                    })
                  )}
                </select>
              </div>
              {ttsProvider === "elevenlabs" && (
                <a
                  href="/tools/tts/voices"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Stimmen anhören →
                </a>
              )}
              {ttsProvider === "kokoro" && (
                <a
                  href="/tools/tts/voices?tab=kokoro"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Stimmen anhören →
                </a>
              )}
              {ttsProvider === "mylab" && (
                <a
                  href="/tools/tts/voices?tab=mylab"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  Stimmen anhören →
                </a>
              )}
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
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
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0s</span>
                <span>3s</span>
              </div>
            </div>


            {/* DPI / Bildqualität */}
            <div className="space-y-2">
              <p className="text-sm font-medium text-gray-700">Bildqualität</p>
              <div className="flex flex-col gap-2">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="dpi"
                    value={96}
                    checked={dpi === 96}
                    onChange={() => setDpi(96)}
                    className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700">Geringe Qualität</span>
                    <p className="text-xs text-gray-400 mt-0.5">Schnellere Verarbeitung, geringere Bildschärfe</p>
                  </div>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="dpi"
                    value={144}
                    checked={dpi === 144}
                    onChange={() => setDpi(144)}
                    className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700">Standard</span>
                    <p className="text-xs text-gray-400 mt-0.5">Empfohlen, gute Bildqualität</p>
                  </div>
                </label>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="dpi"
                    value={300}
                    checked={dpi === 300}
                    onChange={() => setDpi(300)}
                    className="mt-0.5 h-4 w-4 text-primary focus:ring-primary"
                  />
                  <div>
                    <span className="text-sm font-medium text-gray-700">Maximale Qualität</span>
                    <p className="text-xs text-gray-400 mt-0.5">Höchste Bildschärfe, ca. 4–5× längere Bearbeitungszeit</p>
                  </div>
                </label>
              </div>
            </div>

            {/* Summary */}
            <div className="mb-4 rounded-lg bg-gray-50 px-4 py-3">
              <p className="text-sm text-gray-700">
                <span className="font-medium">{slides.length}</span>{" "}
                Folien · ca.{" "}
                <span className="font-medium">{totalWords}</span>{" "}
                Wörter ·{" "}
                <span className={`font-medium ${scriptOverLimit ? "text-red-600" : ""}`}>
                  {totalChars.toLocaleString("de-DE")}
                </span>{" "}
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
                  <button
                    onClick={handleBackToScripts}
                    className="mt-2 px-3 py-1.5 text-sm font-medium text-red-700 border border-red-300 rounded-md hover:bg-red-100 transition-colors"
                  >
                    Zurück zum Skript bearbeiten
                  </button>
                </div>
              </div>
            )}

            {ttsSettingsError && (
              <p className="text-sm text-amber-600 bg-amber-50 border border-amber-200 rounded-md px-3 py-2 mb-3">
                {ttsSettingsError}
              </p>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleBackToScripts}
                className="px-4 py-3 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Zurück
              </button>
              <button
                onClick={handleStartRender}
                disabled={scriptOverLimit}
                className="flex-1 px-4 py-3 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Screencast erstellen
              </button>
            </div>
          </section>
        )}

        {/* ── Step: Rendering (loading) ── */}
        {!resumeLoading && step === "rendering" && (
          <section
            className="animate-[fadeIn_0.3s_ease-out] text-center py-16"
            role="status"
            aria-live="polite"
          >
            <Spinner size="lg" className="justify-center mb-4" />
            <p className="text-sm text-gray-700">
              {renderProgressLabel || "Video wird erstellt..."}
            </p>
            {!renderProgressLabel && (
              <p className="text-xs text-gray-400 mt-2">
                Vertonung und Videoproduktion, das kann ein paar Minuten dauern.
              </p>
            )}
            <button
              onClick={async () => {
                const uuid = currentJobUuidRef.current;
                currentJobUuidRef.current = null;
                abortControllerRef.current?.abort();
                if (uuid) {
                  await fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
                  window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
                }
                setRenderProgressLabel("");
                setAutoState("idle");
                setStep(mode === "auto" ? "upload" : "tts-settings");
                setLoading(false);
              }}
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
        {!resumeLoading && step === "done" && (
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
            <h2 className="text-lg font-bold mb-2 text-center">
              Fertig! Ihr Screencast ist bereit.
            </h2>

            {/* Video player */}
            {videoUrl && (
              <div className="mb-6 rounded-lg overflow-hidden border border-gray-200">
                <video
                  key={videoUrl}
                  controls
                  className="w-full"
                >
                  <source src={videoUrl} type="video/mp4" />
                  Ihr Browser unterstützt kein HTML5-Video.
                </video>
              </div>
            )}

            {/* Downloads: MP4 + Alles als ZIP */}
            <div className="flex justify-center gap-3 mb-4">
              <button
                onClick={handleDownload}
                aria-label="MP4"
                className="px-6 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors flex items-center gap-2"
              >
                <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                MP4
              </button>
              {audioId && (
                <a
                  href={`/api/jobs/${audioId}/bundle`}
                  download
                  aria-label="Alles herunterladen (ZIP)"
                  className="px-6 py-2 bg-white text-primary border border-primary text-sm font-medium rounded-md hover:bg-primary/5 transition-colors flex items-center gap-2"
                >
                  <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  Alles herunterladen (ZIP)
                </a>
              )}
            </div>

            {/* Row 3: Reset */}
            <div className="flex justify-center">
              <button
                onClick={() => resetAll(false)}
                aria-label="Neue Präsentation hochladen"
                className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
              >
                Neue Präsentation
              </button>
            </div>
          </section>
        )}

        {/* ── Error state ── */}
        {!resumeLoading && step === "error" && (
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
              <p className="text-sm text-red-600 mb-3">
                {errorMessage}
              </p>
            )}
            {failedRenderJobUuid && (
              <p className="text-xs text-gray-500 mb-5">
                Klicke auf <strong>Wiederholen</strong> — bereits fertige Clips und Audio werden nicht wiederholt.
              </p>
            )}
            <div className="flex gap-3 justify-center">
              {failedRenderJobUuid && (
                <button
                  onClick={handleRetryRender}
                  aria-label="Job wiederholen"
                  className="px-6 py-2 text-sm text-white bg-primary rounded-md hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
                >
                  Wiederholen
                </button>
              )}
              <button
                onClick={() => resetAll()}
                aria-label="Neue Präsentation hochladen"
                className="px-6 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary transition-colors"
              >
                Neue Präsentation
              </button>
            </div>
          </section>
        )}
        {/* ── Lightbox modal (shared across steps) ── */}
        {!fastMode && lightboxIndex !== null && slides[lightboxIndex]?.imageBase64 && (
          <div
            className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4"
            onClick={() => { setLightboxIndex(null); }}
            role="dialog"
            aria-modal="true"
            aria-label={`Folie ${lightboxIndex + 1}`}
          >
            <div
              className="relative max-w-4xl w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => { setLightboxIndex(null); }}
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


        {/* ── KI-Regenerierung Modal ── */}
        {regeneratingSlide !== null && (
          <>
            {/* Backdrop — subtle */}
            <div className="fixed inset-0 z-40" />

            {/* Panel — Bottom Sheet mobile, right-anchored sidebar on desktop */}
            <div className={`fixed z-50 shadow-2xl flex flex-col overflow-hidden sm:inset-auto sm:top-16 sm:bottom-6 sm:right-6 sm:w-[380px] sm:rounded-2xl ${regenMessages.length > 0 ? "inset-0 rounded-none" : "inset-x-0 bottom-0 rounded-t-2xl max-h-[60vh]"}`} style={{ backgroundColor: "var(--bg)" }}>

              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: "1px solid var(--border)" }}>
                <div className="flex items-center gap-2">
                  <div
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                    style={{ backgroundColor: "var(--kb)" }}
                  >
                    KI
                  </div>
                  <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>KI-Assistent · Folie {regeneratingSlide + 1}</span>
                </div>
                <button onClick={closeRegen} className="w-7 h-7 flex items-center justify-center rounded-full hover:opacity-70 transition-opacity" style={{ backgroundColor: "var(--border)", color: "var(--muted)" }}>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              {/* Chat area */}
              <div ref={regenChatAreaRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-4 min-h-0">

                {/* Markierung als Kontext-Chip oben */}
                {regenAnchorText && (
                  <div className="flex justify-center">
                    <div className="w-full rounded-xl px-3 py-1.5 text-xs italic" style={{ backgroundColor: "rgba(var(--kb-rgb),0.06)", color: "var(--text)", border: "1px solid var(--border)" }}>
                      <span style={{ color: "var(--kb)" }}>✦</span> „{regenAnchorText}"
                    </div>
                  </div>
                )}

                {/* Chatverlauf */}
                {regenMessages.map((msg, idx) => {
                  const isUser = msg.role === "user";
                  const isLastAssistant = !isUser && idx === regenMessages.length - 1;
                  return (
                    <div key={idx} className={`flex flex-col gap-1.5 ${isUser ? "items-end" : "items-start"}`}>
                      {!isUser && (
                        <div className="flex items-center gap-2 mb-0.5">
                          <div
                            className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                            style={{ backgroundColor: "var(--kb)" }}
                          >
                            KI
                          </div>
                          <span className="text-[11px] font-medium" style={{ color: "var(--muted)" }}>
                            KI-Assistent
                          </span>
                        </div>
                      )}
                      <div className={`${isUser ? "max-w-[85%]" : "max-w-[96%]"} space-y-2 ${isUser ? "items-end" : "items-start"} flex flex-col`}>
                        {isUser ? (
                          <div className="text-sm px-4 py-3 rounded-2xl leading-relaxed" style={{ backgroundColor: "var(--kb)", color: "white", borderBottomRightRadius: 6, whiteSpace: "pre-wrap" }}>
                            {msg.content}
                          </div>
                        ) : (
                          <>
                            <RegenTextarea
                              value={msg.content}
                              onChange={(v) => setRegenMessages(regenMessages.map((m, i) => i === idx ? { ...m, content: v } : m))}
                              className="text-sm rounded-2xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary/30 resize-none leading-relaxed w-full overflow-y-auto"
                              style={{ backgroundColor: "var(--surface)", color: "var(--text)", border: "1px solid var(--border)", borderTopLeftRadius: 6 }}
                            />
                            {isLastAssistant && (
                              <div className="flex flex-wrap gap-1.5">
                                {regenAnchorText ? (
                                  <>
                                    <button onClick={() => applyRegen(regeneratingSlide, "replace-selection", msg.content)} className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity" style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}>Markierung ersetzen</button>
                                    <button onClick={() => applyRegen(regeneratingSlide, "insert-before", msg.content)} className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity" style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}>Davor</button>
                                    <button onClick={() => applyRegen(regeneratingSlide, "insert-after", msg.content)} className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity" style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}>Danach</button>
                                    <button onClick={() => applyRegen(regeneratingSlide, "replace-all", msg.content)} className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity" style={{ backgroundColor: "rgba(var(--kb-rgb),0.05)", color: "var(--muted)" }}>Ganzes Skript</button>
                                  </>
                                ) : (
                                  <button onClick={() => applyRegen(regeneratingSlide, "replace-all", msg.content)} className="px-3 py-1 text-xs font-medium rounded-full hover:opacity-80 transition-opacity" style={{ backgroundColor: "rgba(var(--kb-rgb),0.08)", color: "var(--kb)" }}>Ersetzen</button>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}

                {/* Typing indicator */}
                {regenLoading && (
                  <div className="flex items-start gap-2">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                      style={{ backgroundColor: "var(--kb)" }}
                    >
                      KI
                    </div>
                    <div className="px-4 py-3 rounded-2xl text-sm" style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)", borderTopLeftRadius: 6 }}>
                      <span className="inline-flex items-center gap-2">
                        <span className="inline-flex gap-1">
                          {[0, 1, 2].map((n) => (
                            <span
                              key={n}
                              className="inline-block w-1.5 h-1.5 rounded-full animate-bounce"
                              style={{ backgroundColor: "var(--muted)", animationDelay: `${n * 0.15}s` }}
                            />
                          ))}
                        </span>
                        <span className="text-xs" style={{ color: "var(--muted)" }}>Denkt nach…</span>
                      </span>
                    </div>
                  </div>
                )}

                <div ref={regenChatBottomRef} />
              </div>

              {/* Input area */}
              <div className="px-4 pt-4 pb-3" style={{ borderTop: "1px solid var(--border)" }}>
                <div
                  className="flex items-center gap-2 rounded-2xl px-4 py-3"
                  style={{ backgroundColor: "var(--surface)", border: "1px solid var(--border)" }}
                >
                  <textarea
                    value={regenPrompt}
                    onChange={(e) => setRegenPrompt(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!regenLoading) runRegen(regeneratingSlide); }}}
                    rows={1}
                    placeholder="Text eingeben…"
                    autoFocus
                    className="flex-1 text-sm resize-none focus:outline-none disabled:opacity-50 bg-transparent"
                    style={{ color: "var(--text)", maxHeight: 160, overflowY: "auto" }}
                  />
                  <button
                    onClick={() => runRegen(regeneratingSlide)}
                    disabled={regenLoading}
                    className="flex-shrink-0 w-9 h-9 flex items-center justify-center rounded-xl text-white disabled:opacity-40 transition-opacity hover:opacity-85"
                    style={{ backgroundColor: "var(--kb)" }}
                  >
                    {regenLoading ? (
                      <Spinner size="sm" color="current" />
                    ) : (
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </ProtectedRoute>
  );
}

export default function ScreencastPage() {
  return (
    <Suspense>
      <ScreencastPageInner />
    </Suspense>
  );
}
