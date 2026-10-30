"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import LandingPane from "../../_components/event/LandingPane";

export default function EventLandingPage() {
  return (
    <EventAdminGate>
      <LandingPane />
    </EventAdminGate>
  );
}
