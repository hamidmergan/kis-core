"use client";

// Eigener Scrollrahmen, weil die Auftragstabelle breiter ist als ein Telefon
// bei 110 %. So scrollt nur der Inhalt waagerecht, nicht die ganze Seite.
import JobsTab from "../../_components/JobsTab";

export default function ToolJobsPage() {
  return (
    <div className="overflow-x-auto">
      <JobsTab />
    </div>
  );
}
