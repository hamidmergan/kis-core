"use client";

/**
 * Reiter "KI-Verhalten" unter Sprachniveau: die vier grossen Textfelder, mit
 * denen die KI fragt, urteilt und danach antwortet.
 */

import LanguageDiagnosisCard from "../../_components/LanguageDiagnosisCard";
import DiagnosisGradingCard from "../../_components/DiagnosisGradingCard";
import DiagnosisExamplesCard from "../../_components/DiagnosisExamplesCard";
import DiagnosisAdaptiveBehaviorCard from "../../_components/DiagnosisAdaptiveBehaviorCard";

export default function AiBehaviourPage() {
  return (
    <div className="space-y-4">
      <LanguageDiagnosisCard />
      <DiagnosisGradingCard />
      <DiagnosisExamplesCard />
      <DiagnosisAdaptiveBehaviorCard />
    </div>
  );
}
