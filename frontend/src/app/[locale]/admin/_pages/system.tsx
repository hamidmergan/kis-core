"use client";

/** System: maintenance mode and the two platform-wide cards. */

import MaintenanceCard from "../_settings/MaintenanceCard";
import HomeNoticeCard from "../_settings/HomeNoticeCard";
import WelcomeModalCard from "../_settings/WelcomeModalCard";

export default function SystemPage() {
  return (
    <div className="space-y-4">
      <MaintenanceCard />
      <HomeNoticeCard />
      <WelcomeModalCard />
    </div>
  );
}
