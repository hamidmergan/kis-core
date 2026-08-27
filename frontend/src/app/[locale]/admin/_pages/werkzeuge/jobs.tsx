"use client";

// Its own scroll frame, the job table is wide.
import JobsTab from "../../_components/JobsTab";

export default function ToolJobsPage() {
  return (
    <div className="overflow-x-auto">
      <JobsTab />
    </div>
  );
}
