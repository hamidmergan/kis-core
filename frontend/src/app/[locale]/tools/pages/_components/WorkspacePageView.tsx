"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import { backendApi } from "@/lib/api";
import type { Limits, Page } from "../_lib/types";
import PageBar from "./PageBar";
import PageView from "./PageView";

interface Data {
  page: Page;
  limits: Limits;
  anchors: string[];
  workspace: { uuid: string; title: string };
}

/** A page as a workspace's members read it, opened from its source or from a citation. */
export default function WorkspacePageView({ workspaceUuid, sourceUuid }: { workspaceUuid: string; sourceUuid: string }) {
  const t = useTranslations("tools.pages");
  const section = Number(useSearchParams().get("abschnitt") || 0);
  const [data, setData] = useState<Data | null>(null);
  const [gone, setGone] = useState(false);
  const base = `/ai-assistant/workspaces/${workspaceUuid}/sources/${sourceUuid}/page`;

  useEffect(() => {
    backendApi.fetch(base)
      .then(async (r) => (r.ok ? setData(await r.json()) : setGone(true)))
      .catch(() => setGone(true));
  }, [base]);

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
        <PageBar back={`/workspace/${workspaceUuid}`} backLabel="Workspace" />
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
      <PageBar back={`/workspace/${workspaceUuid}`} backLabel={data.workspace.title || "Workspace"} />
      <PageView page={data.page} limits={data.limits} imageBase={`/api${base}/images`} />
      <ScrollTopButton />
    </>
  );
}
