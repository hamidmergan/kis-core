"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import Spinner from "@/components/ui/Spinner";
import HomeNotice from "./HomeNotice";
import UpcomingDeadlinesWidget from "./UpcomingDeadlinesWidget";
import WorkspaceList from "./WorkspaceList";

interface LinkPreview {
  workspace_uuid: string;
  title: string;
  /** Whether this person may enter right now. False while the owner has the
   *  workspace switched off. Joining still works, the room just stays shut. */
  is_open?: boolean;
}

interface Props {
  /** May own workspaces. Controls the owned block only, never the access link. */
  canCreate: boolean;
  firstName: string;
}

/** One home page for every role. Joining a workspace via access link works for
 *  everyone, and the workspace itself decides owner vs student by ownership. */
export default function WorkspaceHome({ canCreate, firstName }: Props) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [enrolling, setEnrolling] = useState(false);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const [linkPreview, setLinkPreview] = useState<LinkPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewCode, setPreviewCode] = useState<string | null>(null);
  const [previewInvalid, setPreviewInvalid] = useState(false);
  // Joined a workspace that is switched off: the enrollment is in place, the
  // room is not. Without this notice the person would land on a list whose new
  // row is greyed out, with nothing saying why.
  const [joinedClosed, setJoinedClosed] = useState(false);

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
      const data = (await res.json()) as { workspace_uuid?: string; is_open?: boolean };
      // Walking into a closed workspace would only earn a locked page, so the
      // way leads back to the list, where the fresh row carries the hint.
      if (data.is_open === false) {
        setJoinedClosed(true);
        router.replace("/");
        return;
      }
      if (data.workspace_uuid) router.replace(`/workspace/${data.workspace_uuid}`);
    } catch (err: unknown) {
      setEnrollError(err instanceof Error ? err.message : t("unknownError"));
    } finally {
      setEnrolling(false);
    }
  }

  // An access link takes over the page until it is accepted or turns out invalid.
  if (previewCode && previewLoading) {
    return (
      <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="max-w-5xl mx-auto flex items-center justify-center min-h-[40vh]">
          <Spinner size="lg" />
        </div>
      </div>
    );
  }

  if (linkPreview) {
    return (
      <div className="px-4 sm:px-6 md:px-8 pt-10 pb-20 lg:pt-15 lg:pb-30">
        <div className="max-w-5xl mx-auto">
          <section
            className="rounded-xl p-10 mb-12 flex flex-col items-center text-center"
            style={{ backgroundColor: "var(--surface)", boxShadow: "var(--shadow)" }}
          >
            <h2 className="text-2xl font-semibold mb-6" style={{ color: "var(--foreground)" }}>
              {linkPreview.title}
            </h2>
            {/* Der Raum ist zu. Einschreiben geht trotzdem, deshalb steht der
                Hinweis ueber dem Knopf und nicht an seiner Stelle. */}
            {linkPreview.is_open === false && (
              <p
                className="mb-6 max-w-md text-sm rounded-lg px-4 py-3"
                style={{ backgroundColor: "var(--surface-dim)", color: "var(--muted)" }}
              >
                {t("closedJoinHint")}
              </p>
            )}
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
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell pt-6 pb-20 lg:pt-15 lg:pb-30">
      <div className="mb-10 lg:mb-16">
        <h1 className="text-3xl font-bold min-h-[2.25rem]">
          {firstName && t("headerTitle", { name: firstName })}
        </h1>
        <p className="text-sm text-foreground-soft mt-1">
          {new Date().toLocaleDateString(locale === "en" ? "en-US" : "de-DE", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "Europe/Berlin",
          })}
        </p>
      </div>

      {previewInvalid && (
        <div
          className="rounded-xl p-4 mb-8 text-sm"
          style={{ backgroundColor: "var(--error-bg)", color: "var(--error)" }}
        >
          {t("enrollInvalidCode")}
        </div>
      )}

      {joinedClosed && (
        <div
          className="rounded-xl p-4 mb-8 text-sm"
          style={{ backgroundColor: "var(--surface-dim)", color: "var(--foreground-soft)" }}
        >
          {t("closedJoinedNotice")}
        </div>
      )}

      <HomeNotice />

      <div className="mb-12">
        <UpcomingDeadlinesWidget />
      </div>

      <WorkspaceList canCreate={canCreate} />
    </div>
  );
}
