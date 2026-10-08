"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import * as api from "../_lib/api";
import type { SharedPage } from "../_lib/types";
import PageBar from "./PageBar";
import PageView from "./PageView";

/** A shared page as anyone with a KIS account reads it, only the preview, never the editor. */
export default function SharedView({ code }: { code: string }) {
  const t = useTranslations("tools.pages");
  const [data, setData] = useState<SharedPage | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    api.getShared(code).then(setData).catch(() => setGone(true));
  }, [code]);

  if (gone) {
    return (
      <>
        <PageBar />
        <div className="max-w-md mx-auto mt-[12vh] px-4 text-center">
          <h1 className="text-xl font-bold mb-1.5">{t("notSharedTitle")}</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("askOwner")}</p>
        </div>
      </>
    );
  }
  if (!data) return <div className="flex items-center justify-center min-h-[50vh]"><Spinner size="lg" /></div>;
  return (
    <>
      <PageBar />
      <PageView
        page={data.page}
        limits={data.limits}
        imageBase={api.imageBase({ code })}
        back={data.owner.code ? { href: `/u/${data.owner.code}`, label: t("allPagesOf", { name: data.owner.name }) } : undefined}
      />
      <ScrollTopButton />
    </>
  );
}
