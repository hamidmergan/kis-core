"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowRight, BookOpenText, Info, Trash } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import Spinner from "@/components/ui/Spinner";
import Select from "@/components/ui/Select";
import Tabs from "@/components/ui/Tabs";
import Checkbox from "@/components/ui/Checkbox";
import Modal from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";
import ProviderSelect from "@/components/tools/ProviderSelect";
import MaterialGauge, { MeasureError, MeasureNote } from "@/components/tools/MaterialGauge";
import { Link, useRouter } from "@/i18n/navigation";
import { backendApi, parseDetail } from "@/lib/api";
import { MAX_UPLOAD_BYTES, MAX_UPLOAD_MB } from "@/lib/constants";
import { notifyJobsChanged } from "@/lib/jobs-events";
import { useFeatureProviders } from "@/hooks/useFeatureProviders";
import { useMaterialMeasure } from "@/hooks/useMaterialMeasure";
import { useModules } from "@/hooks/useModules";
import { usePermissions } from "@/hooks/usePermissions";
import * as api from "../_lib/api";
import type { PageCard, PagesList } from "../_lib/types";
import { CopyButton, ShareSwitch } from "./Sharing";
import { ErgebnisInfoKnopf } from "@/components/jobs/ErgebnisInfo";
import StilChips from "@/components/tools/StilChips";
import { Pagination } from "@/app/[locale]/my-jobs/_components/Pagination";

type SourceMode = "files" | "module";
const FALLBACK_EXTENSIONS = [".pdf", ".docx", ".pptx", ".txt", ".md", ".srt", ".vtt"];
// A page in the making is asked for this often.
const POLL_MS = 3000;
const RUNNING = new Set(["pending", "queued", "running", "waiting_retry"]);
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

/** The card picture: the page's first picture, a book when it has none. */
export function Thumb({ src, className = "aspect-video" }: { src: string | null; className?: string }) {
  return (
    <div className={`relative overflow-hidden ${className}`} style={{ background: "var(--tile-bg)" }}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- served by our own route behind the session
        <img src={src} alt="" className="block w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center" style={{ color: "var(--kb60)" }}>
          <BookOpenText size={44} weight="regular" aria-hidden="true" className="w-8 h-8 sm:w-11 sm:h-11" />
        </div>
      )}
    </div>
  );
}

export function useDate() {
  const locale = useLocale();
  return (iso: string | null) =>
    iso ? new Intl.DateTimeFormat(locale, { day: "2-digit", month: "2-digit", year: "numeric" }).format(new Date(iso)) : "";
}

