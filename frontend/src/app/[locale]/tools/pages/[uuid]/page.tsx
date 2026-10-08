"use client";

import { useParams } from "next/navigation";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Editor from "../_components/Editor";

export default function PageEditorPage() {
  const { uuid } = useParams<{ uuid: string }>();
  return (
    <ProtectedRoute>
      <Editor uuid={uuid} />
    </ProtectedRoute>
  );
}
