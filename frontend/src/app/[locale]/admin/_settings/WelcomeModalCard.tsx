"use client";

/** Switch and text of the first-login welcome dialog belong in one card. */

import SwitchTextCard from "./SwitchTextCard";

export default function WelcomeModalCard() {
  return (
    <SwitchTextCard
      namespace="admin.welcomeModalCard"
      enabledKey="welcome_modal_enabled"
      enabledDefault={true}
      textKey="welcome_modal_text"
      rows={6}
    />
  );
}
