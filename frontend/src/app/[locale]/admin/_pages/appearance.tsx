"use client";

/**
 * Was die Nutzer sehen und wie es heisst. Zwei Karten, deshalb keine
 * Unterseiten: eine zweite Ebene fuer zwei Karten waere reine Buerokratie.
 */

import WorkspaceLabelCard from "../_components/WorkspaceLabelCard";
import HomeNoticeCard from "../_settings/HomeNoticeCard";

export default function AppearancePage() {
  return (
    <div className="space-y-4">
      <WorkspaceLabelCard />
      <HomeNoticeCard />
    </div>
  );
}
