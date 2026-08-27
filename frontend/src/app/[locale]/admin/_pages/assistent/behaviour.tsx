"use client";

/** The level ladder on top, the prompt texts sit collapsed below. */

import { useTranslations } from "next-intl";
import CollapsibleCard from "@/components/ui/CollapsibleCard";
import LanguageDiagnosisCard from "../../_components/LanguageDiagnosisCard";
import DiagnosisGradingCard from "../../_components/DiagnosisGradingCard";
import DiagnosisLevelsCard from "../../_components/DiagnosisLevelsCard";
import DiagnosisAdaptiveBehaviorCard from "../../_components/DiagnosisAdaptiveBehaviorCard";

export default function AiBehaviourPage() {
  const t = useTranslations("admin.diagnosisAdvanced");

  return (
    <div className="space-y-4">
      <DiagnosisLevelsCard />
      <CollapsibleCard title={t("title")} description={t("description")}>
        <div className="space-y-4">
          <LanguageDiagnosisCard />
          <DiagnosisGradingCard />
          <DiagnosisAdaptiveBehaviorCard />
        </div>
      </CollapsibleCard>
    </div>
  );
}
