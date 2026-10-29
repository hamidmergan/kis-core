"use client";

/** Anonymous feedback from testers. */

import { useRouter } from "@/i18n/navigation";
import FeedbackTab from "../../_components/FeedbackTab";

export default function FeedbackPage() {
  const router = useRouter();
  return (
    <FeedbackTab onOpen={(id) => router.push(`/admin/users/feedback-detail?id=${id}`)} />
  );
}
