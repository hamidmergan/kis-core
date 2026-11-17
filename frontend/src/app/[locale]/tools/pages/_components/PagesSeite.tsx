"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowRight, Info } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import Spinner from "@/components/ui/Spinner";
import Tabs from "@/components/ui/Tabs";
import Modal from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import ProviderSelect from "@/components/tools/ProviderSelect";
import StilChips from "@/components/tools/StilChips";
import { Pagination } from "@/app/[locale]/my-jobs/_components/Pagination";
import { Link, useRouter } from "@/i18n/navigation";
import { backendApi, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from "@/lib/constants";
import { appendFiles } from "@/lib/directUpload";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import { useModules } from "@/hooks/useModules";
import { usePermissions } from "@/hooks/usePermissions";
import * as api from "../_lib/api";
import type { PageCard, PagesList } from "../_lib/types";
import { PageKarte, RUNNING } from "./PageCard";
import { DemoSources, FileSources, ModuleSources } from "./PageSources";

type SourceMode = "files" | "module";
const FALLBACK_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md", ".srt", ".vtt"];
// A page in the making is asked for this often.
const POLL_MS = 3000;
// Cards per list page, the newest come first.
const PER_PAGE = 9;
// The demo badge, the same amber as on every other tool with a demo.
const DEMO_BADGE = "text-xs font-semibold px-3.5 py-1.5 rounded border-2 border-transparent hover:border-black transition-colors";
const DEMO_FARBE = { backgroundColor: "rgb(245, 158, 11)", color: "rgb(0, 0, 0)" };

/** The prepared run of the demo: its material and the one page the demo list shows. */
interface DemoSetup {
  workspace: string;
  files: string[];
  instructions: string;
  card: Omit<PageCard, "job_uuid" | "status" | "progress" | "error" | "shared" | "public" | "code"> | null;
}

/** The pages tool, and with demo the same page on the one prepared page of the demo module. */
export default function PagesSeite({ demo = false }: { demo?: boolean }) {
  const t = useTranslations("tools.pages");
  const tDemo = useTranslations("tools.pagesDemo");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const { providers, providerId, setProviderId, loading: providersLoading } = useFeatureProviders("/pages/providers");
  const { permissions } = usePermissions();
  const [list, setList] = useState<PagesList | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [gewaehlterModus, setModus] = useState<SourceMode>("files");
  const [moduleId, setModuleId] = useState("");
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [instructions, setInstructions] = useState("");
  // Null until the default arrived, then the person's text, starting as that default.
  const [imageStyle, setImageStyle] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [toDelete, setToDelete] = useState<PageCard | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<{ uuid: string; message: string } | null>(null);
  const [offset, setOffset] = useState(0);
  // Also read outside the demo, so the badge shows only when a prepared page is there.
  const [demoSetup, setDemoSetup] = useState<DemoSetup | null>(null);
  const listRef = useRef<HTMLElement>(null);

  const extensions = list?.extensions ?? FALLBACK_EXTENSIONS;
  const maxSources = list?.maxSources ?? 10;
  const canUseModules = !!permissions.allow_aia;
  const mode: SourceMode = demo ? "module" : canUseModules ? gewaehlterModus : "files";
  const { modules, sources } = useModules(mode === "module" && !demo ? moduleId : "");
  const messung = useMaterialMeasure("pages", mode, files, moduleId, sourceIds);
  const hatInhalt = mode === "files" ? files.length > 0 : sourceIds.length > 0;

  const load = useCallback(() => api.listPages().then(setList).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    backendApi.fetch("/pages-demo/setup").then((r) => (r.ok ? r.json() : null)).then(setDemoSetup).catch(() => {});
  }, []);
  useEffect(() => {
    if (list && imageStyle === null) setImageStyle(list.imageStyle);
  }, [list, imageStyle]);

  // While a page is being made, its card follows the run.
  const running = !demo && !!list?.pages.some((p) => RUNNING.has(p.status));
  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(load, POLL_MS);
    return () => window.clearInterval(id);
  }, [running, load]);

  // The demo list holds only the prepared page, it opens in its own reading view.
  const demoCards: PageCard[] = demo && demoSetup?.card
    ? [{ ...demoSetup.card, job_uuid: "demo", status: "success", progress: {}, error: null, shared: false, public: false, code: null }]
    : [];
  const pages = demo ? demoCards : list?.pages ?? [];
  // A deletion may leave the offset past the last list page.
  const total = pages.length;
  const start = Math.min(offset, Math.max(0, Math.ceil(total / PER_PAGE) - 1) * PER_PAGE);
  const shown = pages.slice(start, start + PER_PAGE);
  const goTo = (next: number) => {
    setOffset(next);
    listRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    if (!sources) return;
    const vorhanden = new Set(sources.map((q) => q.uuid));
    setSourceIds((alt) => alt.filter((id) => vorhanden.has(id)));
  }, [sources]);

  const addFiles = (neue: File[]) => {
    setUploadError(null);
    setErrorMessage("");
    setFiles((alt) => {
      const gesamt = [...alt];
      for (const f of neue) {
        const ext = "." + (f.name.split(".").pop()?.toLowerCase() ?? "");
        if (!extensions.includes(ext)) { setUploadError(tCommon("onlyExtsAllowed", { exts: extensions.join(", ") })); continue; }
        if (f.size > MAX_UPLOAD_BYTES) { setUploadError(tCommon("fileTooLarge", { n: MAX_UPLOAD_MB })); continue; }
        if (gesamt.length >= maxSources) { setUploadError(t("tooManySources", { max: maxSources })); break; }
        if (!gesamt.some((g) => g.name === f.name && g.size === f.size)) gesamt.push(f);
      }
      return gesamt;
    });
  };

  const submit = async () => {
    if (demo || !hatInhalt || !messung.ready || sending) return;
    setSending(true);
    setErrorMessage("");
    try {
      const form = new FormData();
      form.append("mode", mode);
      // Large files go in parts straight into the bucket, small ones with the request.
      const forgetUploads = mode === "files" ? await appendFiles(form, { tool: "pages", files }) : () => {};
      if (mode !== "files") {
        form.append("workspace_uuid", moduleId);
        form.append("source_uuids", JSON.stringify(sourceIds));
      }
      if (providerId != null) form.append("provider_id", String(providerId));
      if (instructions.trim()) form.append("instructions", instructions.trim());
      if (imageStyle?.trim()) form.append("image_style", imageStyle.trim());
      const res = await backendApi.fetch("/pages", { method: "POST", body: form });
      forgetUploads();
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: tCommon("unknownError") }));
        throw new Error(parseDetail(err.detail, tCommon("unknownError")));
      }
      notifyJobsChanged();
      setFiles([]);
      setSourceIds([]);
      setInstructions("");
      setOffset(0);
      await load();
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : tCommon("unknownError"));
    } finally {
      setSending(false);
    }
  };

  const toggleShare = async (p: PageCard, on: boolean) => {
    const res = await api.setShare(p.job_uuid, on).catch(() => null);
    if (!res) return;
    // A poll may have replaced the list while the call ran, so the change goes into the list of now.
    setList((now) => now && {
      ...now,
      collection: { ...now.collection, ...res.collection },
      pages: now.pages.map((x) => (x.job_uuid === p.job_uuid ? { ...x, shared: res.shared, public: res.public, code: res.code } : x)),
    });
  };

  const cancel = async (p: PageCard) => {
    setCancelling(p.job_uuid);
    await api.deletePage(p.job_uuid).catch(() => {});
    setCancelling(null);
    notifyJobsChanged();
    load();
  };

  const retry = async (p: PageCard) => {
    setRetrying(p.job_uuid);
    setRetryError(null);
    try {
      await api.retryPage(p.job_uuid);
    } catch (err) {
      setRetryError({ uuid: p.job_uuid, message: err instanceof Error ? err.message : tCommon("unknownError") });
    }
    setRetrying(null);
    notifyJobsChanged();
    load();
  };

  const remove = async () => {
    if (!toDelete) return;
    await api.deletePage(toDelete.job_uuid).catch(() => {});
    setToDelete(null);
    notifyJobsChanged();
    load();
  };

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <ToolBackLink />
        <div className="flex items-baseline justify-between gap-3 mb-1">
          <h1 className="text-xl font-bold">{t("title")}</h1>
          {demo ? (
            <Link href="/tools/pages" className={DEMO_BADGE} style={DEMO_FARBE}>{tDemo("beenden")}</Link>
          ) : !!demoSetup?.card && (
            <Link href="/tools/pages-demo" className={DEMO_BADGE} style={DEMO_FARBE}>{t("demoBadge")}</Link>
          )}
        </div>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>
        {demo && (
          <p className="mb-6 flex items-start gap-2 text-sm text-warn-strong">
            <Info size={14} className="mt-0.5 flex-shrink-0 text-warn" aria-hidden="true" />
            {tDemo("hinweis")}
          </p>
        )}

        <div className="grid gap-8 lg:grid-cols-[minmax(0,400px)_1fr]">
          <section className="min-w-0 self-start rounded-xl border border-border-soft bg-surface p-4 sm:p-5">
            {(canUseModules || demo) && (
              <Tabs<SourceMode>
                className="mb-4"
                active={mode}
                onChange={(next) => { setModus(next); setUploadError(null); setErrorMessage(""); }}
                items={[{ key: "files", label: t("tabs.files"), disabled: demo }, { key: "module", label: "Workspace" }]}
              />
            )}

            {demo ? (
              <DemoSources workspace={demoSetup?.workspace ?? ""} files={demoSetup?.files ?? []} />
            ) : mode === "files" ? (
              <FileSources files={files} extensions={extensions} maxSources={maxSources} sending={sending} messung={messung}
                onAdd={addFiles} onRemove={(i) => setFiles((alt) => alt.filter((_, j) => j !== i))} />
            ) : modules === null ? (
              <Spinner className="justify-center py-10" />
            ) : modules.length === 0 ? (
              <EmptyState size="sm" text={t("noModules")} />
            ) : (
              <ModuleSources modules={modules} sources={sources} moduleId={moduleId} sourceIds={sourceIds} maxSources={maxSources}
                sending={sending} messung={messung}
                onModule={(uuid) => { setModuleId(uuid); setSourceIds([]); }}
                onToggle={(uuid) => setSourceIds((alt) => alt.includes(uuid) ? alt.filter((id) => id !== uuid) : alt.length >= maxSources ? alt : [...alt, uuid])} />
            )}
            {uploadError && <p className="mt-2 text-sm text-error" role="alert">{uploadError}</p>}

            <div className="mt-6">
              <label htmlFor="pages-instructions" className="block text-sm font-medium text-foreground mb-1">{t("instructionsLabel")}</label>
              <textarea
                id="pages-instructions"
                value={demo ? demoSetup?.instructions ?? "" : instructions}
                onChange={(e) => setInstructions(e.target.value)}
                readOnly={demo}
                disabled={sending}
                rows={3}
                maxLength={500}
                placeholder={t("instructionsPlaceholder")}
                className="w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft resize-y"
              />
            </div>

            <div className="mt-6">
              <label htmlFor="pages-image-style" className="block text-sm font-medium text-foreground mb-1">{t("imageStyleLabel")}</label>
              {list && (
                <StilChips stile={{ pages: list.imageStyle, ...list.imageStyles }} standard="pages" wert={imageStyle ?? ""}
                  onWahl={setImageStyle} disabled={sending || demo} />
              )}
              <textarea
                id="pages-image-style"
                value={imageStyle ?? ""}
                onChange={(e) => setImageStyle(e.target.value)}
                disabled={sending || imageStyle === null || demo}
                rows={4}
                maxLength={list?.imageStyleMax ?? 600}
                className="w-full px-3 py-2 text-sm border-2 border-border rounded-md bg-background hover:border-kb focus:outline-none focus:border-kb placeholder:text-muted-soft resize-y"
              />
              <p className="mt-1 text-xs text-muted">{t("imageStyleHint")}</p>
            </div>

            <ProviderSelect id="pages-provider-select" label={t("providerLabel")} providers={providers} value={providerId}
              onChange={setProviderId} disabled={sending || demo} loading={providersLoading} className="mt-6" showModel />

            <div className="mt-6">
              <button
                type="button"
                onClick={submit}
                disabled={demo || !hatInhalt || !messung.ready || sending}
                title={demo ? tDemo("ohneErstellen") : undefined}
                className="px-5 py-2 btn-primary text-sm font-medium rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {sending && <Spinner size="sm" color="current" />}
                {t("submit")}
              </button>
            </div>
            {errorMessage && <p className="mt-3 text-sm text-error" role="alert">{errorMessage}</p>}
          </section>

          <section ref={listRef} className="min-w-0 scroll-mt-4">
            <div className="flex items-center gap-2 mb-2.5">
              <h2 className="text-base font-semibold">{t("listTitle")}</h2>
              {list && !demo && (
                <button type="button" className="ml-auto flex items-center gap-1.5 px-3.5 py-1.5 text-sm font-medium btn-secondary rounded-lg whitespace-nowrap"
                  title={t("collectionText", { count: list.collection.count })}
                  onClick={() => router.push(`/u/${list.collection.code}`)}>
                  {t("collectionView")}
                  <ArrowRight size={15} weight="bold" />
                </button>
              )}
            </div>
            {list === null || (demo && demoSetup === null) ? (
              <Spinner className="justify-center py-10" />
            ) : (
              <>
                {pages.length === 0 ? (
                  <EmptyState size="sm" text={demo ? tDemo("keinErgebnis") : t("empty")} />
                ) : (
                  <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
                    {shown.map((p) => (
                      <PageKarte
                        key={p.job_uuid}
                        p={p}
                        demo={demo}
                        cancelling={cancelling === p.job_uuid}
                        retrying={retrying === p.job_uuid}
                        retryError={retryError?.uuid === p.job_uuid ? retryError.message : null}
                        onShare={(on) => toggleShare(p, on)}
                        onCancel={() => cancel(p)}
                        onRetry={() => retry(p)}
                        onDelete={() => setToDelete(p)}
                      />
                    ))}
                  </div>
                )}
                <Pagination total={total} offset={start} limit={PER_PAGE} onOffsetChange={goTo} />
              </>
            )}
          </section>
        </div>
      </div>

      <Modal
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        size="sm"
        title={t("deleteTitle")}
        footer={
          <>
            <button type="button" className="btn-cancel px-4 py-2 text-sm btn-secondary rounded-lg" onClick={() => setToDelete(null)}>{t("cancel")}</button>
            <button type="button" className="px-4 py-2 text-sm btn-primary rounded-lg" onClick={remove}>{t("delete")}</button>
          </>
        }
      >
        <p className="text-sm">{t("deleteText", { title: toDelete?.title || toDelete?.sources || "" })}</p>
      </Modal>
    </ProtectedRoute>
  );
}
