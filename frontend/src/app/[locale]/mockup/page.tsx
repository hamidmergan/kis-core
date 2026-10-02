"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Gear, Info, Stamp } from "@phosphor-icons/react";
import { StartTile } from "../_components/StartTile";
import { resetMockup } from "./_lib/store";
import { ROUTES } from "./_lib/routes";

export default function MockupOverviewPage() {
  const t = useTranslations("mockup.overview");
  const [done, setDone] = useState(false);
  return (
    <main className="max-w-3xl mx-auto px-4 py-8 flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-[-0.01em] text-foreground">{t("title")}</h1>
        <p className="text-base text-foreground-soft mt-1">{t("intro")}</p>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <StartTile href={ROUTES.info} icon={Info} title={t("info.title")} body={t("info.body")} testId="mockup-info" />
        <StartTile href={ROUTES.stamp} icon={Stamp} title={t("stamp.title")} body={t("stamp.body")} testId="mockup-stamp" />
        <StartTile href={ROUTES.admin} icon={Gear} title={t("admin.title")} body={t("admin.body")} testId="mockup-admin" />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => {
            resetMockup();
            setDone(true);
          }}
          className="px-4 py-2 text-sm rounded-md border-2 border-border text-foreground-soft hover:border-kb transition-colors"
        >
          {t("resetAll")}
        </button>
        {done && <span className="text-sm text-foreground-soft">{t("resetDone")}</span>}
      </div>
    </main>
  );
}
