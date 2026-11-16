"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { EmptyState } from "@/components/ui/EmptyState";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import { backendApi } from "@/lib/api";
import type { Limits, Page } from "../_lib/types";
import PageView from "./PageView";
import { PageLoading } from "./ViewStates";

/** The prepared page of the demo, only to read, never to edit or share. */
export default function DemoView() {
  const t = useTranslations("tools.pages");
  const tDemo = useTranslations("tools.pagesDemo");
  const [data, setData] = useState<{ page: Page; limits: Limits } | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    backendApi.fetch("/pages-demo/page")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setMissing(true); });
    return () => { cancelled = true; };
  }, []);

  if (missing) return <div className="max-w-md mx-auto mt-[12vh] px-4"><EmptyState text={tDemo("keinErgebnis")} /></div>;
  if (!data) return <PageLoading />;
  return (
    <>
      <PageView page={data.page} limits={data.limits} imageBase="/api/pages-demo/images"
        back={{ href: "/tools/pages-demo", label: t("back") }} />
      <ScrollTopButton />
    </>
  );
}
