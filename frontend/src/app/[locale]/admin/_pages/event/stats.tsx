"use client";

import { useState } from "react";
import EventAdminGate from "../../_components/event/EventAdminGate";
import ResetCard from "../../_components/event/ResetCard";
import StatsCard from "../../_components/event/StatsCard";

/** The key remounts the numbers after a reset so they load again. */
export default function EventStatsPage() {
  const [version, setVersion] = useState(0);
  return (
    <EventAdminGate>
      <StatsCard key={version} />
      <ResetCard onDone={() => setVersion((v) => v + 1)} />
    </EventAdminGate>
  );
}
