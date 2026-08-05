"use client";

/**
 * Wartungsmodus. Keine gewöhnliche Einstellung, deshalb eigene Karte statt
 * ToggleSetting: der Wert liegt hinter /api/admin/maintenance, nicht in den
 * Einstellungen, und der Schalter ist rot, weil er die Plattform für alle
 * ausser Admins sperrt.
 */

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

export default function MaintenanceCard() {
  const t = useTranslations("admin.maintenanceCard");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/admin/maintenance", { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setEnabled(!!d.enabled))
      .catch(() => {});
  }, []);

  const toggle = async (value: boolean) => {
    setWorking(true);
    setError("");
    try {
      const res = await fetch("/api/admin/maintenance", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: value }),
      });
      if (!res.ok) throw new Error(t("toggleFailed"));
      setEnabled(value);
    } catch (e) {
      setError(String(e));
    } finally {
      setWorking(false);
    }
  };

  if (enabled === null) return null;

  return (
    <div className="border border-border-soft rounded-xl bg-background p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-foreground">{t("title")}</p>
          <p className="text-xs text-muted mt-1">{enabled ? t("active") : t("disabled")}</p>
        </div>
        <button
          onClick={() => toggle(!enabled)}
          disabled={working}
          className={`relative inline-flex shrink-0 w-11 h-6 rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none enabled:hover:border-error ${
            enabled ? "bg-error" : "bg-border"
          } disabled:opacity-50`}
          aria-label={t("toggleAria")}
        >
          <span
            className={`pointer-events-none inline-block w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 ${
              enabled ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      </div>
      {error && <p className="mt-3 text-xs text-error">{error}</p>}
    </div>
  );
}
