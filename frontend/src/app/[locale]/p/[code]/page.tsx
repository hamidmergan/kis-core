"use client";

import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import SharedView from "../../tools/pages/_components/SharedView";

export default function SharedPagePage() {
  const { code } = useParams<{ code: string }>();
  return (
    <ProtectedRoute>
      <SharedView code={code} />
    </ProtectedRoute>
  );
}
