"use client";

/**
 * Kontingente. Der gewählte Nutzer steht in der Adresse (?user=), damit ein
 * Link auf ein bestimmtes Kontingent funktioniert.
 *
 * Der Schritt zurück führt in die Nutzerliste, nicht in einen Zustand innerhalb
 * dieser Seite. Die Zurück-Taste des Browsers tut damit dasselbe wie der Knopf.
 */

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
      onConsumed={() => router.replace("/admin/nutzer/kontingente")}
      onBack={() => router.push("/admin/nutzer/alle-nutzer")}
    />
  );
}
