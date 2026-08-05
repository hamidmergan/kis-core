"use client";

/**
 * Whitelist. Der Schalter dafür stand vorher unter System, also an einer ganz
 * anderen Stelle als die Liste, die er steuert. Jetzt stehen beide zusammen.
 */

import { useTranslations } from "next-intl";
import WhitelistTab from "../../_components/WhitelistTab";
import { useAdminEmail } from "../../_nav/AdminAuth";
import { useSetting } from "../../_settings/SettingsProvider";
import { ToggleSetting } from "../../_settings/fields";

export default function WhitelistPage() {
  const t = useTranslations("admin.whitelistCard");
  const email = useAdminEmail();
  const enabled = useSetting<boolean>("whitelist_enabled", true);

  return (
    <div className="space-y-4">
      <ToggleSetting
        field={enabled}
        title={t("title")}
        activeText={t("active")}
        disabledText={t("disabled")}
        hint={enabled.value === false ? t("warningOff") : undefined}
        label={t("toggleAria")}
      />
      {/* Eigener Scrollrahmen: die Zeile aus Eingabefeld und Knopf wird bei
          110 % auf einem sehr schmalen Telefon knapp. */}
      <div className="overflow-x-auto">
        <WhitelistTab adminEmail={email} />
      </div>
    </div>
  );
}
