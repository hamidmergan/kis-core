"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import StatsCard from "../../_components/event/StatsCard";

export default function EventStatsPage() {
  return (
    <EventAdminGate>
      <StatsCard />
    </EventAdminGate>
  );
}
