"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import * as api from "../_lib/api";
import type { SharedPage } from "../_lib/types";
import PageView from "./PageView";
import { GoneNote, PageLoading } from "./ViewStates";

/** A shared page as its link's readers see it, only the preview, never the editor. */
export default function SharedView({ code }: { code: string }) {
  const t = useTranslations("tools.pages");
  const router = useRouter();
  const [data, setData] = useState<SharedPage | null>(null);
  const [gone, setGone] = useState(false);
  // The page follows the language of the interface, the server falls back to the page's own.
  const lang = useLocale();

  useEffect(() => {
    let cancelled = false;
    api.getShared(code, lang).then((d) => { if (!cancelled) setData(d); }).catch((e) => {
      if (cancelled) return;
      // A link for askFrancis accounts only, after the login the person lands here again.
      if (e instanceof api.LoginNeeded) router.replace(`/login?next=${encodeURIComponent(`/p/${code}`)}`);
      else setGone(true);
    });
    return () => { cancelled = true; };
  }, [code, lang, router]);

  if (gone) return <GoneNote title={t("notSharedTitle")} />;
  if (!data) return <PageLoading />;
  return (
    <>
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
