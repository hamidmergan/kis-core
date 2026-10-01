"use client";

import { useState } from "react";
import { CaretLeft } from "@phosphor-icons/react";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import ToolBackLink from "@/components/ui/ToolBackLink";
import { Link } from "@/i18n/navigation";
import InhaltSchritt from "./_components/InhaltSchritt";
import FolienSchritt from "./_components/FolienSchritt";
import FertigSchritt from "./_components/FertigSchritt";

type Schritt = "inhalt" | "folien" | "fertig";

const SCHRITTE: { key: Schritt; label: string; mobilTitel: string }[] = [
  { key: "inhalt", label: "Inhalt", mobilTitel: "Präsentation" },
  { key: "folien", label: "Folien", mobilTitel: "Folien" },
  { key: "fertig", label: "Fertig", mobilTitel: "Fertig" },
];

/** Temporary unlinked route that rebuilds the design mockup, to be deleted after the decision. */
export default function PraesentationMockupPage() {
  const [schritt, setSchritt] = useState<Schritt>("inhalt");
  const index = SCHRITTE.findIndex((s) => s.key === schritt);
  const zurueck = () => setSchritt(SCHRITTE[Math.max(0, index - 1)].key);

  return (
    <ProtectedRoute>
      <div className="max-w-6xl mx-auto px-4 pb-8 lg:py-8">
        {/* Handy: schmale Kopfzeile mit Zurueck und Fortschrittsbalken statt Reitern. */}
        <div className="lg:hidden -mx-4 mb-4">
          <div className="h-14 flex items-center gap-3 px-4">
            {index === 0 ? (
              <Link href="/" aria-label="Zurück" className="text-muted hover:text-kb transition-colors">
                <CaretLeft size={20} weight="bold" />
              </Link>
            ) : (
              <button type="button" onClick={zurueck} aria-label="Zurück" className="text-muted hover:text-kb transition-colors">
                <CaretLeft size={20} weight="bold" />
              </button>
            )}
            <h1 className="text-base font-bold">{SCHRITTE[index].mobilTitel}</h1>
          </div>
          {index === 0 ? (
            <div className="h-px bg-border-soft" />
          ) : (
            <div className="h-1 bg-border-soft">
              <div className="h-1 bg-kb transition-all" style={{ width: `${((index + 1) / SCHRITTE.length) * 100}%` }} />
            </div>
          )}
        </div>

        <div className="hidden lg:block">
          {index === 0 ? (
            <>
              <ToolBackLink />
              <h1 className="text-xl font-bold mb-1">Präsentation</h1>
              <p className="text-sm text-muted mb-6">
                Lade Material hoch oder wähle einen Workspace, wir bauen daraus eine Foliensammlung.
              </p>
            </>
          ) : (
            <nav className="flex justify-center gap-8 pb-3 mb-8 border-b border-border-soft" aria-label="Schritte">
              {SCHRITTE.map((s, i) => {
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
                    {i + 1}&nbsp;&nbsp;{s.label}
                  </button>
                );
              })}
            </nav>
          )}
        </div>

        {schritt === "inhalt" && <InhaltSchritt onNext={() => setSchritt("folien")} />}
        {schritt === "folien" && <FolienSchritt onNext={() => setSchritt("fertig")} />}
        {schritt === "fertig" && <FertigSchritt onBack={() => setSchritt("folien")} onRestart={() => setSchritt("inhalt")} />}
      </div>
    </ProtectedRoute>
  );
}
