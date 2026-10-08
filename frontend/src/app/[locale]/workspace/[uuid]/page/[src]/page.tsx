"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import WorkspacePageView from "../../../../tools/pages/_components/WorkspacePageView";

export default function WorkspacePageSourcePage() {
  const { uuid, src } = useParams<{ uuid: string; src: string }>();
  return (
    <ProtectedRoute>
      <Suspense>
        <WorkspacePageView workspaceUuid={uuid} sourceUuid={src} />
      </Suspense>
    </ProtectedRoute>
  );
}
