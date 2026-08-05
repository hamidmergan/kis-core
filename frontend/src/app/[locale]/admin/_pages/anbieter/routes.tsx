"use client";

// Eigener Scrollrahmen: eine Funktionszeile besteht aus Name, Anbieterauswahl,
// Modellfeld und Testknopf und wird schmaler als 800 px nicht sinnvoll.
import ProvidersTab from "../../_components/providers";

export default function ProviderRoutesPage() {
  return (
    <div className="overflow-x-auto">
      <ProvidersTab only="routes" />
    </div>
  );
}
