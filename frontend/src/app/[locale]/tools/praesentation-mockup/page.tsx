"use client";

import { useState } from "react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import InhaltSchritt from "./_components/InhaltSchritt";
import FolienSchritt from "./_components/FolienSchritt";
import FertigSchritt from "./_components/FertigSchritt";

type Schritt = "inhalt" | "folien" | "fertig";

const SCHRITTE: { key: Schritt; label: string }[] = [
  { key: "inhalt", label: "Inhalt" },
  { key: "folien", label: "Folien" },
  { key: "fertig", label: "Fertig" },
];

/**
 * Vorlaeufige Route, keine echte Funktion: testet, ob die Praesentation sich im
 * Aussehen an Uebersetzung/Bildgenerierung anlehnen laesst (zweispaltig, Buehne
 * rechts). Nicht verlinkt, nach der Entscheidung wieder loeschen.
 */
export default function PraesentationMockupPage() {
  const [schritt, setSchritt] = useState<Schritt>("inhalt");

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 py-8">
        <ToolBackLink />
        <h1 className="text-xl font-bold mb-1">Präsentation (Mockup)</h1>
        <p className="text-sm text-muted mb-6">
          Vorläufige Route, nicht verlinkt. Nur zum Aussehen vergleichen, ohne echte Funktion dahinter.
        </p>

        <nav className="flex justify-center gap-8 pb-3 mb-8 border-b border-border-soft" aria-label="Schritte">
          {SCHRITTE.map((s) => {
            const aktiv = s.key === schritt;
            return (
              <button
                key={s.key}
                type="button"
                onClick={() => setSchritt(s.key)}
                className={`text-sm pb-2.5 -mb-px border-b-2 transition-colors ${
                  aktiv ? "font-semibold text-kb border-kb" : "text-muted-soft border-transparent hover:text-kb"
                }`}
              >
                {s.label}
              </button>
            );
          })}
        </nav>

        {schritt === "inhalt" && <InhaltSchritt onNext={() => setSchritt("folien")} />}
        {schritt === "folien" && <FolienSchritt onBack={() => setSchritt("inhalt")} onNext={() => setSchritt("fertig")} />}
        {schritt === "fertig" && <FertigSchritt onBack={() => setSchritt("folien")} onRestart={() => setSchritt("inhalt")} />}
      </div>
    </ProtectedRoute>
  );
}
