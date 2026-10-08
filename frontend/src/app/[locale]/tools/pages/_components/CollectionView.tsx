"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ShareNetwork } from "@phosphor-icons/react";
import Spinner from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { useRouter } from "@/i18n/navigation";
import * as api from "../_lib/api";
import type { Collection } from "../_lib/types";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { CopyButton } from "./Sharing";
import { Thumb, useDate } from "./PagesSeite";

/** Every page one person shares, as cards, newest first. Private pages never show up here. */
export default function CollectionView({ code }: { code: string }) {
  const t = useTranslations("tools.pages");
  const router = useRouter();
  const date = useDate();
  const [data, setData] = useState<Collection | null>(null);
  const [gone, setGone] = useState(false);

  useEffect(() => {
    api.getCollection(code).then(setData).catch((e) => {
      // A link for KIS accounts only, after the login the person lands here again.
      if (e instanceof api.LoginNeeded) router.replace(`/login?next=${encodeURIComponent(`/u/${code}`)}`);
      else setGone(true);
    });
  }, [code, router]);

  if (gone) {
    return (
      <>
        <div className="max-w-md mx-auto mt-[12vh] px-4 text-center">
          <h1 className="text-xl font-bold mb-1.5">{t("collectionMissing")}</h1>
          <p className="text-sm" style={{ color: "var(--muted)" }}>{t("askOwner")}</p>
        </div>
      </>
    );
  }
  if (!data) return <div className="flex items-center justify-center min-h-[50vh]"><Spinner size="lg" /></div>;
  return (
    <>
      <div className="max-w-6xl mx-auto px-4 pt-8 pb-16">
        {data.own && <ToolBackLink href="/tools/pages" label={t("back")} />}
        <div className="flex items-center gap-3 mb-1">
          <h1 className="text-xl font-bold flex-1">{t("collectionHeading", { name: data.owner.name })}</h1>
          {data.own && (
            <CopyButton text={() => api.collectionUrl(code)} label={t("collectionCopy")} icon={<ShareNetwork size={17} weight="regular" />} />
          )}
        </div>
        <p className="text-sm text-muted mb-5">{t("collectionIntro", { name: data.owner.name })}</p>
        {data.pages.length === 0 ? (
          <EmptyState size="sm" text={t("collectionEmpty")} />
        ) : (
          <div className="grid gap-3.5" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
            {data.pages.map((p) => (
              <article
                key={p.code}
                data-testid="collection-card"
                tabIndex={0}
                onClick={() => router.push(`/p/${p.code}`)}
                onKeyDown={(e) => { if (e.key === "Enter") router.push(`/p/${p.code}`); }}
                className="flex flex-col rounded-xl border border-border-soft overflow-hidden bg-background cursor-pointer outline-2 outline-transparent hover:outline-kb focus-visible:outline-kb transition-[outline-color]"
                style={{ outlineStyle: "solid" }}
              >
                <Thumb src={p.image ? `${api.imageBase({ code: p.code })}/${p.image}` : null} />
                <div className="px-3.5 pt-3 pb-3.5">
                  <div className="font-semibold leading-snug text-foreground">{p.title}</div>
                  <div className="text-xs text-muted mt-0.5">{t("changedOn", { date: date(p.updated_at) })}</div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
