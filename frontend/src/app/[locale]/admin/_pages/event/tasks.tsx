"use client";

import EventAdminGate from "../../_components/event/EventAdminGate";
import TaskCardCard from "../../_components/event/TaskCardCard";
import TaskStatsCard from "../../_components/event/TaskStatsCard";

export default function EventTasksPage() {
  return (
    <EventAdminGate>
      <div className="flex flex-col gap-4">
        <TaskCardCard />
        <TaskStatsCard />
      </div>
    </EventAdminGate>
  );
}
