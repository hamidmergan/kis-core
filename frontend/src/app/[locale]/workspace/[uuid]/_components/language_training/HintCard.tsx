"use client";

import { useTranslations } from "next-intl";

import Mascot from "@/components/ui/Mascot";
import { useMascotPref } from "@/hooks/useMascotPref";

/** Der Tipp zur Aufgabe, als Karte an der Aufgabe statt als Antwort im Chat.
 *
 *  Er steht fertig im Datensatz, ist also sofort da und kostet keinen Modellaufruf.
 *  Das Gesicht ist das im Kopf gewaehlte Maskottchen, damit derselbe Begleiter hilft,
 *  der auch im Chat antwortet.
 */
export function HintCard({ text }: { text: string }) {
  const t = useTranslations("workspace.detail.languageTraining");
  const { variant } = useMascotPref();
  // Die Namen sind Eigennamen und werden in keiner Sprache uebersetzt, deshalb stehen
  // sie hier und nicht in den Sprachdateien.
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
