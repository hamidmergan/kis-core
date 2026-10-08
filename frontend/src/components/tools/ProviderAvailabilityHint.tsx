"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

/** Under a provider or voice picker: providers come and go with free computing capacity. */
export default function ProviderAvailabilityHint() {
  const t = useTranslations("common");
  const tStatus = useTranslations("ki.providerStatus");
  return (
    <p className="mt-1.5 text-xs text-muted">
      {t("providerAvailability")}{" "}
      <Link href="/provider-status" className="underline hover:text-foreground-soft">
        {tStatus("title")}
      </Link>
    </p>
  );
}
