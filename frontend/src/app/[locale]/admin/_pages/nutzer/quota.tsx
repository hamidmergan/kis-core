"use client";

/** The chosen user sits in the URL, the way back leads into the list. */

import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import QuotaTab from "../../_components/QuotaTab";

export default function QuotaPage() {
  const router = useRouter();
  const search = useSearchParams();
  const raw = search.get("user");
  const userId = raw && /^\d+$/.test(raw) ? Number(raw) : null;

  return (
    <QuotaTab
      targetUserId={userId}
      onConsumed={() => router.replace("/admin/users/quotas")}
      onBack={() => router.push("/admin/users/all")}
    />
  );
}
