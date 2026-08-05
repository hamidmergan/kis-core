"use client";

// Die Auslastung steckt bewusst in JobsTab: hierher schaut man, wenn jemand
// meldet dass es haengt, und dann will man die Auftragsliste direkt darunter.
//
// Eigener Scrollrahmen, weil Auftragstabelle und Auslastungsbalken breiter sind
// als ein Telefon bei 110 %. So scrollt nur der Inhalt waagerecht, nicht die
// ganze Seite mitsamt Seitenleiste.
import JobsTab from "../../_components/JobsTab";

export default function ToolJobsPage() {
  return (
    <div className="overflow-x-auto">
      <JobsTab />
    </div>
  );
}
