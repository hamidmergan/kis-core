"use client";

/**
 * Die Nutzerliste. Der Sprung zu den Kontingenten läuft jetzt über die Adresse
 * statt über einen Rückruf, damit die Kontingent-Seite auch direkt erreichbar
 * ist. Vorher war sie nur über diesen Klick zu finden und stand in keinem Menü.
 */

import { useRouter } from "@/i18n/navigation";
import UsersTab from "../../_components/UsersTab";

export default function UsersPage() {
  const router = useRouter();
  return (
    <UsersTab onOpenQuota={(userId) => router.push(`/admin/nutzer/kontingente?user=${userId}`)} />
  );
}
