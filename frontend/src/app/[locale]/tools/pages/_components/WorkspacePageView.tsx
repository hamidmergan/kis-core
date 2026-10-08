"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import { backendApi } from "@/lib/api";
import type { LanguageChoice, Limits, Page } from "../_lib/types";
import ToolBackLink from "@/components/ui/ToolBackLink";
import PageView from "./PageView";

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
    backendApi.fetch(`${base}?sprache=${encodeURIComponent(lang)}`)
      .then(async (r) => (r.ok ? setData(await r.json()) : setGone(true)))
      .catch(() => setGone(true));
  }, [base, lang]);

  // A citation names a section by its number, the page jumps there once it is drawn.
  useEffect(() => {
    if (!data || !section) return;
    const id = data.anchors[section - 1];
    const el = id ? document.getElementById(id) : null;
    if (el) window.setTimeout(() => el.scrollIntoView({ block: "start" }), 50);
  }, [data, section]);

  if (gone) {
    return (
      <>
        <div className="max-w-6xl mx-auto px-4 pt-8"><ToolBackLink href={`/workspace/${workspaceUuid}`} label="Workspace" /></div>
        <div className="max-w-md mx-auto mt-[12vh] px-4 text-center">
          <h1 className="text-xl font-bold mb-1.5">{t("pageGone")}</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("askOwner")}</p>
        </div>
      </>
    );
  }
  if (!data) return <div className="flex items-center justify-center min-h-[50vh]"><Spinner size="lg" /></div>;
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
