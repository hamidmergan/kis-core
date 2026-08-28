"use client";

/** Access codes, behind the same server switch as the LDAP users. */

import { useTranslations } from "next-intl";
import AccessCodesTab from "../../_components/AccessCodesTab";
import { usePermissions } from "@/hooks/usePermissions";

export default function AccessCodesPage() {
  const t = useTranslations("admin.accessCodes");
  const { loaded, permissions } = usePermissions();

  if (!loaded) return null;
  if (!permissions.allow_ldap_user_create) {
    return <p className="text-sm text-muted-soft">{t("disabled")}</p>;
  }
  return <AccessCodesTab />;
}
