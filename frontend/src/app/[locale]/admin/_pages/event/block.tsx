"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import EventPane from "../../_components/event/EventPane";

export default function EventBlockPage() {
  return (
    <EventAdminGate>
      <EventPane />
    </EventAdminGate>
  );
}
