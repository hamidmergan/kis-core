"use client";

/** Switch and text of the start page notice belong in one card. */

import SwitchTextCard from "./SwitchTextCard";

export default function HomeNoticeCard() {
  return (
    <SwitchTextCard
      namespace="admin.homeNoticeCard"
      enabledKey="home_notice_enabled"
      enabledDefault={false}
      textKey="home_notice_text"
      rows={8}
    />
  );
}
