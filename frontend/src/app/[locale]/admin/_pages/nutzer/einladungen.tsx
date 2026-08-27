"use client";

/** Invitations, behind the same server switch as the LDAP users. */

import { useTranslations } from "next-intl";
import InvitesTab from "../../_components/InvitesTab";
import { usePermissions } from "@/hooks/usePermissions";

export default function InvitesPage() {
  const t = useTranslations("admin.invites");
  const { loaded, permissions } = usePermissions();

  if (!loaded) return null;
  if (!permissions.allow_ldap_user_create) {
    return <p className="text-sm text-muted-soft">{t("disabled")}</p>;
  }
  return <InvitesTab />;
}
