"use client";

import { useTranslations } from "next-intl";
import Spinner from "@/components/ui/Spinner";

/** The spinner in the middle of the screen while a page or an overview loads. */
export function PageLoading() {
  return <div className="flex items-center justify-center min-h-[50vh]"><Spinner size="lg" /></div>;
}

/** What a reader sees when a page or an overview is gone or not shared with them. */
export function GoneNote({ title }: { title: string }) {
  const t = useTranslations("tools.pages");
  return (
    <div className="max-w-md mx-auto mt-[12vh] px-4 text-center">
      <h1 className="text-xl font-bold mb-1.5">{title}</h1>
      <p className="text-sm" style={{ color: "var(--muted)" }}>{t("askOwner")}</p>
    </div>
  );
}
