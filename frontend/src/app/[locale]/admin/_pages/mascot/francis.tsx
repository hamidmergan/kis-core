"use client";

// Its own scroll frame so only the overview scrolls horizontally.
import FrancisTab from "../../_components/FrancisTab";

export default function FrancisPage() {
  return (
    <div className="overflow-x-auto">
      <FrancisTab />
    </div>
  );
}
