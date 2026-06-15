"use client";

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { CalendarBlank } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import ExpandableText from "@/components/ui/ExpandableText";
import UpcomingDeadlinesWidget from "./UpcomingDeadlinesWidget";
import HomeNotice from "./HomeNotice";
import { useWorkspaceLabel } from "@/hooks/useWorkspaceLabel";
import type { StudentWorkspace } from "../_shared";

interface LinkPreview {
  workspace_uuid: string;
  title: string;
}

export default function StudentView() {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const labels = useWorkspaceLabel();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [workspaces, setModules] = useState<StudentWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const [linkPreview, setLinkPreview] = useState<LinkPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewCode, setPreviewCode] = useState<string | null>(null);
  const [previewInvalid, setPreviewInvalid] = useState(false);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setLinkPreview(null);
      setPreviewCode(null);
      setPreviewInvalid(false);
      return;
    }
    setPreviewCode(code);
    setPreviewLoading(true);
    setPreviewInvalid(false);
    fetch(`/api/ai-assistant/access-link/preview?code=${encodeURIComponent(code)}`, {
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          setLinkPreview(null);
          setPreviewInvalid(true);
          return;
        }
        const data = (await res.json()) as LinkPreview;
        setLinkPreview(data);
      })
      .catch(() => {
        setLinkPreview(null);
        setPreviewInvalid(true);
      })
      .finally(() => setPreviewLoading(false));
  }, [searchParams]);

  const loadModules = useCallback(async () => {
    try {
      const res = await fetch("/api/ai-assistant/my-workspaces", { credentials: "include" });
      if (res.ok) setModules(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadModules().finally(() => setLoading(false));
  }, [loadModules]);

  useEffect(() => {
    const needsPoll = workspaces.some((m) => m.status === "pending" || m.status === "indexing");
    if (!needsPoll) return;
    const id = setInterval(loadModules, 3000);
    return () => clearInterval(id);
  }, [workspaces, loadModules]);

  async function handleEnrollLink() {
    if (!previewCode) return;
    setEnrolling(true);
    setEnrollError(null);
    try {
      const res = await fetch("/api/ai-assistant/enroll", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enroll_code: previewCode }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? t("enrollInvalidCode"));
      }
      const data = (await res.json()) as { workspace_uuid?: string };
      if (data.workspace_uuid) router.replace(`/workspace/${data.workspace_uuid}`);
    } catch (err: unknown) {
      setEnrollError(err instanceof Error ? err.message : t("unknownError"));
    } finally {
      setEnrolling(false);
    }
  }

  const showLinkCard = !!linkPreview;
  const previewPending = !!previewCode && previewLoading;

  return (
    <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
      <div className="max-w-5xl mx-auto">
      {!showLinkCard && !previewPending && (
        <h1 className="text-3xl font-bold mb-10">{t("welcomeTitle")}</h1>
      )}

      {previewPending ? (
        <div className="flex items-center justify-center min-h-[40vh]">
          <Spinner size="lg" />
        </div>
      ) : showLinkCard ? (
        <section
          className="rounded-xl p-10 mb-12 flex flex-col items-center text-center"
          style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
        >
          <h2 className="text-2xl font-semibold mb-6" style={{ color: "var(--foreground)" }}>
            {linkPreview!.title}
          </h2>
          <button
            type="button"
            onClick={handleEnrollLink}
            disabled={enrolling}
            className="btn-primary px-8 py-3 rounded-lg text-base font-medium disabled:opacity-50"
          >
            {enrolling ? "…" : t("enroll")}
          </button>
          {enrollError && (
            <p className="mt-4 text-sm" style={{ color: "var(--error)" }}>
              {enrollError}
            </p>
          )}
        </section>
      ) : (
        <>
          {previewInvalid && (
            <div
              className="rounded-xl p-4 mb-8 text-sm"
              style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}
            >
              {t("enrollInvalidCode")}
            </div>
          )}

          <HomeNotice />

          <div className="mb-12">
            <UpcomingDeadlinesWidget />
          </div>

          <h2 className="text-xl font-semibold mb-8">{t("myWorkspaces", { label: labels.plural })}</h2>
        </>
      )}

      {!showLinkCard && !previewPending && (
        loading ? (
          <div className="flex items-center justify-center min-h-[60vh]">
            <Spinner size="lg" />
          </div>
        ) : workspaces.length === 0 ? (
          <p className="text-center py-10 text-sm" style={{ color: "var(--muted)" }}>
            {t("noEnrollments")}
          </p>
        ) : (
          <ul className="divide-y divide-border-soft border border-border-soft rounded-xl overflow-hidden">
            {workspaces.map((m, i) => {
              const href = m.enrollment_id ? `/workspace/${m.uuid}?eid=${m.enrollment_id}` : `/workspace/${m.uuid}`;
              const untilDate = m.enrolled_until
                ? new Date(m.enrolled_until).toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    timeZone: "Europe/Berlin",
                  })
                : null;
              return (
                <li
                  key={`${m.uuid}-${m.enrollment_id ?? i}`}
                  className="px-5 py-4 bg-background hover:bg-surface cursor-pointer"
                  onClick={() => router.push(href)}
                  onMouseEnter={() => router.prefetch(href)}
                  onMouseDown={(e) => { if (e.button === 1) { e.preventDefault(); window.open(`/${locale}${href}`, "_blank"); } }}
                >
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium truncate">{m.title}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      {m.description && (
                        <ExpandableText className="text-xs text-muted-soft" clampClass="line-clamp-1">
                          {m.description}
                        </ExpandableText>
                      )}
                      {untilDate && (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-soft whitespace-nowrap">
                          <CalendarBlank size={12} />
                          {t("untilDate", { date: untilDate })}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )
      )}
      </div>
    </div>
  );
}
