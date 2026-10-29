"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import RaffleCard from "../../_components/event/RaffleCard";
import RaffleEntriesCard from "../../_components/event/RaffleEntriesCard";

export default function EventRafflePage() {
  return (
    <EventAdminGate>
      <div className="flex flex-col gap-4">
        <RaffleCard />
        <RaffleEntriesCard />
      </div>
    </EventAdminGate>
  );
}
