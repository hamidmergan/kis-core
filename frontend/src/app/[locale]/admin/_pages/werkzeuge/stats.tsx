"use client";

// Die Statistiktabelle hat sechs Spalten und passt auf einem Telefon nicht.
// Eigener Scrollrahmen statt Umbruch: eine Tabelle mit umgebrochenen Zeilen
// waere schlechter lesbar als eine, die man seitwaerts schiebt.
import StatsTab from "../../_components/StatsTab";

export default function ToolStatsPage() {
  return (
    <div className="overflow-x-auto">
      <StatsTab />
    </div>
  );
}
