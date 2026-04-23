"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Header from "@/components/layout/Header";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { useGlossaries } from "@/hooks/useGlossaries";
import { api, pollJob, downloadJobAsBlob, parseDetail, type JobStatus } from "@/lib/api";
import { checkAuthStatus } from "@/lib/auth";
import BackLink from "@/components/ui/BackLink";
import Spinner from "@/components/ui/Spinner";
import type {
  ScreencastState,
  ScreencastStep,
  SlideData,
} from "@/types";
import ScreencastStepper from "@/components/screencast/ScreencastStepper";
import { stepToIndex } from "@/components/screencast/steps";
import UploadStep from "./_steps/UploadStep";
import {
  TranslatingStep,
  GeneratingScriptsStep,
  RenderingStep,
  DoneStep,
  ErrorStep,
} from "./_steps/StatusSteps";
import UserPromptStep from "./_steps/UserPromptStep";
import TranslationReviewStep from "./_steps/TranslationReviewStep";
import ScriptReviewStep from "./_steps/ScriptReviewStep";
import TtsSettingsStep from "./_steps/TtsSettingsStep";
import Lightbox from "./_components/Lightbox";
import RegenChatModal, { type RegenApplyMode } from "./_components/RegenChatModal";
import { wordCount, estimateDuration } from "@/lib/text";
import { KOKORO_ACCENT_LABEL } from "@/lib/voice-labels";
import { useFileDropzone } from "@/hooks/useFileDropzone";
import { useVoices } from "@/hooks/useVoices";
import { useScriptEditing, useScriptAutosave } from "@/hooks/useScriptEditing";

