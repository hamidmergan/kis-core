"use client";

import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import CollectionView from "../../tools/pages/_components/CollectionView";

export default function CollectionPage() {
  const { code } = useParams<{ code: string }>();
  return (
    <ProtectedRoute>
      <CollectionView code={code} />
    </ProtectedRoute>
  );
}
