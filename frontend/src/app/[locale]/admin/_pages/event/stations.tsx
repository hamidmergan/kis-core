"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import CardTextsCard from "../../_components/event/CardTextsCard";
import StationsPane from "../../_components/event/StationsPane";

export default function EventStationsPage() {
  return (
    <EventAdminGate>
      <div className="flex flex-col gap-4">
        <CardTextsCard />
        <StationsPane />
      </div>
    </EventAdminGate>
  );
}
