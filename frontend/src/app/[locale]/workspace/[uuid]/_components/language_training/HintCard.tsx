"use client";

import { useTranslations } from "next-intl";

import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";

/** The hint as a card on the exercise, there at once and without a model call. */
export function HintCard({ text }: { text: string }) {
  const t = useTranslations("workspace.detail.languageTraining");
  const { variant } = useMascotPref();
  // The names are proper nouns and therefore not in the language files.
  const name = variant === "hilde" ? "Hilde" : "Francis";
  return (
    <div className="flex items-start gap-2.5 px-3 py-2.5 rounded-2xl border-2"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}>
      <Mascot variant={variant} size={40} state="idle" className="shrink-0" />
      <p className="text-sm leading-relaxed" style={{ color: "var(--foreground)" }}>
        <span className="font-semibold">{t("common.hintFrom", { name })}</span>{" "}
        {text}
      </p>
    </div>
  );
}
