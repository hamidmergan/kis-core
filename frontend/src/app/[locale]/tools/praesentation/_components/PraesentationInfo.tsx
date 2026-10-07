"use client";

import { useLocale, useTranslations } from "next-intl";
import { ErgebnisInfoKnopf, useErgebnisAngaben, type Auftrag } from "@/components/jobs/ErgebnisInfo";
import { sprachName } from "@/lib/format";

/** The info icon of a deck: material, template, instruction, picture style and who wrote and drew. */
export default function PraesentationInfo({ jobUuid, bereit, auftrag: mitgebracht }: {
  jobUuid: string;
  /** The info is read once the slides stand, before that there is nothing to tell. */
  bereit: boolean;
  /** The demo brings its info along, a real run reads it from its job. */
  auftrag?: Auftrag;
}) {
  const locale = useLocale();
  const t = useTranslations("common.result");
  const gelesen = useErgebnisAngaben(mitgebracht || !bereit ? null : jobUuid);
  const auftrag = mitgebracht ?? gelesen;
  const a = auftrag?.angaben;
  return (
    <ErgebnisInfoKnopf auftrag={auftrag} zeilen={[
      { label: t("sources"), wert: a?.material?.split(", ").join("\n") },
      { label: t("template"), wert: a?.vorlage },
      { label: t("language"), wert: sprachName(a?.sprache, locale) },
      { label: t("instructions"), wert: a?.anweisung },
      { label: t("imageStyle"), wert: a?.bildstil },
      { label: t("textProvider"), wert: a?.anbieter },
      { label: t("imageProvider"), wert: a?.bildanbieter },
    ]} />
  );
}
