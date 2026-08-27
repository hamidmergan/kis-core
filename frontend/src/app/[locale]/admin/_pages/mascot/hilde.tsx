"use client";

// Its own scroll frame so only the overview scrolls horizontally.
import HildeTab from "../../_components/HildeTab";

export default function HildePage() {
  return (
    <div className="overflow-x-auto">
      <HildeTab />
    </div>
  );
}
