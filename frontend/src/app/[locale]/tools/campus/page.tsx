"use client";

import ProtectedRoute from "@/components/auth/ProtectedRoute";
import CampusSeite from "./_components/CampusSeite";

export default function CampusPage() {
  return (
    <ProtectedRoute>
      <div className="aia-scale" style={{ display: "contents" }}>
        <CampusSeite />
      </div>
    </ProtectedRoute>
  );
}
