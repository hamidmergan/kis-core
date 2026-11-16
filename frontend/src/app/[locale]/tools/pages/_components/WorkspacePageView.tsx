"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import { backendApi } from "@/lib/api";
import ToolBackLink from "@/components/ui/ToolBackLink";
import type { LanguageChoice, Limits, Page } from "../_lib/types";
import PageView from "./PageView";
import { GoneNote, PageLoading } from "./ViewStates";

interface Data {
  page: Page;
  limits: Limits;
  anchors: string[];
  languages: LanguageChoice[];
  language: string;
  workspace: { uuid: string; title: string };
}

/** A page as a workspace's members read it, opened from its source or from a citation. */
export default function WorkspacePageView({ workspaceUuid, sourceUuid }: { workspaceUuid: string; sourceUuid: string }) {
  const t = useTranslations("tools.pages");
  const params = useSearchParams();
  const section = Number(params.get("abschnitt") || 0);
  const [data, setData] = useState<Data | null>(null);
  const [gone, setGone] = useState(false);
  // The page follows the language of the interface, the server falls back to the page's own.
  const lang = useLocale();
  const base = `/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/page`;

  useEffect(() => {
    let cancelled = false;
    backendApi.fetch(`${base}?sprache=${encodeURIComponent(lang)}`)
      .then(async (r) => {
        const body = r.ok ? await r.json() : null;
        if (cancelled) return;
        if (body) setData(body);
        else setGone(true);
      })
      .catch(() => { if (!cancelled) setGone(true); });
    return () => { cancelled = true; };
  }, [base, lang]);

  // A citation names a section by its number, the page jumps there once it is drawn.
  useEffect(() => {
    if (!data || !section) return;
    const id = data.anchors[section - 1];
    const el = id ? document.getElementById(id) : null;
    if (!el) return;
    const timer = window.setTimeout(() => el.scrollIntoView({ block: "start" }), 50);
    return () => window.clearTimeout(timer);
  }, [data, section]);

  if (gone) {
    return (
      <>
        <div className="max-w-6xl mx-auto px-4 pt-8"><ToolBackLink href={`/workspace/${workspaceUuid}`} label="Workspace" /></div>
        <GoneNote title={t("pageGone")} />
      </>
    );
  }
  if (!data) return <PageLoading />;
  return (
    <>
      <PageView
        page={data.page}
        limits={data.limits}
        imageBase={`/api${base}/images`}
        back={{ href: `/workspace/${workspaceUuid}`, label: data.workspace.title || "Workspace" }}
      />
      <ScrollTopButton />
    </>
  );
}
