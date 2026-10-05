"use client";

import { useTranslations } from "next-intl";

/** Under a provider or voice picker: providers come and go with free computing capacity. */
export default function ProviderAvailabilityHint() {
  const t = useTranslations("common");
  return <p className="mt-1.5 text-xs text-muted">{t("providerAvailability")}</p>;
}
