"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import Spinner from "@/components/ui/Spinner";
import ScrollTopButton from "@/app/[locale]/_components/landing/ScrollTopButton";
import * as api from "../_lib/api";
import type { SharedPage } from "../_lib/types";
import { LanguageSwitch } from "./Languages";
import PageBar from "./PageBar";
import PageView from "./PageView";

/** A shared page as its link's readers see it, only the preview, never the editor. */
export default function SharedView({ code }: { code: string }) {
  const t = useTranslations("tools.pages");
  const router = useRouter();
  const [data, setData] = useState<SharedPage | null>(null);
  const [gone, setGone] = useState(false);
  // The language sits in the link, so a shared link can open the page in it directly.
  const [lang, setLang] = useState<string | null>(useSearchParams().get("sprache"));

  useEffect(() => {
    api.getShared(code, lang).then(setData).catch((e) => {
      // A link for KIS accounts only, after the login the person lands here again.
      if (e instanceof api.LoginNeeded) router.replace(`/login?next=${encodeURIComponent(`/p/${code}`)}`);
      else setGone(true);
    });
  }, [code, lang, router]);

  const switchTo = (key: string) => {
    const url = new URL(window.location.href);
    if (key === data?.languages[0]?.key) url.searchParams.delete("sprache");
    else url.searchParams.set("sprache", key);
    window.history.replaceState(null, "", url);
    setLang(key);
  };

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
      <PageBar>
        <LanguageSwitch value={data.language} choices={data.languages} onChange={switchTo} />
      </PageBar>
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
