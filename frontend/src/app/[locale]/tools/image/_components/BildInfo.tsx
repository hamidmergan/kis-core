"use client";

import { useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, useErgebnisAngaben } from "@/components/jobs/ErgebnisInfo";

/** The info icon of a picture or an answer about it: type, provider, prompt or task, and the settings. */
export default function BildInfo({ jobUuid, art }: { jobUuid: string; art: "generate" | "edit" | "analyze" }) {
  const t = useTranslations("tools.image");
  const auftrag = useErgebnisAngaben(jobUuid);
  const a = auftrag?.angaben;
  // Only known option keys get a label, anything else stays out of the info.
  const label = (gruppe: string, key?: string) => (key && t.has(`${gruppe}.${key}`) ? t(`${gruppe}.${key}`) : null);
  const [breite, hoehe] = a?.groesse?.split("x") ?? [];

  return (
    <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
      { label: t("info.type"), wert: t(`info.types.${art}`) },
      { label: t("providerLabel"), wert: a?.anbieter },
      { label: t("result.prompt"), wert: a?.prompt },
      { label: t("analyze.task"), wert: label("analyze.tasks", a?.aufgabe) },
      { label: t("info.question"), wert: a?.frage },
      { label: t("options.style"), wert: a?.stil === "keiner" ? null : label("options.styles", a?.stil) },
      { label: t("options.format"), wert: label("options.formats", a?.format) },
      { label: t("options.quality"), wert: label("options.qualities", a?.qualitaet) },
      { label: t("options.size"), wert: hoehe ? t("info.pixels", { breite, hoehe }) : null },
    ]} />
  );
}