/** The pages tool, and with demo the same page on the one prepared page of the demo module. */
export default function PagesSeite({ demo = false }: { demo?: boolean }) {
  const t = useTranslations("tools.pages");
  const tDemo = useTranslations("tools.pagesDemo");
  const tCommon = useTranslations("common");
  const tResult = useTranslations("common.result");
  const router = useRouter();
  const date = useDate();
  const { providers, providerId, setProviderId } = useFeatureProviders("/pages/providers");
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
  const [dragActive, setDragActive] = useState(false);
  const [toDelete, setToDelete] = useState<PageCard | null>(null);
  const [offset, setOffset] = useState(0);
  // Also read outside the demo, so the badge shows only when a prepared page is there.
  const [demoSetup, setDemoSetup] = useState<DemoSetup | null>(null);
  const listRef = useRef<HTMLElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const extensions = list?.extensions ?? FALLBACK_EXTENSIONS;
  const maxSources = list?.maxSources ?? 10;
  const canUseModules = !!permissions.allow_aia;
  const mode: SourceMode = demo ? "module" : canUseModules ? gewaehlterModus : "files";
  const { modules, sources } = useModules(mode === "module" && !demo ? moduleId : "");
  const messung = useMaterialMeasure("pages", mode, files, moduleId, sourceIds);
  const hatInhalt = mode === "files" ? files.length > 0 : sourceIds.length > 0;
  const full = files.length >= maxSources;
  const voll = sourceIds.length >= maxSources;

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
      if (mode === "files") files.forEach((f) => form.append("files", f));
      else {
        form.append("workspace_uuid", moduleId);
        form.append("source_uuids", JSON.stringify(sourceIds));
      }
      if (providerId != null) form.append("provider_id", String(providerId));
      if (instructions.trim()) form.append("instructions", instructions.trim());
      if (imageStyle?.trim()) form.append("image_style", imageStyle.trim());
      const res = await backendApi.fetch("/pages", { method: "POST", body: form });
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
    if (!res || !list) return;
    setList({
      ...list,
      collection: { ...list.collection, ...res.collection },
      pages: list.pages.map((x) => (x.job_uuid === p.job_uuid ? { ...x, shared: res.shared, public: res.public, code: res.code } : x)),
    });
  };

  const remove = async () => {
    if (!toDelete) return;
    await api.deletePage(toDelete.job_uuid).catch(() => {});
    setToDelete(null);
    notifyJobsChanged();
    load();
  };

  const stepText = (p: PageCard) => {
    const s = p.progress?.step;
    if (!s || !t.has(`step.${s}`)) return t("creating");
    return typeof p.progress.part === "number" && typeof p.progress.total === "number" && p.progress.part > 0
      ? t(`step.${s}Counted`, { part: p.progress.part, total: p.progress.total })
      : t(`step.${s}`);
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
          <p className="mb-6 flex items-start gap-2 rounded-lg border border-warn-border bg-warn-bg px-3 py-2.5 text-sm text-warn-strong">
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
              <div className="space-y-4">
                <Select id="pages-module" ariaLabel="Workspace" value="demo" onChange={() => {}} disabled
                  options={[{ value: "demo", label: demoSetup?.workspace ?? "" }]} />
                <div>
                  <ul className="space-y-2">
                    {(demoSetup?.files ?? []).map((name) => (
                      <li key={name}>
                        <Checkbox checked disabled onChange={() => {}} label={name} className="min-w-0 max-w-full"
                          labelClassName="text-sm text-foreground truncate min-w-0" />
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-muted">{tDemo("materialVorgegeben")}</p>
                </div>
              </div>
            ) : mode === "files" ? (
              <>
                <div
                  role="button"
                  tabIndex={0}
                  aria-label={t("selectFileAria")}
                  onClick={() => !sending && !full && inputRef.current?.click()}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === " ") && !sending && !full) { e.preventDefault(); inputRef.current?.click(); }
                  }}
                  onDrop={(e) => { e.preventDefault(); setDragActive(false); if (!sending) addFiles(Array.from(e.dataTransfer.files)); }}
                  onDragOver={(e) => { e.preventDefault(); if (!sending && !full) setDragActive(true); }}
                  onDragLeave={() => setDragActive(false)}
                  className={[
                    "border-2 border-dashed rounded-lg p-8 text-center transition-colors bg-background",
                    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-kb",
                    dragActive ? "border-kb bg-info-bg" : files.length ? "border-kb60" : "border-border hover:border-kb",
                    sending || full ? "opacity-50 cursor-not-allowed" : "cursor-pointer",
                  ].join(" ")}
                >
                  <p className="text-sm font-medium text-muted">
                    {tCommon("dropOrBrowse")} <span className="text-kb underline">{tCommon("browse")}</span>
                  </p>
                  <p className="text-xs text-muted-soft mt-1">{t("formats", { exts: extensions.join(", "), max: maxSources })}</p>
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  multiple
                  accept={extensions.join(",")}
                  onChange={(e) => { addFiles(Array.from(e.target.files ?? [])); if (inputRef.current) inputRef.current.value = ""; }}
                  className="hidden"
                  aria-hidden="true"
                />
                {files.length > 0 && (
                  <div className="mt-4">
                    <MaterialGauge bilanz={messung} max={messung.max} />
                    <ul className="space-y-1">
                      {files.map((f, i) => (
                        <li key={`${f.name}-${f.size}`} className="text-sm text-foreground">
                          <div className="flex items-center justify-between gap-3">
                            <span className="truncate">{f.name}</span>
                            <span className="flex items-center gap-3 shrink-0 whitespace-nowrap">
                              <MeasureNote messung={messung.forFile(f)} />
                              {!sending && (
                                <button type="button" onClick={() => setFiles((alt) => alt.filter((_, j) => j !== i))}
                                  className="text-xs text-muted hover:text-foreground">
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
            ) : modules === null ? (
              <Spinner className="justify-center py-10" />
            ) : modules.length === 0 ? (
              <EmptyState size="sm" text={t("noModules")} />
            ) : (
              <div className="space-y-4">
                <Select
                  id="pages-module"
                  ariaLabel="Workspace"
                  value={moduleId}
                  onChange={(uuid) => { setModuleId(uuid); setSourceIds([]); }}
                  disabled={sending}
                  placeholder={tCommon("pleaseSelect")}
                  options={modules.map((m) => ({ value: m.uuid, label: m.title }))}
                />
                {moduleId && (sources === null ? (
                  <Spinner className="justify-center py-6" />
                ) : sources.length === 0 ? (
                  <EmptyState size="sm" text={t("noSources")} />
                ) : (
                  <div>
                    {sourceIds.length > 0 && <MaterialGauge bilanz={messung} max={messung.max} />}
                    <ul className="space-y-2">
                      {sources.map((q) => (
                        <li key={q.uuid}>
                          <div className="flex items-center justify-between gap-3">
                            {/* The card is narrow, a long name is cut so the count stays inside it. */}
                            <span className="min-w-0 flex-1" title={q.filename}>
                              <Checkbox
                                checked={sourceIds.includes(q.uuid)}
                                disabled={sending || (voll && !sourceIds.includes(q.uuid))}
                                onChange={() => setSourceIds((alt) => alt.includes(q.uuid) ? alt.filter((id) => id !== q.uuid) : alt.length >= maxSources ? alt : [...alt, q.uuid])}
                                label={q.filename}
                                className="min-w-0 max-w-full"
                                labelClassName="text-sm text-foreground truncate min-w-0"
                              />
                            </span>
                            {sourceIds.includes(q.uuid) && (
                              <span className="shrink-0 whitespace-nowrap"><MeasureNote messung={messung.forSource(q.uuid)} /></span>
                            )}
                          </div>
                          {sourceIds.includes(q.uuid) && <MeasureError messung={messung.forSource(q.uuid)} />}
                        </li>
                      ))}
                    </ul>
                    <p className={`mt-2 text-xs ${voll ? "text-error font-medium" : "text-muted"}`}>{t("tooManySources", { max: maxSources })}</p>
                  </div>
                ))}
              </div>
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
              onChange={setProviderId} disabled={sending || demo} className="mt-6" showModel />

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
                    {shown.map((p) => {
                      const open = p.status === "success";
                      const go = () => open && router.push(demo ? "/tools/pages-demo/ansicht" : `/tools/pages/${p.job_uuid}`);
                      return (
                        <article
                          key={p.job_uuid}
                          data-testid="page-card"
                          tabIndex={open ? 0 : undefined}
                          onClick={go}
                          onKeyDown={(e) => { if (e.key === "Enter" && e.target === e.currentTarget) go(); }}
                          className={`flex flex-col rounded-xl border border-border-soft overflow-hidden bg-background outline-2 outline-transparent transition-[outline-color] ${open ? "cursor-pointer hover:outline-kb focus-visible:outline-kb" : ""}`}
                          style={{ outlineStyle: "solid" }}
                        >
                          <div className="flex flex-1 sm:block">
                            <Thumb
                              src={p.image ? `${demo ? "/api/pages-demo/images" : api.imageBase({ uuid: p.job_uuid })}/${p.image}` : null}
                              className="w-28 shrink-0 self-start mt-3 ml-3 rounded-lg aspect-[4/3] sm:w-auto sm:m-0 sm:rounded-none sm:aspect-video"
                            />
                            <div className="px-3.5 pt-3 pb-1 flex-1 min-w-0">
                              {p.title && <div className="font-semibold leading-snug text-foreground line-clamp-2 break-words" title={p.title}>{p.title}</div>}
                              <div className="text-xs text-muted mt-0.5 truncate" title={p.sources}>{p.sources}</div>
                              {open && <div className="text-xs text-muted mt-0.5">{t("changedOn", { date: date(p.updated_at) })}</div>}
                              {RUNNING.has(p.status) && <div className="text-xs text-muted mt-0.5">{stepText(p)} …</div>}
                              {p.status === "paused" && <div className="text-xs text-warn-strong mt-0.5">{t("paused")}</div>}
                              {p.status === "failed" && <div className="text-xs text-error mt-0.5 line-clamp-2">{p.error || t("failed")}</div>}
                            </div>
                          </div>
                          {RUNNING.has(p.status) ? (
                            <div className="mx-3.5 mb-3.5 mt-2"><Spinner size="xs" label={undefined} /></div>
                          ) : (
                            <div className="flex items-center justify-between gap-2 px-3.5 pt-2.5 pb-3 min-h-[50px]" onClick={(e) => e.stopPropagation()}>
                              {open && !demo ? <ShareSwitch on={p.shared} isPublic={p.public} onToggle={(on) => toggleShare(p, on)} /> : <span />}
                              <div className="flex items-center gap-1.5">
                                {open && p.shared && p.code && (
                                  <CopyButton text={() => api.shareUrl(p.code!)} label={t("copyLink")} />
                                )}
                                {open && (
                                  <ErgebnisInfoKnopf
                                    size="md"
                                    auftrag={{ angaben: p.info, erstellt: p.created_at, datei: p.sources }}
                                    zeilen={[
                                      { label: tResult("sources"), wert: (
                                        <ul className="space-y-0.5">{p.sources.split(", ").map((n, i) => <li key={i}>{n}</li>)}</ul>
                                      ) },
                                      { label: "Workspace", wert: p.info.workspace },
                                      { label: tResult("instructions"), wert: p.info.anweisung },
                                      { label: tResult("textProvider"), wert: p.info.anbieter },
                                      { label: tResult("imageProvider"), wert: p.info.bildanbieter },
                                      { label: tResult("imageStyle"), wert: p.info.bildstil },
                                    ]}
                                  />
                                )}
                                {!demo && <button
                                  type="button"
                                  onClick={() => setToDelete(p)}
                                  className="w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0"
                                  style={{ backgroundColor: "var(--surface-dim)" }}
                                  title={t("delete")}
                                  aria-label={t("delete")}
                                >
                                  <Trash size={13} weight="bold" />
                                </button>}
                              </div>
                            </div>
                          )}
                        </article>
                      );
                    })}
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
