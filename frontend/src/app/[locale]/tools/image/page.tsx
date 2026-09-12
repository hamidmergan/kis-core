"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import GenerateTab from "./_tabs/GenerateTab";
import EditTab from "./_tabs/EditTab";
import AnalyzeTab from "./_tabs/AnalyzeTab";

type Tab = "generate" | "edit" | "analyze";


export default function ImagePage() {
  const t = useTranslations("tools.image");
  const tt = useTranslations("tools.image.tabs");
  const tabs: { id: Tab; label: string }[] = [
    { id: "generate", label: tt("generate") },
    { id: "edit", label: tt("edit") },
    { id: "analyze", label: tt("analyze") },
  ];
  const [activeTab, setActiveTab] = useState<Tab>("generate");

  return (
    <ProtectedRoute>
      <div className="max-w-4xl mx-auto px-4 py-8" data-tour="tool-image">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">{t("title")}</h1>
        <p className="text-sm text-muted mb-6">
          {t("intro")}
        </p>

        <div className="flex gap-1 mb-6 border-b border-border-soft">
          {tabs.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === id
                  ? "border-kb text-kb"
                  : "border-transparent text-muted hover:text-foreground-soft"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className={activeTab === "generate" ? "" : "hidden"}><GenerateTab /></div>
        <div className={activeTab === "edit" ? "" : "hidden"}><EditTab /></div>
        <div className={activeTab === "analyze" ? "" : "hidden"}><AnalyzeTab /></div>
      </div>
    </ProtectedRoute>
  );
}
