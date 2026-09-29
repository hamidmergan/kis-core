"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import Tabs from "@/components/ui/Tabs";
import GenerateTab from "./_tabs/GenerateTab";
import EditTab from "./_tabs/EditTab";
import AnalyzeTab from "./_tabs/AnalyzeTab";
import Verlauf from "./_components/Verlauf";
import type { BildErgebnis } from "./_components/useBildAuftraege";
import type { Uebergabe } from "./_utils";

type Tab = "generate" | "edit" | "analyze";


export default function ImagePage() {
  const t = useTranslations("tools.image");
  const tt = useTranslations("tools.image.tabs");
  const [activeTab, setActiveTab] = useState<Tab>("generate");
  const [uebergabe, setUebergabe] = useState<{ ziel: "edit" | "analyze"; bild: Uebergabe } | null>(null);

  // A result or a history picture moves into the other task, all tabs stay mounted and keep their own state.
  const uebergeben = useCallback((ziel: "edit" | "analyze", bild: BildErgebnis) => {
    const datei = new File([bild.blob], bild.filename, { type: bild.blob.type || "image/png" });
    setUebergabe({ ziel, bild: { id: Date.now(), datei } });
    setActiveTab(ziel);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8" data-tour="tool-image">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
        <p className="text-sm text-muted mb-6">{t("intro")}</p>

        <Tabs
          className="mb-6"
          active={activeTab}
          onChange={setActiveTab}
          items={[
            { key: "generate", label: tt("generate") },
            { key: "edit", label: tt("edit") },
            { key: "analyze", label: tt("analyze") },
          ]}
        />

        <div className={activeTab === "generate" ? "" : "hidden"}>
          <GenerateTab onUebergabe={uebergeben} />
        </div>
        <div className={activeTab === "edit" ? "" : "hidden"}>
          <EditTab uebergabe={uebergabe?.ziel === "edit" ? uebergabe.bild : null} onUebergabe={uebergeben} />
        </div>
        <div className={activeTab === "analyze" ? "" : "hidden"}>
          <AnalyzeTab uebergabe={uebergabe?.ziel === "analyze" ? uebergabe.bild : null} />
        </div>

        <Verlauf onBearbeiten={(b) => uebergeben("edit", b)} onBeschreiben={(b) => uebergeben("analyze", b)} />
      </div>
    </ProtectedRoute>
  );
}
