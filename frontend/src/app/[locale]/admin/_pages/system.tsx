"use client";

/**
 * System. Frueher ein Sammelbecken aus siebzehn Karten, heute drei: der
 * Wartungsmodus und das, was vorher unter "Oberflaeche" stand.
 *
 * Die fuenf Zahlenfelder fuer Parallelitaet sind entfallen, die Maschine wird
 * erkannt und die Grenzen kommen daraus. Was gerade laeuft, steht als
 * Auslastung bei den Auftraegen.
 *
 * "Oberflaeche" war ein eigener Punkt in der Leiste fuer zwei Karten. Beide
 * gelten fuer die ganze Plattform, genau wie der Wartungsmodus, und stehen
 * deshalb jetzt hier.
 */

import MaintenanceCard from "../_settings/MaintenanceCard";
import WorkspaceLabelCard from "../_components/WorkspaceLabelCard";
import HomeNoticeCard from "../_settings/HomeNoticeCard";

export default function SystemPage() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
      <WorkspaceLabelCard />
      <HomeNoticeCard />
    </div>
  );
}
