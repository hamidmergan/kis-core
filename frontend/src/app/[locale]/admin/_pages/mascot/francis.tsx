"use client";

// Die Posen-Uebersicht ist breiter als der Inhaltsbereich. Eigener Scrollrahmen,
// damit nur sie waagerecht scrollt und nicht die ganze Seite.
import FrancisTab from "../../_components/FrancisTab";

export default function FrancisPage() {
  return (
    <div className="overflow-x-auto">
      <FrancisTab />
    </div>
  );
}
