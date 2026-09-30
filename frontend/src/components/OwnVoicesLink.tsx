"use client";

import { useTranslations } from "next-intl";
import { usePermissions } from "@/hooks/usePermissions";
import { hasPerm, PERM } from "@/lib/permissions";

/** Next to the voice picker: the way to connect one's own account at an outside voice service. */
export default function OwnVoicesLink() {
  const t = useTranslations("interfaces");
  const { loaded, permissions } = usePermissions();
  if (!loaded || !hasPerm(permissions, PERM.interfaces)) return null;
  return (
    <a href="/interfaces" target="_blank" rel="noopener noreferrer" className="text-sm text-kb hover:underline">
      {t("voicesLink")}
    </a>
  );
}
