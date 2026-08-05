"use client";

// Die Posen-Uebersicht ist breiter als der Inhaltsbereich. Eigener Scrollrahmen,
// damit nur sie waagerecht scrollt und nicht die ganze Seite.
import HildeTab from "../../_components/HildeTab";

export default function HildePage() {
  return (
    <div className="overflow-x-auto">
      <HildeTab />
    </div>
  );
}
