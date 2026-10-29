"use client";

/** The selected feedback sits in the URL, back leads to the list. */

import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import FeedbackDetailTab from "../../_components/FeedbackDetailTab";

export default function FeedbackDetailPage() {
  const router = useRouter();
  const search = useSearchParams();
  const raw = search.get("id");
  const id = raw && /^\d+$/.test(raw) ? Number(raw) : null;

  if (id === null) return null;

  return (
    <FeedbackDetailTab id={id} onBack={() => router.push("/admin/users/feedback")} />
  );
}
