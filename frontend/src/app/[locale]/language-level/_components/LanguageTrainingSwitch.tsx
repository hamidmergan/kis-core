"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import ToggleRow from "@/components/ui/ToggleRow";

/** The person's own switch for the language trainer. */
export function LanguageTrainingSwitch({ active, onChanged }: { active: boolean; onChanged: () => void }) {
  const t = useTranslations("languageLevel.languageTraining");
  const [busy, setBusy] = useState(false);

  const toggle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch("/api/me/language-training", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active: !active }),
      });
      if (res.ok) onChanged();
    } catch {
      // A network error stays silent, the switch just does not move.
    } finally {
      setBusy(false);
    }
  };

  return (
    <section
      className="rounded-2xl p-5 mt-8"
      style={{ border: "1px solid var(--border)", backgroundColor: "var(--surface)" }}
    >
      <ToggleRow
        title={t("switchTitle")}
        description={t("switchDescription")}
        checked={active}
        onToggle={() => void toggle()}
        disabled={busy}
      />
    </section>
  );
}
