"use client";

/** The jump to the quotas goes through the URL. */

import { useRouter } from "@/i18n/navigation";
import UsersTab from "../../_components/UsersTab";

export default function UsersPage() {
  const router = useRouter();
  return (
    <UsersTab onOpenQuota={(userId) => router.push(`/admin/nutzer/kontingente?user=${userId}`)} />
  );
}
