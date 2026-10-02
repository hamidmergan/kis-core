"use client";

import { useTranslations } from "next-intl";
import { CheckCircle } from "@phosphor-icons/react";
import { Link } from "@/i18n/navigation";
import ToggleRow from "@/components/ui/ToggleRow";
import { ROUTES } from "../../_lib/routes";

/** Optional account link, the toggle only previews the linked state in the mockup. */
export default function LoginOptional({ linked, onToggle }: { linked: boolean; onToggle: () => void }) {
  const t = useTranslations("mockup.stamp.login");
  return (
    <section className="flex flex-col gap-4 rounded-2xl border-2 border-border-soft bg-background p-5" data-testid="login-optional">
      <div>
        <h2 className="text-base font-semibold text-foreground">{t("title")}</h2>
        <p className="mt-1 text-sm text-foreground-soft">{t("body")}</p>
      </div>
      {linked ? (
        <p className="flex items-center gap-2 text-sm text-foreground" data-testid="login-linked">
          <CheckCircle size={20} weight="fill" aria-hidden="true" className="text-success" />
          {t("linked")}
        </p>
      ) : (
        <Link href={ROUTES.login} className="self-start px-3 py-2 text-sm btn-primary rounded-md transition-colors whitespace-nowrap">
          {t("button")}
        </Link>
      )}
      <div className="border-t border-border-soft pt-4">
        <ToggleRow title={t("simulate")} description={t("simulateHint")} checked={linked} onToggle={onToggle} />
      </div>
    </section>
  );
}
