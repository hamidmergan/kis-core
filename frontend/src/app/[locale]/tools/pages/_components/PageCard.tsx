"use client";

import { useLocale, useTranslations } from "next-intl";
import { BookOpenText, Trash, X } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { ErgebnisInfoKnopf } from "@/components/jobs/ErgebnisInfo";
import { useRouter } from "@/i18n/navigation";
import * as api from "../_lib/api";
import type { PageCard } from "../_lib/types";
import { CopyButton, ShareSwitch } from "./Sharing";

export const RUNNING = new Set(["pending", "queued", "running", "waiting_retry"]);

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

interface KarteProps {
  p: PageCard;
  demo: boolean;
  cancelling: boolean;
  retrying: boolean;
  retryError: string | null;
  onShare: (on: boolean) => void;
  onCancel: () => void;
  onRetry: () => void;
  onDelete: () => void;
}

/** One page of the list: its picture, where its run stands, and what the owner can do with it. */
export function PageKarte({ p, demo, cancelling, retrying, retryError, onShare, onCancel, onRetry, onDelete }: KarteProps) {
  const t = useTranslations("tools.pages");
  const tResult = useTranslations("common.result");
  const router = useRouter();
  const date = useDate();
  const open = p.status === "success";
  const go = () => open && router.push(demo ? "/tools/pages-demo/ansicht" : `/tools/pages/${p.job_uuid}`);
  const stepText = () => {
    const s = p.progress?.step;
    if (!s || !t.has(`step.${s}`)) return t("creating");
    return typeof p.progress.part === "number" && typeof p.progress.total === "number" && p.progress.part > 0
      ? t(`step.${s}Counted`, { part: p.progress.part, total: p.progress.total })
      : t(`step.${s}`);
  };
  return (
    <article
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
          {RUNNING.has(p.status) && <div className="text-xs text-muted mt-0.5">{stepText()} …</div>}
          {p.status === "paused" && <div className="text-xs text-warn-strong mt-0.5">{t("paused")}</div>}
          {p.status === "failed" && <div className="text-xs text-error mt-0.5 line-clamp-2">{p.error || t("failed")}</div>}
          {retryError && <div className="text-xs text-error mt-0.5 line-clamp-2" role="alert">{retryError}</div>}
        </div>
      </div>
      {RUNNING.has(p.status) ? (
        <div className="flex items-center justify-between gap-2 mx-3.5 mb-3 mt-2" onClick={(e) => e.stopPropagation()}>
          <Spinner size="xs" label={undefined} />
          {!demo && <button
            type="button"
            onClick={onCancel}
            disabled={cancelling}
            className="w-7 h-7 flex items-center justify-center rounded-full btn-icon flex-shrink-0 disabled:opacity-50"
            style={{ backgroundColor: "var(--surface-dim)" }}
            title={t("cancelDelete")}
            aria-label={t("cancelDelete")}
          >
            <X size={13} weight="bold" />
          </button>}
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2 px-3.5 pt-2.5 pb-3 min-h-[50px]" onClick={(e) => e.stopPropagation()}>
          {open && !demo ? <ShareSwitch on={p.shared} isPublic={p.public} onToggle={onShare} />
            : !demo && (p.status === "failed" || p.status === "paused") ? (
              <button
                type="button"
                onClick={onRetry}
                disabled={retrying}
                className="btn-primary inline-flex text-xs font-medium px-2.5 py-1 rounded-md disabled:opacity-50"
              >
                {retrying ? "..." : t(p.status === "paused" ? "continue" : "retry")}
              </button>
            ) : <span />}
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
              onClick={onDelete}
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
}
