"use client";

import { useLocale, useTranslations } from "next-intl";

/** "Hallo, Name" plus today's date, shared by the start page and the module list. */
export function Greeting({ firstName }: { firstName: string }) {
  const t = useTranslations("workspace.list");
  const locale = useLocale();
  return (
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
  );
}
