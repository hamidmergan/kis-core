"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Files, Info } from "@phosphor-icons/react";
import { useLocale, useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ErgebnisInfoKnopf, ErgebnisLoeschenKnopf, useErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Modal from "@/components/ui/Modal";
import ToolBackLink from "@/components/ui/ToolBackLink";
import StatusMark from "@/components/ui/StatusMark";
import JobHistoryTable from "@/components/jobs/JobHistoryTable";
import { Link } from "@/i18n/navigation";
import { backendApi, pollJob, downloadJobAsBlob, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_MB, MAX_UPLOAD_BYTES } from "@/lib/constants";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import Tabs from "@/components/ui/Tabs";
import Checkbox from "@/components/ui/Checkbox";
import { EmptyState } from "@/components/ui/EmptyState";
import BackgroundHint from "@/components/tools/BackgroundHint";
import ProviderSelect from "@/components/tools/ProviderSelect";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { usePermissions } from "@/hooks/usePermissions";
import { useModules } from "@/hooks/useModules";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { demoSchritte, warte, type DemoSetup } from "../_demo";
import { useSummaryHistory } from "./useSummaryHistory";

type Template = { slug: string; nameDe: string; nameEn: string; hintDe: string; hintEn: string };
type Setup = { templates: Template[]; maxSources: number; extensions: string[] };
type Progress = { step?: string; part?: number; total?: number } | null;
type SourceMode = "files" | "module";

const FALLBACK_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md", ".srt", ".vtt"];
const KEINE_DATEIEN: File[] = [];
// Milliseconds each line of the simulated demo run stays up.
const DEMO_SCHRITT_MS = 400;
const DEMO_BADGE = "text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent";
const DEMO_FARBE = { backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" };

function herunterladen(href: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = "";
  a.click();
}

/** The summary tool, and with demo the same page on the prepared runs of the demo module. */
function ZusammenfassungSeiteInner({ demo = false }: { demo?: boolean }) {
  const t = useTranslations("tools.summarize");
  const tDemo = useTranslations("tools.summarizeDemo");
  const tCommon = useTranslations("common");
  const tResult = useTranslations("common.result");
  const locale = useLocale();
  // Runs on the chat model, an empty list hides the choice.
  const { providers, providerId, setProviderId } = useFeatureProviders("/summary/providers");
  const [setup, setSetup] = useState<Setup | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  // Whoever has no assistant sees no workspace tab, so the choice cannot get stuck.
  const { permissions } = usePermissions();
  const [gewaehlterModus, setModus] = useState<SourceMode>("files");
  const [moduleId, setModuleId] = useState("");
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [template, setTemplate] = useState("");
  const [instructions, setInstructions] = useState("");
  const [processing, setProcessing] = useState(false);
  const [step, setStep] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [doneJobUuid, setDoneJobUuid] = useState<string | null>(null);
  const auftrag = useErgebnisAngaben(demo ? null : doneJobUuid);
  const [errorMessage, setErrorMessage] = useState("");
  // Read straight on the page once a run is done, the downloads stay as a second way to get it.
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [materialienOffen, setMaterialienOffen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // The prepared runs, also read outside the demo so the badge only shows when there is one.
  const [demoSetup, setDemoSetup] = useState<DemoSetup | null>(null);
  const demoLauf = useRef<AbortController | null>(null);

  const extensions = setup?.extensions ?? FALLBACK_EXTENSIONS;
  const maxSources = setup?.maxSources ?? 10;
  // The demo offers only the templates that have a prepared result.
  const templates = (setup?.templates ?? []).filter((v) => !demo || demoSetup?.templates.includes(v.slug));
  const templateName = (v: Template) => (locale === "de" ? v.nameDe : v.nameEn);
  const templateHint = (v: Template) => (locale === "de" ? v.hintDe : v.hintEn);
  const chosen = templates.find((v) => v.slug === template);
  const canUseModules = !!permissions.allow_aia;
  // Whoever loses the assistant must not stay stuck in a tab that is gone.
  const mode: SourceMode = demo ? "module" : canUseModules ? gewaehlterModus : "files";
  const { modules, sources } = useModules(mode === "module" && !demo ? moduleId : "");
  const messung = useMaterialMeasure("summary", demo ? "files" : mode, demo ? KEINE_DATEIEN : files, moduleId, sourceIds);
  // The real history makes no sense on the demo page, which never creates a job.
  const verlauf = useSummaryHistory();
  // Only the jobs list links straight to one summary.
  const ausListe = useSearchParams().get("job");
  const voll = sourceIds.length >= maxSources;
  const hatInhalt = demo ? templates.length > 0 : mode === "files" ? files.length > 0 : sourceIds.length > 0;
  const bereit = demo || messung.ready;

  useEffect(() => {
    backendApi.fetch("/summary/templates")
      .then(async (r) => {
        if (!r.ok) return;
        const data = (await r.json()) as Setup;
        setSetup(data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    backendApi.fetch("/summary-demo/setup")
      .then(async (r) => {
        if (!r.ok) return;
        const data = (await r.json()) as DemoSetup;
        setDemoSetup(data);
        if (demo) setInstructions(data.instructions);
      })
      .catch(() => {});
    return () => demoLauf.current?.abort();
  }, [demo]);

  // Arriving from the jobs list: open straight on that one result.
  useEffect(() => {
    if (demo || !ausListe) return;
    setDoneJobUuid(ausListe);
    setErrorMessage("");
  }, [demo, ausListe]);

  // The first template that may be picked, in the demo only once its prepared runs are known.
  useEffect(() => {
    if (templates[0] && !templates.some((v) => v.slug === template)) setTemplate(templates[0].slug);
  }, [templates, template]);

  // Nothing is preselected, a source that is gone drops out of the choice.
  useEffect(() => {
    if (!sources) return;
    const vorhanden = new Set(sources.map((q) => q.uuid));
    setSourceIds((alt) => (alt.every((id) => vorhanden.has(id)) ? alt : alt.filter((id) => vorhanden.has(id))));
  }, [sources]);

  // The finished text, fetched once so the result reads straight on the page.
  useEffect(() => {
    if (!doneJobUuid) { setPreviewText(null); return; }
    let abgelaufen = false;
    (async () => {
      try {
        const text = demo
          ? await (await backendApi.fetch(`/summary-demo/${doneJobUuid}/md`)).text()
          : await (await downloadJobAsBlob(doneJobUuid)).blob.text();
        if (!abgelaufen) setPreviewText(text);
      } catch {
        // The downloads below still work even when the preview fetch fails.
      }
    })();
    return () => { abgelaufen = true; };
  }, [doneJobUuid, demo]);

  const waehleWorkspace = (uuid: string) => {
    setModuleId(uuid);
    setSourceIds([]);
    setDoneJobUuid(null);
    setErrorMessage("");
  };

  const schalteQuelle = (uuid: string) => {
    setDoneJobUuid(null);
    setErrorMessage("");
    setSourceIds((alt) => {
      if (alt.includes(uuid)) return alt.filter((id) => id !== uuid);
      return alt.length >= maxSources ? alt : [...alt, uuid];
    });
  };

  const validateFile = useCallback((file: File): string | null => {
    const ext = "." + (file.name.split(".").pop()?.toLowerCase() ?? "");
    if (!extensions.includes(ext)) {
      return tCommon("onlyExtsAllowed", { exts: extensions.join(", ") });
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return tCommon("fileTooLarge", { n: MAX_UPLOAD_MB });
    }
    return null;
  }, [extensions, tCommon]);

  const addFiles = useCallback((neue: File[]) => {
    setUploadError(null);
    setDoneJobUuid(null);
    setErrorMessage("");
    setFiles((alt) => {
      const gesamt = [...alt];
      for (const f of neue) {
        const err = validateFile(f);
        if (err) { setUploadError(err); continue; }
        if (gesamt.length >= maxSources) {
          setUploadError(t("tooManySources", { max: maxSources }));
          break;
        }
        if (!gesamt.some((g) => g.name === f.name && g.size === f.size)) gesamt.push(f);
      }
      return gesamt;
    });
  }, [validateFile, maxSources, t]);

  const removeFile = (index: number) => setFiles((alt) => alt.filter((_, i) => i !== index));

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      if (processing) return;
      addFiles(Array.from(e.dataTransfer.files));
    },
    [processing, addFiles],
  );

  // The steps of a real run with their numbers, then the prepared result of the chosen template.
  const demoStarten = async () => {
    if (!demoSetup) return;
    const ctrl = new AbortController();
    demoLauf.current = ctrl;
    setProcessing(true);
    setErrorMessage("");
    setDoneJobUuid(null);
    try {
      for (const s of demoSchritte(demoSetup.files.length, demoSetup.sections[template] ?? 1)) {
        setStep(s.part ? t(`step.${s.step}Counted`, { part: s.part, total: s.total ?? s.part }) : t(`step.${s.step}`));
        await warte(DEMO_SCHRITT_MS, ctrl.signal);
      }
      // In the demo the finished run is the template whose prepared result it hands out.
      setDoneJobUuid(template);
    } catch {
      return;
    } finally {
      setProcessing(false);
      setStep("");
    }
  };

  const handleSubmit = async () => {
    if (demo) return demoStarten();
    if (!hatInhalt || !messung.ready || processing) return;
    setProcessing(true);
    setErrorMessage("");
    setDoneJobUuid(null);
    setStep(t("step.extract"));
    try {
      const formData = new FormData();
      formData.append("mode", mode);
      if (mode === "files") files.forEach((f) => formData.append("files", f));
      if (mode === "module") {
        formData.append("workspace_uuid", moduleId);
        formData.append("source_uuids", JSON.stringify(sourceIds));
      }
      if (template) formData.append("template", template);
      if (providerId != null) formData.append("provider_id", String(providerId));
      if (instructions.trim()) formData.append("instructions", instructions.trim());
      const response = await backendApi.fetch("/summary", { method: "POST", body: formData });
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      const data = await response.json();
      window.dispatchEvent(new Event("kis-jobs-changed"));
      await pollJob(
        data.job_uuid,
        (status) => {
          const p = status.progress as Progress;
          // A step the page does not know keeps the last line instead of breaking the page.
          if (!p?.step || !t.has(`step.${p.step}`)) return;
          // Zero done files reads as the plain sentence, never as "0 von 1".
          setStep(typeof p.part === "number" && typeof p.total === "number" && p.part > 0
            ? t(`step.${p.step}Counted`, { part: p.part, total: p.total })
            : t(`step.${p.step}`));
        },
        3000,
      );
      window.dispatchEvent(new Event("kis-jobs-changed"));
      setDoneJobUuid(data.job_uuid);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setProcessing(false);
      setStep("");
    }
  };

  const handleDownload = async () => {
    if (!doneJobUuid) return;
    if (demo) return herunterladen(`/api/summary-demo/${doneJobUuid}/md`);
    try {
      const { blob, filename } = await downloadJobAsBlob(doneJobUuid);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("downloadFailed"));
    }
  };

  const handleDownloadDocx = async () => {
    if (!doneJobUuid) return;
    if (demo) return herunterladen(`/api/summary-demo/${doneJobUuid}/docx`);
    try {
      const { blob, filename } = await downloadJobAsBlob(doneJobUuid, "zusammenfassung.docx", "docx");
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("downloadFailed"));
    }
  };

  const handleReset = () => {
    setFiles([]);
    setSourceIds([]);
    setDoneJobUuid(null);
    setPreviewText(null);
    setErrorMessage("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const full = files.length >= maxSources;

  // The source names of the shown result: the job's own list once it is history, the current choice while it is fresh.
  const materialien = (() => {
    const eintrag = verlauf.find((v) => v.job_uuid === doneJobUuid);
    if (eintrag) return eintrag.original_filename.split(",").map((n) => n.trim()).filter(Boolean);
    if (demo) return demoSetup?.files ?? [];
    if (mode === "files") return files.map((f) => f.name);
    if (sources) return sources.filter((s) => sourceIds.includes(s.uuid)).map((s) => s.filename);
    return [];
  })();

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <ToolBackLink />
        <div className="flex items-baseline justify-between gap-3 mb-1">
          <h1 className="text-xl font-bold">{t("title")}</h1>
          {demo ? (
            <span className={DEMO_BADGE} style={DEMO_FARBE}>{tDemo("demoBadge")}</span>
          ) : !!demoSetup?.templates.length && (
            <Link href="/tools/summarize-demo" className={`${DEMO_BADGE} hover:border-black transition-colors`} style={DEMO_FARBE}>
              {t("demoBadge")}
            </Link>
          )}
        </div>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>
        {demo && (
          <p className="mb-6 flex items-start gap-2 rounded-lg bg-surface-dim px-3 py-2.5 text-sm text-foreground-soft">
            <Info size={14} className="mt-0.5 flex-shrink-0 text-muted-soft" aria-hidden="true" />
            {tDemo("hinweis")}
          </p>
        )}

        {/* Where the material comes from, above both columns like the tabs of the image tool. */}
        {(canUseModules || demo) && (
          <Tabs<SourceMode>
            className="mb-6"
            active={mode}
            onChange={(next) => { setModus(next); setUploadError(null); setErrorMessage(""); }}
            items={[
              { key: "files", label: t("tabs.files"), disabled: demo },
              { key: "module", label: "Workspace" },
            ]}
          />
        )}

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]" data-tour="tool-summary">
        <section className="min-w-0 rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
          {templates.length > 0 && (
            <div>
              <label htmlFor="summary-template-select" className="block text-sm font-medium text-foreground mb-1">
                {t("templateLabel")}
              </label>
              <Select
                id="summary-template-select"
                value={template}
                onChange={setTemplate}
                disabled={processing}
                options={templates.map((v) => ({ value: v.slug, label: templateName(v) }))}
              />
              {chosen && <p className="mt-1 text-xs text-muted">{templateHint(chosen)}</p>}
            </div>
          )}

          <div className="mt-6">
            <label htmlFor="summary-instructions" className="block text-sm font-medium text-foreground mb-1">
              {t("instructionsLabel")}
            </label>
            <textarea
              id="summary-instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              disabled={processing}
              readOnly={demo}
              rows={3}
              placeholder={t("instructionsPlaceholder")}
              className="w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft resize-y"
            />
          </div>

          <ProviderSelect
            id="summary-provider-select"
            label={t("providerLabel")}
            providers={providers}
            value={providerId}
            onChange={setProviderId}
            disabled={processing}
            className="mt-6"
            showModel
          />

          {!doneJobUuid && (
            <div className="mt-6">
              <button
                onClick={handleSubmit}
                disabled={!hatInhalt || !bereit || processing}
                className="self-start px-5 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {processing && <Spinner size="sm" color="current" />}
                {processing ? tCommon("processing") : t("submit")}
              </button>
            </div>
          )}

          {errorMessage && (
            <p className="mt-3 text-sm text-error" role="alert">{errorMessage}</p>
          )}
        </section>

        {/* The material on the right, the result takes its place once it is there. On the phone the material leads. */}
        <section className="min-w-0 order-first lg:order-none lg:col-start-2 lg:row-start-1">
          <div className="rounded-xl border border-kb/15 bg-kb/5 p-4 sm:p-5" aria-live="polite">
            {processing ? (
              <div className="flex flex-col items-center justify-center gap-3 py-14 text-center">
                <Spinner label={step || tCommon("processing")} />
                {!demo && <BackgroundHint />}
              </div>
            ) : doneJobUuid ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <StatusMark tone="success" className="text-sm font-medium">{tCommon("downloadReady")}</StatusMark>
                  <span className="flex items-center gap-2">
                  {materialien.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setMaterialienOffen(true)}
                      aria-label={t("materialsAria")}
                      title={t("materialsAria")}
                      className="text-muted-soft hover:text-foreground transition-colors"
                    >
                      <Files size={16} weight="bold" />
                    </button>
                  )}
                  {!demo && (
                    <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
                      { label: tResult("provider"), wert: auftrag?.angaben.anbieter },
                      { label: t("templateLabel"), wert: (() => {
                        const v = templates.find((x) => x.slug === auftrag?.angaben.vorlage);
                        return v ? templateName(v) : auftrag?.angaben.vorlage;
                      })() },
                    ]} />
                  )}
                  </span>
                </div>
                <div className="rounded-md border border-border-soft bg-background p-4 sm:p-5 max-h-[28rem] overflow-y-auto text-sm leading-relaxed text-foreground">
                  {previewText ? (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({ children }) => <h1 className="text-lg font-bold mb-3">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-base font-semibold mt-5 mb-2 first:mt-0">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-sm font-semibold mt-4 mb-1.5 first:mt-0">{children}</h3>,
                        p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        table: ({ children }) => <div className="overflow-x-auto my-3"><table className="w-full text-sm border-collapse">{children}</table></div>,
                        th: ({ children }) => <th className="text-left px-2 py-1 font-semibold border-b border-border-soft">{children}</th>,
                        td: ({ children }) => <td className="px-2 py-1 border-t border-border-soft">{children}</td>,
                      }}
                    >
                      {previewText}
                    </ReactMarkdown>
                  ) : (
                    <Spinner className="justify-center py-6" />
                  )}
                </div>
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={handleDownload}
                    className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
                  >
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t("downloadLabel")}
                  </button>
                  <button
                    onClick={handleDownloadDocx}
                    className="px-4 py-2 btn-primary text-sm rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors flex items-center gap-2"
                  >
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    {t("downloadDocxLabel")}
                  </button>
                  <button
                    onClick={handleReset}
                    className="px-4 py-2 text-sm text-foreground-soft border border-border rounded-md btn-ghost focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors"
                  >
                    {t("newSummary")}
                  </button>
                  {!demo && <ErgebnisLoeschenKnopf jobUuid={doneJobUuid} auftrag={auftrag} onGeloescht={handleReset} />}
                </div>
              </div>
            ) : (
              <>
              {demo && (
                !demoSetup ? (
                  <Spinner className="justify-center py-10" />
                ) : templates.length === 0 && setup ? (
                  <EmptyState text={tDemo("keinErgebnis")} />
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="summary-module" className="block text-sm font-medium text-foreground mb-1">
                        Workspace
                      </label>
                      <Select
                        id="summary-module"
                        value="demo"
                        onChange={() => {}}
                        disabled
                        options={[{ value: "demo", label: demoSetup.workspace }]}
                      />
                    </div>
                    <div>
                      <span className="block text-sm font-medium text-foreground mb-2">{t("chosenFiles")}</span>
                      <ul className="space-y-2">
                        {demoSetup.files.map((name) => (
                          <li key={name}>
                            <Checkbox checked disabled onChange={() => {}} label={name} labelClassName="text-sm text-foreground" />
                          </li>
                        ))}
                      </ul>
                      <p className="mt-2 text-xs text-muted">{tDemo("materialVorgegeben")}</p>
                    </div>
                  </div>
                )
              )}

              {mode === "module" && !demo && (
                modules === null ? (
                  <Spinner className="justify-center py-10" />
                ) : modules.length === 0 ? (
                  <EmptyState text={t("noModules")} />
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="summary-module" className="block text-sm font-medium text-foreground mb-1">
                        Workspace
                      </label>
                      <Select
                        id="summary-module"
                        value={moduleId}
                        onChange={waehleWorkspace}
                        disabled={processing}
                        placeholder={tCommon("pleaseSelect")}
                        options={modules.map((m) => ({ value: m.uuid, label: m.title }))}
                      />
                    </div>
                    {moduleId &&
                      (sources === null ? (
                        <Spinner className="justify-center py-6" />
                      ) : sources.length === 0 ? (
                        <EmptyState size="sm" text={t("noSources")} />
                      ) : (
                        <div>
                          {sourceIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
                          <span className="block text-sm font-medium text-foreground mb-2">{t("chosenFiles")}</span>
                          <ul className="space-y-2">
                            {sources.map((q) => (
                              <li key={q.uuid}>
                                <div className="flex items-center justify-between gap-3">
                                  <Checkbox
                                    checked={sourceIds.includes(q.uuid)}
                                    disabled={processing || (voll && !sourceIds.includes(q.uuid))}
                                    onChange={() => schalteQuelle(q.uuid)}
                                    label={q.filename}
                                    labelClassName="text-sm text-foreground"
                                  />
                                  {sourceIds.includes(q.uuid) && <MeasureNote messung={messung.forSource(q.uuid)} />}
                                </div>
                                {sourceIds.includes(q.uuid) && <MeasureError messung={messung.forSource(q.uuid)} />}
                              </li>
                            ))}
                          </ul>
                          <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>
                            {t("tooManySources", { max: maxSources })}
                          </p>
                        </div>
                      ))}
                  </div>
                )
              )}

              {mode === "files" && (
              <>
              <div
                role="button"
                tabIndex={0}
                aria-label={t("selectFileAria")}
                onClick={() => !processing && !full && inputRef.current?.click()}
                onKeyDown={(e) => {
                  if ((e.key === "Enter" || e.key === " ") && !processing && !full) {
                    e.preventDefault();
                    inputRef.current?.click();
                  }
                }}
                onDrop={handleDrop}
                onDragOver={(e) => { e.preventDefault(); if (!processing && !full) setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                className={[
                  "border-2 border-dashed rounded-lg p-10 text-center transition-colors",
                  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb",
                  dragActive ? "border-kb bg-info-bg" : files.length ? "border-kb60 bg-kb20" : "border-border hover:border-kb",
                  processing || full ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
                ].join(" ")}
              >
                <p className="text-sm font-medium text-muted">
                  {tCommon("dropOrBrowse")}{" "}
                  <span className="text-kb underline">{tCommon("browse")}</span>
                </p>
                <p className="text-xs text-muted-soft mt-1">{extensions.join(", ")}</p>
              </div>
              <input
                ref={inputRef}
                type="file"
                multiple
                accept={extensions.join(",")}
                onChange={(e) => {
                  addFiles(Array.from(e.target.files ?? []));
                  if (inputRef.current) inputRef.current.value = "";
                }}
                className="hidden"
                aria-hidden="true"
              />
              </>
              )}
              {uploadError && (
                <p className="mt-2 text-sm text-error" role="alert">{uploadError}</p>
              )}

              {mode === "files" && files.length > 0 && (
                <div className="mt-4">
                  <MaterialGauge bilanz={messung} max={messung.max} />
                  <p className="text-sm font-medium text-foreground mb-2">{t("chosenFiles")}</p>
                  <ul className="space-y-1">
                    {files.map((f, i) => (
                      <li key={`${f.name}-${f.size}`} className="text-sm text-foreground">
                        <div className="flex items-center justify-between gap-3">
                          <span className="truncate">{f.name}</span>
                          <span className="flex items-center gap-3 shrink-0">
                            <MeasureNote messung={messung.forFile(f)} />
                            {!processing && !doneJobUuid && (
                              <button
                                type="button"
                                onClick={() => removeFile(i)}
                                className="text-xs text-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb"
                              >
                                {t("removeFile")}
                              </button>
                            )}
                          </span>
                        </div>
                        <MeasureError messung={messung.forFile(f)} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              </>
            )}
          </div>
        </section>
        </div>

        {!demo && (
          <div className="mt-10">
            <h2 className="text-sm font-semibold text-foreground mb-1">{t("history.title")}</h2>
            <p className="text-xs text-muted mb-3">{verlauf.length ? t("history.hint") : t("history.empty")}</p>
            {verlauf.length > 0 && (
              <JobHistoryTable
                entries={verlauf}
                selectedUuid={doneJobUuid}
                disabled={processing}
                locale={locale}
                colMaterial={t("history.colMaterial")}
                colDate={t("history.colDate")}
                onSelect={(uuid) => { setDoneJobUuid(uuid); setErrorMessage(""); }}
              />
            )}
          </div>
        )}

        <Modal open={materialienOffen} onClose={() => setMaterialienOffen(false)} title={t("materialsModalTitle")} size="sm">
          <ul className="space-y-1.5 text-sm text-foreground">
            {materialien.map((name, i) => (
              <li key={`${i}-${name}`} className="truncate" title={name}>{name}</li>
            ))}
          </ul>
        </Modal>
      </div>
    </ProtectedRoute>
  );
}

/** Wrapped so useSearchParams (the jobs-list link) has the Suspense boundary it needs. */
export default function ZusammenfassungSeite(props: { demo?: boolean }) {
  return (
    <Suspense fallback={null}>
      <ZusammenfassungSeiteInner {...props} />
    </Suspense>
  );
}
