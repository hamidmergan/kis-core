"use client";

/**
 * System. Frueher ein Sammelbecken aus siebzehn Karten, heute nur noch der
 * Wartungsmodus.
 *
 * Die fuenf Zahlenfelder fuer Parallelitaet sind entfallen, die Maschine wird
 * erkannt und die Grenzen kommen daraus. Was gerade laeuft, steht als
 * Auslastung bei den Auftraegen.
 */

import MaintenanceCard from "../_settings/MaintenanceCard";

export default function SystemPage() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
    </div>
  );
}
