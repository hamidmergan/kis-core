"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import StationsPane from "../../_components/event/StationsPane";

export default function EventStationsPage() {
  return (
    <EventAdminGate>
      <StationsPane />
    </EventAdminGate>
  );
}
