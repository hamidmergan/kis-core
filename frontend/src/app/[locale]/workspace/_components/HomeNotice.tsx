"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Notice {
  enabled: boolean;
  text: string;
}

/**
 * Admin-configurable notice banner for the start page. Shown to all users
 * (any role) above "Nächste Termine". Reads the public /health/labels probe
 * so it renders without auth/admin rights. Renders nothing unless the admin
 * enabled it AND left a non-empty text.
 */
export default function HomeNotice() {
  const [notice, setNotice] = useState<Notice | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .fetch("/api/health/labels", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data) return;
        setNotice({
          enabled: data.home_notice_enabled === true,
          text: typeof data.home_notice_text === "string" ? data.home_notice_text : "",
        });
      })
      .catch(() => {
        /* ignore - banner is non-critical */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!notice || !notice.enabled || !notice.text.trim()) return null;

  return (
    <div className="mb-10 flex justify-center">
      <div
        className="max-w-2xl w-full rounded-xl border border-warn-border bg-warn-bg px-5 py-4 text-center text-sm text-warn-strong whitespace-pre-line"
        role="status"
      >
        {notice.text}
      </div>
    </div>
  );
}
