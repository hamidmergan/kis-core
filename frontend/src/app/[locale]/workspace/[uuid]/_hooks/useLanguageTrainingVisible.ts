"use client";

import { useEffect, useState } from "react";

/** Whether the language trainer is offered to this person, switched on and has a stored level. */
export function useLanguageTrainingVisible(): boolean {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setVisible(
          data.language_training_enabled === true
            && data.language_training_active === true
            && typeof data.language_level === "string",
        );
      })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, []);
  return visible;
}
