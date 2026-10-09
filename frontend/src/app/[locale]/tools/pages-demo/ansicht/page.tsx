"use client";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import DemoView from "../../pages/_components/DemoView";

export default function PagesDemoViewPage() {
  return (
    <ProtectedRoute>
      <DemoView />
    </ProtectedRoute>
  );
}
