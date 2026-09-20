"use client";

/** The operating numbers of the summary pipeline, measured on 20.09. and tunable since.
 *
 * The fields themselves come from the backend, adding one is an entry in
 * services/tool_numbers.py plus its three texts in the language files.
 */

import ToolNumbers from "../../_settings/ToolNumbers";

export default function GrenzenZusammenfassungPage() {
  return (
    // Keine Gruppenueberschrift: der Reiter heisst schon Zusammenfassung, und alle
    // Felder hier gehoeren zu diesem einen Dienst.
    // Die Zahlen wirken beim naechsten Lauf, ein Neustart der Arbeiter ist nicht noetig.
    <div className="space-y-4">
      <ToolNumbers tool="summary" />
    </div>
  );
}
