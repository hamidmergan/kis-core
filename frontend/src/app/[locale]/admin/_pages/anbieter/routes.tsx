"use client";

// Its own scroll frame, a feature row needs width.
import ProvidersTab from "../../_components/providers";

export default function ProviderRoutesPage() {
  return (
    <div className="overflow-x-auto">
      <ProvidersTab only="routes" />
    </div>
  );
}