const ACCEPTED_EXTENSIONS = [".pptx"];

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
  const {
    file,
    fileError,
    dragOver,
    selectFile: handleFileSelect,
    onDragOver: handleDragOver,
    onDragLeave: handleDragLeave,
    onDrop: handleDrop,
    reset: resetFile,
  } = useFileDropzone({ acceptedExtensions: ACCEPTED_EXTENSIONS });
  const [speed, setSpeed] = useState(1.0);
  const [slidePause, setSlidePause] = useState<number>(0.5);
  const [dpi, setDpi] = useState(144);
  // Per-slide AI regeneration state (modal-intern state lebt in RegenChatModal)
  const [regeneratingSlide, setRegeneratingSlide] = useState<number | null>(null);
  const [regenAnchorText, setRegenAnchorText] = useState("");
  const [regenAnchorSlide, setRegenAnchorSlide] = useState<number | null>(null);

  useEffect(() => {
    const handler = () => {
      if (regeneratingSlide !== null) return;
      if (!window.getSelection()?.toString().trim()) {
        setRegenAnchorText("");
        setRegenAnchorSlide(null);
      }
    };
    document.addEventListener("selectionchange", handler);
    return () => document.removeEventListener("selectionchange", handler);
  }, [regeneratingSlide]);


  const [glossaryIds, setGlossaryIds] = useState<string[]>(["", "", ""]);
  const [slides, setSlides] = useState<SlideData[]>([]);
  const [translateJobUuid, setTranslateJobUuid] = useState("");
  const [downloadBlob, setDownloadBlob] = useState<Blob | null>(null);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [correctedFileName, setCorrectedFileName] = useState<string | null>(null);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);

  const autosaveScripts = useScriptAutosave({ jobUuid: translateJobUuid });
  const {
    openAccordion,
    editingSlide,
    editBuffer,
    setEditBuffer,
    startEdit: startEditHook,
    cancelEdit,
    saveEdit,
    toggleAccordion,
    reset: resetScriptEditing,
  } = useScriptEditing({
    onSave: (index, newScript) => {
      const updated = slides.map((s, i) => (i === index ? { ...s, script: newScript } : s));
      setSlides(updated);
      autosaveScripts(updated.map((s) => s.script));
    },
  });
  const startEdit = (index: number) => startEditHook(index, slides[index]?.script ?? "");

  const voicesResult = useVoices();
  const {
    loaded: providersLoaded,
    providers,
    defaultProvider,
    defaultVoiceId,
    elevenlabs: voices,
    kokoro: kokoroVoices,
    mylab: mylabVoices,
    thorsten: thorstenVoices,
  } = voicesResult;
  const elevenlabsEnabled = providers.elevenlabs;
  const fishSpeechEnabled = providers.fish_speech;
  const kokoroEnabled = providers.kokoro;
  const mylabEnabled = providers.mylab;
  const thorstenEnabled = providers.thorsten;
  const [voiceId, setVoiceId] = useState("");
  const [ttsProvider, setTtsProvider] = useState<"elevenlabs" | "fish_speech" | "kokoro" | "mylab" | "thorsten">("kokoro");
  useEffect(() => {
    if (defaultProvider) setTtsProvider(defaultProvider);
  }, [defaultProvider]);
  useEffect(() => {
    if (defaultVoiceId && !voiceId) setVoiceId(defaultVoiceId);
  }, [defaultVoiceId, voiceId]);
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
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentJobUuidRef = useRef<string | null>(null);
  const isGeneratingScriptsRef = useRef(false);

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
    resetFile();
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
    resetScriptEditing();
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

  const openRegen = (index: number) => setRegeneratingSlide(index);

  const closeRegen = () => {
    setRegeneratingSlide(null);
    setRegenAnchorText("");
    setRegenAnchorSlide(null);
  };

  const applyRegen = (index: number, mode: RegenApplyMode, content: string) => {
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

  // ── Track max reached step ──
  useEffect(() => {
    const idx = stepToIndex(step);
    setMaxReachedIdx((prev) => Math.max(prev, idx));
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
            <ScreencastStepper
              step={step}
              maxReachedIdx={maxReachedIdx}
              sourceLang={sourceLang}
              onStepClick={handleStepClick}
            />
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
          <UploadStep
            showDemoLink={showDemoLink}
            hasActiveJob={hasActiveJob}
            file={file}
            fileError={fileError}
            dragOver={dragOver}
            autoState={autoState}
            mode={mode}
            isAdmin={isAdmin}
            fastMode={fastMode}
            sourceLang={sourceLang}
            targetLang={targetLang}
            languages={languages}
            glossaryIds={glossaryIds}
            isAutoMode={isAutoMode}
            autoDownloadName={autoDownloadName}
            autoError={autoError}
            renderProgressLabel={renderProgressLabel}
            failedRenderJobUuid={failedRenderJobUuid}
            audioId={audioId}
            fileRef={fileRef}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onFileSelect={handleFileSelect}
            onSourceLangChange={setSourceLang}
            onTargetLangChange={setTargetLang}
            onGlossaryIdsChange={setGlossaryIds}
            onModeChange={setMode}
            onFastModeChange={setFastMode}
            onUploadNext={handleUploadNext}
            onAutoDownload={handleAutoDownload}
            onReset={resetAll}
            onRetryRender={failedRenderJobUuid ? handleRetryRender : undefined}
            onZipDownload={handleAutoZipDownload}
          />
        )}

        {/* ── Step: Translating (loading) ── */}
        {!resumeLoading && step === "translating" && (
          <TranslatingStep
            sourceLang={sourceLang}
            targetLang={targetLang}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}`, { method: "DELETE", credentials: "include" }).catch(() => {});
                window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
              }
              setStep("upload");
              setLoading(false);
            }}
          />
        )}

        {/* ── Step: User Prompt ── */}
        {!resumeLoading && step === "user-prompt" && (
          <UserPromptStep
            scriptInputMode={scriptInputMode}
            importedScripts={importedScripts}
            importError={importError}
            jsonDragOver={jsonDragOver}
            jsonFileRef={jsonFileRef}
            loading={loading}
            onScriptInputModeChange={setScriptInputMode}
            onResetImport={() => {
              setImportedScripts(null);
              setImportError(null);
            }}
            onJsonDragOverChange={setJsonDragOver}
            onJsonImport={handleJsonImport}
            onNext={() => {
              if (scriptInputMode === "manual") {
                setSlides((prev) => prev.map((s) => ({ ...s, script: "" })));
                setStep("script-review");
              } else if (scriptInputMode === "import") {
                if (!importedScripts) {
                  setImportError("Bitte zuerst eine JSON-Datei auswählen.");
                  return;
                }
                setSlides((prev) => prev.map((s, i) => ({ ...s, script: importedScripts[i] ?? "" })));
                setStep("script-review");
              } else {
                handleAcceptTranslation();
              }
            }}
          />
        )}

        {/* ── Step: Translation Review ── */}
        {!resumeLoading && step === "translation-review" && (
          <TranslationReviewStep
            slides={slides}
            fastMode={fastMode}
            loading={loading}
            correctedFileName={correctedFileName}
            onLightboxOpen={setLightboxIndex}
            onDownloadTranslatedPptx={handleDownloadTranslatedPptx}
            onUploadCorrectedPptx={handleUploadCorrectedPptx}
            onAcceptAndNext={() => {
              setMaxReachedIdx((v) => Math.max(v, 3));
              setStep("user-prompt");
            }}
          />
        )}

        {/* ── Step: Generating Scripts (loading) ── */}
        {!resumeLoading && step === "generating-scripts" && (
          <GeneratingScriptsStep
            slideCount={slides.length}
            onCancel={() => {
              const uuid = currentJobUuidRef.current;
              currentJobUuidRef.current = null;
              abortControllerRef.current?.abort();
              if (uuid) {
                fetch(`/api/jobs/${uuid}/cancel`, { method: "POST", credentials: "include" }).catch(() => {});
                window.dispatchEvent(new CustomEvent("kis-jobs-changed"));
              }
              setStep("translation-review");
              setLoading(false);
            }}
          />
        )}

        {/* ── Step: Script Review ── */}
        {!resumeLoading && step === "script-review" && (
          <ScriptReviewStep
            slides={slides}
            openAccordion={openAccordion}
            editingSlide={editingSlide}
            editBuffer={editBuffer}
            fastMode={fastMode}
            regenAnchorSlide={regenAnchorSlide}
            regenAnchorText={regenAnchorText}
            onEditBufferChange={setEditBuffer}
            onLightboxOpen={setLightboxIndex}
            onAccordionToggle={toggleAccordion}
            onRegenAnchor={(slide, text) => {
              setRegenAnchorSlide(slide);
              setRegenAnchorText(text);
            }}
            onOpenRegen={openRegen}
            onStartEdit={startEdit}
            onCancelEdit={cancelEdit}
            onSaveEdit={saveEdit}
            onAcceptScripts={handleAcceptScripts}
          />
        )}

        {/* ── Step: TTS Settings ── */}
        {!resumeLoading && step === "tts-settings" && (
          <TtsSettingsStep
            providersLoaded={providersLoaded}
            elevenlabsEnabled={elevenlabsEnabled}
            fishSpeechEnabled={fishSpeechEnabled}
            kokoroEnabled={kokoroEnabled}
            mylabEnabled={mylabEnabled}
            thorstenEnabled={thorstenEnabled}
            ttsProvider={ttsProvider}
            voices={voices}
            kokoroVoices={kokoroVoices}
            mylabVoices={mylabVoices}
            thorstenVoices={thorstenVoices}
            voiceId={voiceId}
            speed={speed}
            slidePause={slidePause}
            dpi={dpi}
            slides={slides}
            totalWords={totalWords}
            totalChars={totalChars}
            scriptOverLimit={scriptOverLimit}
            maxChars={SCREENCAST_MAX_CHARS}
            ttsSettingsError={ttsSettingsError}
            onTtsProviderChange={setTtsProvider}
            onVoiceIdChange={setVoiceId}
            onSpeedChange={setSpeed}
            onSlidePauseChange={setSlidePause}
            onDpiChange={setDpi}
            onBackToScripts={handleBackToScripts}
            onStartRender={handleStartRender}
          />
        )}

        {/* ── Step: Rendering (loading) ── */}
        {!resumeLoading && step === "rendering" && (
          <RenderingStep
            renderProgressLabel={renderProgressLabel}
            onCancel={async () => {
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
          />
        )}

        {/* ── Step: Done ── */}
        {!resumeLoading && step === "done" && (
          <DoneStep
            videoUrl={videoUrl}
            audioId={audioId}
            onDownloadMp4={handleDownload}
            onReset={() => resetAll(false)}
          />
        )}

        {/* ── Error state ── */}
        {!resumeLoading && step === "error" && (
          <ErrorStep
            errorMessage={errorMessage}
            failedRenderJobUuid={failedRenderJobUuid}
            onRetry={handleRetryRender}
            onReset={() => resetAll()}
          />
        )}
        {!fastMode && lightboxIndex !== null && (
          <Lightbox
            index={lightboxIndex}
            slides={slides}
            onClose={() => setLightboxIndex(null)}
            onIndexChange={setLightboxIndex}
          />
        )}


        {regeneratingSlide !== null && slides[regeneratingSlide] && (
          <RegenChatModal
            slideIndex={regeneratingSlide}
            slideExtractedText={slides[regeneratingSlide].extractedText}
            currentScript={slides[regeneratingSlide].script || ""}
            anchorText={regenAnchorText}
            targetLang={targetLang}
            onApply={(mode, content) => applyRegen(regeneratingSlide, mode, content)}
            onClose={closeRegen}
          />
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
